#!/usr/bin/env python3
"""Genera pacientes-demostracion.json (apps#12, S-09).

200 pacientes ficticios con 1 a 4 consultas de lunes a sábado entre el 21 de
septiembre y el 27 de octubre de 2026, para que el dashboard "Brigada de
salud" de DHIS2 tenga varias semanas de datos. La semilla es fija: ejecutarlo
otra vez produce el mismo archivo. Ansible carga el JSON; este script no corre
en la VM.

Uso: python3 generar-demostracion.py > pacientes-demostracion.json
"""
import json
import random
from datetime import date, timedelta

INICIO = date(2026, 9, 21)
FIN = date(2026, 10, 27)
PACIENTES = 200
r = random.Random(2026)

NOMBRES_F = ["María", "Luz", "Ana", "Carmen", "Rosa", "Diana", "Sandra", "Paola", "Lucía", "Valentina",
             "Sofía", "Isabella", "Camila", "Gloria", "Marta", "Juliana", "Natalia", "Laura", "Andrea", "Yolanda"]
NOMBRES_M = ["José", "Luis", "Carlos", "Jorge", "Andrés", "Juan", "Miguel", "Pedro", "Santiago", "Mateo",
             "Samuel", "Diego", "Javier", "Óscar", "Fabio", "Hernán", "Alejandro", "Felipe", "Daniel", "Julián"]
APELLIDOS = ["García", "Rodríguez", "Martínez", "López", "González", "Hernández", "Pérez", "Sánchez", "Ramírez",
             "Torres", "Flórez", "Rivera", "Gómez", "Díaz", "Moreno", "Muñoz", "Rojas", "Vargas", "Castro",
             "Ortiz", "Mosquera", "Valencia", "Cuesta", "Palacios", "Caicedo", "Hurtado", "Asprilla", "Murillo"]
# Grupos de edad del dashboard: 0-4, 5-14, 15-49 y 50 o más
EDADES = [((0, 4), 15), ((5, 14), 15), ((15, 49), 45), ((50, 85), 25)]
DETALLES = {
    "CONTROL": ["Control de presión arterial", "Control de crecimiento y desarrollo", "Revisión de resultados",
                "Control de diabetes", "Control después de tratamiento"],
    "FIEBRE": ["Fiebre desde hace dos días", "Fiebre y dolor de cabeza", "Fiebre y tos", "Malestar general y escalofrío"],
    "DOLOR": ["Dolor abdominal", "Dolor de cabeza", "Dolor de espalda", "Dolor de oído", "Dolor de garganta"],
    "EMBARAZO": ["Control prenatal", "Control prenatal, segundo trimestre", "Náuseas en el embarazo"],
    "VACUNACION": ["Vacunas del esquema", "Refuerzo de vacuna", "Vacuna de influenza"],
    "OTRO": ["Herida en la mano", "Picadura de insecto", "Diarrea", "Tos sin fiebre", "Erupción en la piel"],
}


def dias_habiles():
    d, dias = INICIO, []
    while d <= FIN:
        if d.weekday() < 6:  # sin domingos
            dias.append(d)
        d += timedelta(days=1)
    return dias


def elegir(pesos):
    return r.choices(list(pesos), weights=list(pesos.values()))[0]


def motivo(edad, sexo, primera):
    if not primera and r.random() < 0.6:
        return "CONTROL"
    pesos = {"CONTROL": 25, "FIEBRE": 25, "DOLOR": 20, "OTRO": 10,
             "VACUNACION": 25 if edad < 15 else 4,
             "EMBARAZO": 20 if sexo == "F" and 15 <= edad <= 45 else 0}
    return elegir(pesos)


def peso(edad):
    if edad < 1:
        return round(r.uniform(4, 9), 1)
    if edad < 15:
        return round(edad * 2.5 + 8 + r.uniform(-2, 3), 1)
    return round(r.uniform(48, 88), 1)


def temperatura(motivo_principal):
    if motivo_principal == "FIEBRE":
        return round(r.uniform(38.0, 39.6) if r.random() < 0.75 else r.uniform(37.3, 37.9), 1)
    return round(r.uniform(36.0, 37.2), 1)


def paciente(n, dias):
    sexo = elegir({"F": 55, "M": 44, "O": 1})
    nombre = r.choice(NOMBRES_M if sexo == "M" else NOMBRES_F)
    (minimo, maximo) = r.choices([e for e, _ in EDADES], weights=[p for _, p in EDADES])[0]
    edad = r.randint(minimo, maximo)
    nacimiento = INICIO - timedelta(days=edad * 365 + r.randint(0, 364))

    # Primera consulta en cualquier día; las siguientes, de 3 a 14 días después
    fechas = [r.choice(dias)]
    for _ in range(elegir({0: 50, 1: 30, 2: 15, 3: 5})):
        siguiente = fechas[-1] + timedelta(days=r.randint(3, 14))
        if siguiente.weekday() == 6:
            siguiente += timedelta(days=1)
        if siguiente > FIN:
            break
        fechas.append(siguiente)

    eventos = []
    for i, fecha in enumerate(fechas):
        edad_consulta = (fecha - nacimiento).days // 365
        m = motivo(edad_consulta, sexo, i == 0)
        eventos.append({
            "event": f"EvtDemo{len(EVENTOS) + 1:04d}",
            "programStage": "EtapaConsu1",
            "orgUnit": "KitSalud001",
            "occurredAt": fecha.isoformat(),
            "status": "COMPLETED",
            "dataValues": [
                {"dataElement": "DeMotivoPr1", "value": m},
                {"dataElement": "DeMotivoCo1", "value": r.choice(DETALLES[m])},
                {"dataElement": "DePesoKg001", "value": str(peso(edad_consulta))},
                {"dataElement": "DeTempera01", "value": str(temperatura(m))},
            ],
        })
        EVENTOS.append(eventos[-1])

    return {
        "trackedEntity": f"PacDemo{n:04d}",
        "trackedEntityType": "TipoPacien1",
        "orgUnit": "KitSalud001",
        "attributes": [
            {"attribute": "AtrNombre01", "value": nombre},
            {"attribute": "AtrApellid1", "value": f"{r.choice(APELLIDOS)} {r.choice(APELLIDOS)}"},
            {"attribute": "AtrDocumen1", "value": f"DEMO-{n:04d}"},
            {"attribute": "AtrFechaNa1", "value": nacimiento.isoformat()},
            {"attribute": "AtrSexoPac1", "value": sexo},
        ],
        "enrollments": [{
            "enrollment": f"InsDemo{n:04d}",
            "program": "ProgAtenPr1",
            "orgUnit": "KitSalud001",
            "enrolledAt": fechas[0].isoformat(),
            "occurredAt": fechas[0].isoformat(),
            "status": "ACTIVE",
            "events": eventos,
        }],
    }


EVENTOS = []
dias = dias_habiles()
datos = {"trackedEntities": [paciente(n, dias) for n in range(1, PACIENTES + 1)]}
print(json.dumps(datos, ensure_ascii=False, indent=1))
