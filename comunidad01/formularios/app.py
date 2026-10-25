"""Formularios de prerregistro del kit de salud (R8, D-07, apps#6).

La persona llena unos pocos datos desde su celular, o el personal la ayuda.
La app solo puede insertar en PostgreSQL de clinica01 (usuario formularios),
así que nunca muestra ni guarda en comunidad01 lo que otras personas
registraron. A cada prerregistro le da un código corto para que el personal
la llame por él.
"""
import os
import re
import secrets
from datetime import date

import psycopg
from flask import Flask, render_template, request

app = Flask(__name__)

DB = {
    "host": os.environ.get("DB_HOST", "clinica01.salud.movil"),
    "port": int(os.environ.get("DB_PORT", "5432")),
    "dbname": os.environ.get("DB_NAME", "prerregistro"),
    "user": os.environ.get("DB_USER", "formularios"),
    "password": os.environ.get("DB_PASSWORD", ""),
    # Si la base no responde, la persona recibe el aviso enseguida
    "connect_timeout": 3,
}

TIPOS_DOCUMENTO = [
    ("CC", "Cédula de ciudadanía"),
    ("TI", "Tarjeta de identidad"),
    ("RC", "Registro civil"),
    ("CE", "Cédula de extranjería"),
    ("OTRO", "Otro documento"),
    ("NINGUNO", "No tengo documento"),
]
MOTIVOS = [
    ("CONTROL", "Control o revisión"),
    ("FIEBRE", "Fiebre o malestar"),
    ("DOLOR", "Dolor"),
    ("EMBARAZO", "Embarazo"),
    ("VACUNACION", "Vacunación"),
    ("OTRO", "Otro motivo"),
]
# Sin letras ni números que se confundan al decirlos en voz alta (0/O, 1/I, 5/S...)
ALFABETO_CODIGO = "ACDEFGHJKMNPRTUVWXY34679"


@app.after_request
def cabeceras(respuesta):
    respuesta.headers["Content-Security-Policy"] = "default-src 'self'; form-action 'self'; frame-ancestors 'none'"
    respuesta.headers["X-Content-Type-Options"] = "nosniff"
    respuesta.headers["Referrer-Policy"] = "no-referrer"
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


def validar(f):
    """Devuelve (datos, errores) a partir del formulario."""
    errores = {}
    d = {k: (f.get(k) or "").strip() for k in (
        "nombres", "apellidos", "tipo_documento", "numero_documento",
        "fecha_nacimiento", "celular", "motivo", "detalle")}
    d["autoriza_datos"] = f.get("autoriza_datos") == "si"

    for campo, nombre in (("nombres", "su nombre"), ("apellidos", "sus apellidos")):
        if not d[campo]:
            errores[campo] = f"Escriba {nombre}."
        elif len(d[campo]) > 80:
            errores[campo] = "Es demasiado largo."
    if d["tipo_documento"] not in dict(TIPOS_DOCUMENTO):
        errores["tipo_documento"] = "Elija el tipo de documento."
    elif d["tipo_documento"] != "NINGUNO":
        if not re.fullmatch(r"[0-9A-Za-z-]{3,20}", d["numero_documento"]):
            errores["numero_documento"] = "Escriba el número del documento, sin puntos ni espacios."
    else:
        d["numero_documento"] = ""
    if d["fecha_nacimiento"]:
        try:
            nacimiento = date.fromisoformat(d["fecha_nacimiento"])
            if not date(1900, 1, 1) <= nacimiento <= date.today():
                raise ValueError
        except ValueError:
            errores["fecha_nacimiento"] = "Revise la fecha de nacimiento."
    d["celular"] = re.sub(r"[\s-]", "", d["celular"])
    if d["celular"] and not re.fullmatch(r"[0-9]{7,15}", d["celular"]):
        errores["celular"] = "Escriba solo los números del celular."
    if d["motivo"] not in dict(MOTIVOS):
        errores["motivo"] = "Elija el motivo de la consulta."
    if len(d["detalle"]) > 200:
        errores["detalle"] = "Escriba algo más corto (máximo 200 letras)."
    if not d["autoriza_datos"]:
        errores["autoriza_datos"] = "Para registrarse tiene que autorizar el uso de sus datos."
    return d, errores


def guardar(d):
    codigo = "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(4))
    with psycopg.connect(**DB) as conexion:
        conexion.execute(
            "INSERT INTO prerregistros (codigo, nombres, apellidos, tipo_documento, numero_documento,"
            " fecha_nacimiento, celular, motivo, detalle, autoriza_datos)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (codigo, d["nombres"], d["apellidos"], d["tipo_documento"], d["numero_documento"] or None,
             d["fecha_nacimiento"] or None, d["celular"] or None, d["motivo"], d["detalle"] or None,
             d["autoriza_datos"]),
        )
    return codigo


def formulario(datos=None, errores=None, aviso=None, estado=200):
    return render_template(
        "formulario.html", datos=datos or {}, errores=errores or {}, aviso=aviso,
        tipos=TIPOS_DOCUMENTO, motivos=MOTIVOS, hoy=date.today().isoformat(),
    ), estado


@app.get("/")
def inicio():
    return formulario()


@app.post("/")
def enviar():
    datos, errores = validar(request.form)
    if errores:
        return formulario(datos, errores, estado=400)
    try:
        codigo = guardar(datos)
    except psycopg.OperationalError:
        # La base de clinica01 no responde: se avisa y se conserva lo escrito.
        # La próxima vez que la persona envíe, la app vuelve a intentar.
        app.logger.warning("PostgreSQL de clinica01 no responde")
        return formulario(datos, aviso=(
            "En este momento no pudimos guardar sus datos. Espere unos minutos y vuelva a "
            "tocar Enviar, o pida ayuda al personal de salud."), estado=503)
    return render_template("gracias.html", codigo=codigo, nombres=datos["nombres"])


@app.get("/salud")
def salud():
    # Solo dice que la app está viva; no toca la base
    return "ok\n", 200, {"Content-Type": "text/plain"}
