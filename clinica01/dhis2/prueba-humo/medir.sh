#!/bin/sh
# Muestra el consumo de los contenedores de DHIS2 cada INTERVALO segundos
# (por defecto 5) hasta que se interrumpe. Uso: medir.sh > muestras.csv
INTERVALO=${INTERVALO:-5}
echo "hora,contenedor,memoria,cpu"
while :; do
  docker stats --no-stream --format '{{.Name}},{{.MemUsage}},{{.CPUPerc}}' dhis2-core-1 dhis2-db-1 |
    sed "s/^/$(date +%T),/"
  sleep "$INTERVALO"
done
