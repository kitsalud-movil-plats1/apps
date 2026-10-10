# DHIS2 en clinica01

DHIS2 con PostgreSQL/PostGIS en Docker Compose (D-06, sección 10.1 del documento). Hoy está la versión de la prueba de humo (apps#1); la instalación con Caddy, cuentas y respaldo llega en apps#2.

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `postgis/postgis:16-3.5` (límite 2 GB) y `dhis2/core:2.42.6.0` (límite 4 GB, heap `-Xms1g -Xmx2g`), healthchecks, `restart: unless-stopped` y DHIS2 solo en `127.0.0.1:8080` |
| [`dhis.conf`](dhis.conf) | Conexión a la base con `${DB_*}`, que DHIS2 toma de las variables de entorno; no lleva secretos |
| [`.env.example`](.env.example) | Variables que lee Compose (`DATOS`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`). El `.env` real lo genera Ansible desde el vault, con permisos `600` |
| [`prueba-humo/`](prueba-humo/) | `carga.py` (programa tracker mínimo y pacientes ficticios por API) y `medir.sh` (muestras de `docker stats`) |

## Cómo se despliega

Con Ansible, desde `platform/ansible/`. Los roles `docker` y `dhis2` están en `apps/ansible/roles/`.

```bash
ansible-playbook playbooks/clinica01.yml                        # instala Docker y levanta DHIS2
ansible-playbook playbooks/clinica01.yml -e dhis2_estado=stopped  # docker compose down; los datos quedan
```

El rol copia `compose.yml` y `dhis.conf` a `/srv/dhis2/` (disco de datos de la VM), genera `.env` con la contraseña de la base (`vault_dhis2_db_password`) y deja los datos en `/srv/dhis2/postgres` y `/srv/dhis2/files` (este último del usuario `65534`, con el que corre la imagen).

Docker y Compose vienen de los paquetes de Ubuntu (`docker.io` 29.1.3 y `docker-compose-v2` 2.40.3), retenidos con `hold`. Las imágenes se descargan por F-17 (las VMs salen a Internet por 80 y 443, solo IPv4).

## Cómo se accede

DHIS2 solo escucha en la VM. Para verlo desde la máquina propia se abre un túnel a través de kit01.

```bash
ssh -J kitsalud@100.90.225.113 -L 8080:127.0.0.1:8080 kitsalud@10.20.20.11
# después, http://localhost:8080
```

La cuenta de fábrica de DHIS2 es `admin` con la contraseña `district`. Solo se usa en la prueba de humo; en apps#2 se cambia y se crean las cuentas individuales.

## Prueba de humo (R-03)

Resultados completos en apps#1. Con 5 usuarios registrando 2000 pacientes a la vez, DHIS2 llegó a 1,66 GiB y PostgreSQL a 322 MiB. En reposo usan 1,51 GiB y 137 MiB. El primer arranque tarda 57 s y un reinicio con datos 25 s.

Para repetirla en clinica01, con DHIS2 levantado:

```bash
sudo ./medir.sh > muestras.csv &                 # muestras cada 5 s (INTERVALO para cambiarlo)
python3 carga.py                                 # crea los metadatos, 200 pacientes y 50 búsquedas
for u in 1 2 3 4 5; do SIN_METADATOS=1 PACIENTES=400 BUSQUEDAS=100 python3 carga.py & done; wait
kill %1
```

## Cómo se verifica

| Comando (en clinica01) | Resultado esperado |
|---|---|
| `sudo docker compose -f /srv/dhis2/compose.yml ps` | `dhis2-db-1` y `dhis2-core-1` en `healthy` |
| `curl -s -u <usuario>:<clave> http://127.0.0.1:8080/api/system/info` | JSON con `"version":"2.42.6"` |
| `sudo docker stats --no-stream` | Memoria de cada contenedor dentro de su límite |
| `stat -c '%a' /srv/dhis2/.env` | `600` |

## Diagnóstico

- **`core` se queda en `health: starting`.** El primer arranque tarda alrededor de un minuto y el healthcheck espera hasta 10 minutos. `sudo docker logs -f dhis2-core-1` muestra el avance hasta `Server startup in`.
- **`core` no conecta con la base.** Revisar que `.env` tenga `DB_PASSWORD` y que `db` esté `healthy`. Si se cambió la contraseña después de crear la base, PostgreSQL conserva la anterior; hay que cambiarla también dentro de la base.
- **No descarga las imágenes.** Revisar la salida a Internet de las VMs (F-17) y el DNS (`resolvectl query registry-1.docker.io`).
- **`files` sin permisos.** `/srv/dhis2/files` tiene que ser del usuario `65534`.
