"""Consulta de prerregistros del kit de salud (R8, R10, D-07, apps#7).

El personal entra con su usuario de Samba AD. La app hace bind por LDAPS con
esas credenciales, verifica el certificado del DC con la raíz del kit y solo
deja entrar a quien esté en el grupo clinicos. En PostgreSQL usa el usuario
consultas, que lee los prerregistros y solo puede cambiar atendido y
atendido_en.
"""
import hmac
import logging
import os
import re
import secrets
import ssl
import sys
from datetime import date, timedelta

import psycopg
from flask import Flask, redirect, render_template, request, session, url_for
from ldap3 import Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from psycopg.rows import dict_row
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
# Solo Caddy (127.0.0.1) llega a la app; de él salen la IP y el esquema del cliente
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.config.update(
    # Llave nueva en cada arranque (gunicorn --preload la comparte entre
    # workers). No se guarda en ningún lado; reiniciar cierra las sesiones.
    SECRET_KEY=secrets.token_bytes(32),
    SESSION_COOKIE_NAME="__Host-consultas",
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    # Sin actividad en 30 minutos hay que volver a entrar
    PERMANENT_SESSION_LIFETIME=timedelta(minutes=30),
)

# Registro de accesos a stdout; Docker lo manda a journald y de ahí a kit01 (F-15)
registro = logging.getLogger("consultas")
registro.addHandler(logging.StreamHandler(sys.stdout))
registro.setLevel(logging.INFO)
registro.propagate = False

ZONA = os.environ.get("ZONA_HORARIA", "America/Bogota")
DB = {
    "host": os.environ.get("DB_HOST", "10.20.20.11,fd5a:fc7e:d716:20::11"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "prerregistro"),
    "user": os.environ.get("DB_USER", "consultas"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "connect_timeout": 3,
    # Las horas se muestran en la hora local del kit
    "options": f"-c TimeZone={ZONA}",
}
LDAP_HOST = os.environ.get("LDAP_HOST", "dc01.ad.salud.movil")
LDAP_DOMINIO = os.environ.get("LDAP_DOMINIO", "ad.salud.movil")
LDAP_BASE = os.environ.get("LDAP_BASE", "DC=ad,DC=salud,DC=movil")
LDAP_GRUPO = os.environ.get("LDAP_GRUPO", "clinicos")
LDAP_CA = os.environ.get("LDAP_CA", "/certs/raiz.crt")
GRUPO_DN = f"CN={LDAP_GRUPO},CN=Users,{LDAP_BASE}".lower()

TIPOS_DOCUMENTO = {
    "CC": "Cédula de ciudadanía",
    "TI": "Tarjeta de identidad",
    "RC": "Registro civil",
    "CE": "Cédula de extranjería",
    "OTRO": "Otro documento",
    "NINGUNO": "Sin documento",
}
MOTIVOS = {
    "CONTROL": "Control o revisión",
    "FIEBRE": "Fiebre o malestar",
    "DOLOR": "Dolor",
    "EMBARAZO": "Embarazo",
    "VACUNACION": "Vacunación",
    "OTRO": "Otro motivo",
}
COLUMNAS = ("id, creado, codigo, nombres, apellidos, tipo_documento, numero_documento,"
            " fecha_nacimiento, celular, motivo, detalle, atendido_en")


@app.after_request
def cabeceras(respuesta):
    respuesta.headers["Content-Security-Policy"] = "default-src 'self'; form-action 'self'; frame-ancestors 'none'"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@app.before_request
def revisar_csrf():
    # Todo POST lleva el token de la sesión (además de SameSite=Strict)
    if request.method == "POST":
        token = session.get("csrf", "")
        if not token or not hmac.compare_digest(token, request.form.get("csrf", "")):
            # Página abierta desde antes de un reinicio o de que venciera la sesión
            session.clear()
            return redirect(url_for("entrar", vencida=1))


@app.context_processor
def plantillas():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf": session["csrf"], "usuario": session.get("usuario"), "nombre": session.get("nombre")}


def autenticar(usuario, clave):
    """Bind LDAPS con las credenciales del usuario. Devuelve (nombre, en_grupo)
    o None si el usuario o la clave no sirven."""
    tls = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=LDAP_CA, version=ssl.PROTOCOL_TLS_CLIENT)
    servidor = Server(LDAP_HOST, port=636, use_ssl=True, tls=tls, connect_timeout=5)
    conexion = Connection(servidor, user=f"{usuario}@{LDAP_DOMINIO}", password=clave, receive_timeout=10)
    try:
        if not conexion.bind():
            return None
        conexion.search(LDAP_BASE, f"(sAMAccountName={escape_filter_chars(usuario)})",
                        attributes=["displayName", "givenName", "memberOf"])
        if not conexion.entries:
            return None
        entrada = conexion.entries[0]
        grupos = [g.lower() for g in entrada.memberOf.values]
        nombre = str(entrada.displayName or entrada.givenName or usuario)
        return nombre, GRUPO_DN in grupos
    finally:
        conexion.unbind()


def edad(nacimiento):
    if not nacimiento:
        return None
    hoy = date.today()
    return hoy.year - nacimiento.year - ((hoy.month, hoy.day) < (nacimiento.month, nacimiento.day))


def leer(busqueda):
    filtro, parametros = "", {}
    if busqueda:
        filtro = " AND (codigo = upper(%(q)s) OR numero_documento = %(q)s)"
        parametros["q"] = busqueda
    with psycopg.connect(**DB, row_factory=dict_row) as conexion:
        pendientes = conexion.execute(
            f"SELECT {COLUMNAS} FROM prerregistros WHERE NOT atendido{filtro} ORDER BY creado",
            parametros).fetchall()
        atendidos = conexion.execute(
            f"SELECT {COLUMNAS} FROM prerregistros WHERE atendido AND atendido_en::date = current_date{filtro}"
            " ORDER BY atendido_en DESC", parametros).fetchall()
    for fila in pendientes + atendidos:
        fila["edad"] = edad(fila["fecha_nacimiento"])
        fila["tipo_documento"] = TIPOS_DOCUMENTO.get(fila["tipo_documento"], fila["tipo_documento"])
        fila["motivo"] = MOTIVOS.get(fila["motivo"], fila["motivo"])
    return pendientes, atendidos


@app.get("/entrar")
def entrar():
    if session.get("usuario"):
        return redirect(url_for("inicio"))
    vencida = "vencida" in request.args
    return render_template("entrar.html", error="Su sesión terminó. Vuelva a entrar." if vencida else None)


@app.post("/entrar")
def entrar_enviar():
    usuario = (request.form.get("usuario") or "").strip().lower()
    usuario = usuario.removesuffix("@" + LDAP_DOMINIO)
    clave = request.form.get("clave") or ""
    # Sin clave, AD aceptaría un bind anónimo
    if not re.fullmatch(r"[a-z0-9._-]{1,64}", usuario) or not clave:
        return render_template("entrar.html", error="Escriba su usuario y su contraseña.", usuario=usuario), 400
    try:
        resultado = autenticar(usuario, clave)
    except LDAPException as e:
        registro.warning("No se pudo consultar Samba AD (%s): %s", LDAP_HOST, e)
        return render_template("entrar.html", usuario=usuario, error=(
            "No se pudo comprobar su usuario porque el servidor de cuentas no responde. "
            "Intente de nuevo en unos minutos.")), 503
    if resultado is None:
        registro.info("Entrada rechazada: %s desde %s (usuario o clave)", usuario, request.remote_addr)
        return render_template("entrar.html", usuario=usuario, error="El usuario o la contraseña no son correctos."), 401
    nombre, en_grupo = resultado
    if not en_grupo:
        registro.info("Entrada rechazada: %s desde %s (no está en %s)", usuario, request.remote_addr, LDAP_GRUPO)
        return render_template("entrar.html", usuario=usuario, error=(
            "Su usuario no tiene acceso a los prerregistros. Solo entra el personal clínico.")), 403
    session.clear()
    session.permanent = True
    session.update(usuario=usuario, nombre=nombre, csrf=secrets.token_urlsafe(32))
    registro.info("Entrada: %s desde %s", usuario, request.remote_addr)
    return redirect(url_for("inicio"))


@app.post("/salir")
def salir():
    if session.get("usuario"):
        registro.info("Salida: %s desde %s", session["usuario"], request.remote_addr)
    session.clear()
    return redirect(url_for("entrar"))


@app.get("/")
def inicio():
    if not session.get("usuario"):
        return redirect(url_for("entrar"))
    busqueda = (request.args.get("q") or "").strip()[:20]
    try:
        pendientes, atendidos = leer(busqueda)
    except psycopg.OperationalError:
        registro.warning("PostgreSQL de clinica01 no responde")
        return render_template("lista.html", busqueda=busqueda, pendientes=[], atendidos=[], aviso=(
            "En este momento no se pueden leer los prerregistros. Intente de nuevo en unos minutos.")), 503
    return render_template("lista.html", busqueda=busqueda, pendientes=pendientes, atendidos=atendidos)


@app.post("/atendido/<int:id>")
def atendido(id):
    if not session.get("usuario"):
        return redirect(url_for("entrar"))
    marcar = request.form.get("accion") != "deshacer"
    try:
        with psycopg.connect(**DB) as conexion:
            fila = conexion.execute(
                "UPDATE prerregistros SET atendido = %(marcar)s,"
                " atendido_en = CASE WHEN %(marcar)s THEN now() END WHERE id = %(id)s RETURNING codigo",
                {"marcar": marcar, "id": id}).fetchone()
    except psycopg.OperationalError:
        registro.warning("PostgreSQL de clinica01 no responde")
        return redirect(url_for("inicio"))
    if fila:
        registro.info("%s: %s %s desde %s", "Atendido" if marcar else "Pendiente de nuevo",
                      fila[0], session["usuario"], request.remote_addr)
    return redirect(url_for("inicio", q=request.form.get("q") or None))


@app.get("/salud")
def salud():
    # Solo dice que la app está viva; no toca la base ni AD
    return "ok\n", 200, {"Content-Type": "text/plain"}
