#!/usr/bin/env python3
"""Prueba de humo de DHIS2 (apps#1, R-03).

Crea por la API un programa tracker mínimo (unidad organizativa, tipo
"Paciente" con nombre, apellido y documento, programa con una etapa
"Consulta") y registra pacientes ficticios con su inscripción y una consulta.
Después hace búsquedas por atributo. Solo usa la biblioteca estándar.

Variables de entorno: DHIS2_URL (por defecto http://127.0.0.1:8080),
DHIS2_USUARIO y DHIS2_CLAVE (por defecto la cuenta de fábrica, que solo
existe en la prueba de humo), PACIENTES (200), LOTE (20), BUSQUEDAS (50) y
SIN_METADATOS=1 para solo registrar y buscar (varios procesos a la vez).
"""
import base64
import json
import os
import random
import time
import urllib.error
import urllib.request

URL = os.environ.get("DHIS2_URL", "http://127.0.0.1:8080")
USUARIO = os.environ.get("DHIS2_USUARIO", "admin")
CLAVE = os.environ.get("DHIS2_CLAVE", "district")
PACIENTES = int(os.environ.get("PACIENTES", "200"))
LOTE = int(os.environ.get("LOTE", "20"))
BUSQUEDAS = int(os.environ.get("BUSQUEDAS", "50"))

# UID fijos (11 caracteres, empiezan por letra) para que la carga de metadatos sea repetible
OU = "KitSalud001"
TEA_NOMBRE, TEA_APELLIDO, TEA_DOCUMENTO = "AtrNombre01", "AtrApellid1", "AtrDocumen1"
TET = "TipoPacien1"
PROGRAMA = "ProgAtenPr1"
ETAPA = "EtapaConsu1"

AUTH = "Basic " + base64.b64encode(f"{USUARIO}:{CLAVE}".encode()).decode()


def api(metodo, ruta, cuerpo=None):
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(URL + ruta, data=datos, method=metodo)
    req.add_header("Authorization", AUTH)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            texto = r.read().decode()
            return r.status, json.loads(texto) if texto else {}
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def metadatos():
    atributo = lambda uid, nombre, unico=False: {
        "id": uid, "name": nombre, "shortName": nombre, "valueType": "TEXT",
        "aggregationType": "NONE", "unique": unico,
    }
    publico = {"public": "rwrw----"}
    carga = {
        "organisationUnits": [{"id": OU, "name": "Kit de salud móvil", "shortName": "Kit de salud", "openingDate": "2026-01-01"}],
        "trackedEntityAttributes": [
            atributo(TEA_NOMBRE, "Nombre"),
            atributo(TEA_APELLIDO, "Apellido"),
            atributo(TEA_DOCUMENTO, "Documento", unico=True),
        ],
        "trackedEntityTypes": [{
            "id": TET, "name": "Paciente", "shortName": "Paciente", "sharing": publico,
            "trackedEntityTypeAttributes": [
                {"trackedEntityAttribute": {"id": a}, "searchable": True, "displayInList": True}
                for a in (TEA_NOMBRE, TEA_APELLIDO, TEA_DOCUMENTO)
            ],
        }],
        "programs": [{
            "id": PROGRAMA, "name": "Atención primaria", "shortName": "Atención primaria",
            "programType": "WITH_REGISTRATION", "trackedEntityType": {"id": TET},
            "organisationUnits": [{"id": OU}], "sharing": publico,
            "programTrackedEntityAttributes": [
                {"trackedEntityAttribute": {"id": a}, "searchable": True, "displayInList": True, "mandatory": a == TEA_DOCUMENTO}
                for a in (TEA_NOMBRE, TEA_APELLIDO, TEA_DOCUMENTO)
            ],
            "programStages": [{"id": ETAPA}],
        }],
        "programStages": [{"id": ETAPA, "name": "Consulta", "program": {"id": PROGRAMA}, "sharing": publico}],
    }
    codigo, r = api("POST", "/api/metadata?importStrategy=CREATE_AND_UPDATE&atomicMode=ALL&importReportMode=ERRORS", carga)
    informe = r.get("response", r)
    print(f"metadatos: HTTP {codigo}, estado {informe.get('status')}, {informe.get('stats')}")
    for tipo in informe.get("typeReports", []):
        for objeto in tipo.get("objectReports", []):
            for error in objeto.get("errorReports", []):
                print(f"  error en {tipo['klass'].split('.')[-1]}: {error.get('errorCode')} {error.get('message')}")
    if codigo != 200:
        raise SystemExit("La carga de metadatos falló; no se registran pacientes")

    # La cuenta de prueba captura y busca en la unidad del kit
    _, yo = api("GET", "/api/me?fields=id")
    for coleccion in ("organisationUnits", "teiSearchOrganisationUnits", "dataViewOrganisationUnits"):
        api("POST", f"/api/users/{yo['id']}/{coleccion}/{OU}")


NOMBRES = ["Ana", "Luis", "María", "Jorge", "Sofía", "Carlos", "Lucía", "Andrés", "Valentina", "Diego"]
APELLIDOS = ["Gómez", "Rodríguez", "López", "Martínez", "García", "Pérez", "Sánchez", "Ramírez", "Torres", "Díaz"]


def paciente(n):
    hoy = time.strftime("%Y-%m-%d")
    return {
        "trackedEntityType": TET, "orgUnit": OU,
        "attributes": [
            {"attribute": TEA_NOMBRE, "value": random.choice(NOMBRES)},
            {"attribute": TEA_APELLIDO, "value": random.choice(APELLIDOS)},
            {"attribute": TEA_DOCUMENTO, "value": f"PRUEBA-{os.getpid()}-{int(time.time())}-{n:05d}"},
        ],
        "enrollments": [{
            "program": PROGRAMA, "orgUnit": OU, "enrolledAt": hoy, "occurredAt": hoy, "status": "ACTIVE",
            "events": [{"programStage": ETAPA, "orgUnit": OU, "occurredAt": hoy, "status": "COMPLETED"}],
        }],
    }


def registrar():
    tiempos, creados = [], 0
    for inicio in range(0, PACIENTES, LOTE):
        lote = [paciente(n) for n in range(inicio, min(inicio + LOTE, PACIENTES))]
        t = time.time()
        codigo, r = api("POST", "/api/tracker?async=false", {"trackedEntities": lote})
        tiempos.append(time.time() - t)
        estado = r.get("status")
        if codigo != 200 or estado != "OK":
            print(f"lote {inicio}: HTTP {codigo}, {estado}, {json.dumps(r.get('validationReport', r))[:400]}")
            continue
        creados += r.get("stats", {}).get("created", 0)
    print(f"registro: {PACIENTES} pacientes en lotes de {LOTE}; objetos creados {creados}; "
          f"lote promedio {sum(tiempos) / len(tiempos):.2f} s, máximo {max(tiempos):.2f} s")


def buscar():
    tiempos, encontrados = [], 0
    for _ in range(BUSQUEDAS):
        apellido = random.choice(APELLIDOS)
        t = time.time()
        _, r = api("GET", f"/api/tracker/trackedEntities?program={PROGRAMA}&orgUnits={OU}"
                          f"&filter={TEA_APELLIDO}:eq:{urllib.request.quote(apellido)}&pageSize=50")
        tiempos.append(time.time() - t)
        encontrados += len(r.get("trackedEntities", r.get("instances", [])))
    print(f"búsquedas: {BUSQUEDAS} por apellido; promedio {sum(tiempos) / len(tiempos):.2f} s, "
          f"máximo {max(tiempos):.2f} s; resultados {encontrados}")


if __name__ == "__main__":
    if os.environ.get("SIN_METADATOS") != "1":
        metadatos()
    registrar()
    buscar()
