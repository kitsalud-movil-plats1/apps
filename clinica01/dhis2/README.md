# DHIS2 en clinica01

Aplicación de pacientes del kit, con cuentas locales para que no dependa de AD (R6, D-06). DHIS2 y PostgreSQL/PostGIS corren en Docker Compose y Caddy los publica por HTTPS en `https://pacientes.salud.movil` ([`../caddy/`](../caddy/)).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `postgis/postgis:16-3.5` (límite 2 GB) y `dhis2/core:2.42.6.0` (límite 4 GB, heap `-Xms1g -Xmx2g`), healthchecks, `restart: unless-stopped` y DHIS2 solo en `127.0.0.1:8080` |
| [`dhis.conf`](dhis.conf) | Conexión a la base con `${DB_*}`, que DHIS2 toma de las variables de entorno, y `server.base.url = https://pacientes.salud.movil` con `server.https = on`. No lleva secretos |
| [`context.xml`](context.xml) | El `context.xml` de Tomcat de la imagen con `RemoteIpValve`, para que DHIS2 respete `X-Forwarded-Proto`, `X-Forwarded-Port` y `X-Forwarded-For` de Caddy. Sin él, DHIS2 redirige a `http://` |
| [`metadatos/kit.json`](metadatos/kit.json) | Metadatos del kit con UID fijos (ver abajo) |
| [`metadatos/pacientes-ficticios.json`](metadatos/pacientes-ficticios.json) | 20 pacientes ficticios (S-09) con su inscripción y una consulta |
| [`.env.example`](.env.example) | Variables que lee Compose (`DATOS`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`). El `.env` real lo genera Ansible desde el vault, con permisos `600` |
| [`prueba-humo/`](prueba-humo/) | `carga.py` y `medir.sh` de la prueba de humo (apps#1) |

## Programa y cuentas

| Elemento | Valor |
|---|---|
| Unidad organizativa | Kit de salud móvil (`KitSalud001`) |
| Tipo de entidad | Paciente, con nombre, apellido, documento (único), fecha de nacimiento y sexo (femenino, masculino u otro) |
| Programa tracker | Atención primaria (`ProgAtenPr1`), con registro y una inscripción por paciente. Los primeros tres atributos son obligatorios |
| Etapa | Consulta, repetible, con motivo de consulta (obligatorio), peso (kg), temperatura (°C) y observaciones |
| Acceso | Los metadatos son de lectura pública para las cuentas. Los datos de pacientes solo los leen y escriben las cuentas del grupo "Personal clínico" (`GrpPersCli1`) |
| Roles | "Personal clínico" (app Capture y dashboard, registrar y actualizar pacientes) y "Administrador" (todas las autoridades) |
| Cuentas | `admin` (superusuario de la imagen), `ana.rojas` y `carlos.perez` con "Personal clínico", `laura.gomez` con "Administrador". Las tres del personal están en el grupo y en la unidad del kit |

Las cuentas son locales de DHIS2 y no dependen de AD; tienen los mismos nombres que en el dominio para que sea fácil saber quién es quién. Las contraseñas están en el vault (`vault_dhis2_admin_password` y `vault_dhis2_usuarios_password`) y siguen la convención del grupo (R-14). La política de DHIS2 exige mayúscula, número y símbolo y rechaza palabras genéricas como `password` o `admin` (`Password must not have any generic word`), así que usa la clave alternativa de la convención.

## Cómo se despliega

Con Ansible, desde `platform/ansible/`. Los roles `docker`, `dhis2` y `caddy` están en `apps/ansible/roles/` y las cuentas en `inventarios/kit/group_vars/all/dhis2.yml`.

```bash
ansible-playbook playbooks/clinica01.yml                          # Docker, DHIS2, su configuración y Caddy
ansible-playbook playbooks/clinica01.yml -e dhis2_estado=stopped  # docker compose down; los datos quedan
```

- **Archivos.** El rol copia `compose.yml`, `dhis.conf` y `context.xml` a `/srv/dhis2/` y genera `.env` con la contraseña de la base. Los datos quedan en `/srv/dhis2/postgres` y `/srv/dhis2/files` (este último del usuario `65534`, con el que corre la imagen). Si cambia `dhis.conf` o `context.xml` el rol reinicia `core`, porque van montados archivo por archivo.
- **Configuración por la API.** Se hace desde la VM contra `127.0.0.1:8080`, después de esperar a que `/api/system/ping` responda. Cada paso solo actúa si hace falta, así que una segunda ejecución termina con `changed=0`.
  - Si `admin` todavía tiene la clave de fábrica, la cambia por la del vault (`PUT /api/me/changePassword`).
  - Importa `kit.json` (`POST /api/metadata`, `CREATE_AND_UPDATE`) si el archivo cambió o si falta el programa (base nueva).
  - Crea las cuentas que falten. La clave solo se pone al crear la cuenta.
  - Le asigna a `admin` la unidad del kit para captura y búsqueda.
  - Carga los pacientes ficticios si falta `PacFict0001`.

Docker y Compose vienen de los paquetes de Ubuntu (`docker.io` 29.1.3 y `docker-compose-v2` 2.40.3), retenidos con `hold`. Las imágenes se descargan por F-17 (las VMs salen a Internet por 80 y 443, solo IPv4).

## Cómo se accede

Desde la Interna, en `https://pacientes.salud.movil` (F-05). El certificado lo firma la CA local de Caddy en clinica01, así que el navegador muestra una advertencia hasta instalar la raíz (apps#3 la unifica y la publica). La app para registrar pacientes es **Capture**.

Desde la máquina propia, con un túnel a través de kit01 y una línea en `/etc/hosts`. DHIS2 conserva el puerto del túnel en sus redirecciones.

```bash
ssh -J kitsalud@100.90.225.113 -L 8443:127.0.0.1:443 kitsalud@10.20.20.11
echo '127.0.0.1 pacientes.salud.movil' | sudo tee -a /etc/hosts
# después, https://pacientes.salud.movil:8443
```

## Prueba de humo (R-03)

Resultados completos en apps#1. Con 5 usuarios registrando 2000 pacientes a la vez, DHIS2 llegó a 1,66 GiB y PostgreSQL a 322 MiB. En reposo usan 1,51 GiB y 137 MiB. El primer arranque tarda 57 s y un reinicio con datos 25 s.

Los datos de esa prueba (2220 pacientes y la cuenta de fábrica) se apartaron en `/srv/dhis2-prueba-humo/` al instalar la versión del kit, que arranca con la base vacía. Para repetirla hay que hacerlo en una instancia aparte, porque usa la cuenta de fábrica.

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
| `curl -s -o /dev/null -w '%{http_code}' -u admin:district http://127.0.0.1:8080/api/me` | `401` (la clave de fábrica ya no sirve) |
| `curl -gs -u admin:<clave> 'http://127.0.0.1:8080/api/tracker/trackedEntities?program=ProgAtenPr1&orgUnits=KitSalud001&pageSize=1&totalPages=true'` | `pager.total` de 20 o más |
| Desde la Interna, `curl -4` y `curl -6 --cacert <raíz> https://pacientes.salud.movil/` | `302` hacia `https://pacientes.salud.movil/dhis-web-login/` |
| Como `ana.rojas`, `POST /api/tracker?async=false` con un paciente y `GET /api/tracker/trackedEntities?...&filter=AtrDocumen1:eq:<documento>` (P6) | `status OK` y el paciente con `createdBy` `ana.rojas` |
| `cd /srv/dhis2 && sudo docker compose down && sudo docker compose up -d` y otra vez el conteo | El mismo número de pacientes |
| `sudo docker stats --no-stream` | Memoria de cada contenedor dentro de su límite |
| `stat -c '%a' /srv/dhis2/.env` | `600` |

## Diagnóstico

- **`core` se queda en `health: starting`.** El primer arranque tarda alrededor de un minuto y el healthcheck espera hasta 10 minutos. `sudo docker logs -f dhis2-core-1` muestra el avance hasta `Server startup in`.
- **`core` no conecta con la base.** Revisar que `.env` tenga `DB_PASSWORD` y que `db` esté `healthy`. Si se cambió la contraseña después de crear la base, PostgreSQL conserva la anterior; hay que cambiarla también dentro de la base.
- **No descarga las imágenes.** Revisar la salida a Internet de las VMs (F-17) y el DNS (`resolvectl query registry-1.docker.io`).
- **`files` sin permisos.** `/srv/dhis2/files` tiene que ser del usuario `65534`.
- **Después del login el navegador va a `http://` o pierde el puerto del túnel.** Falta el `RemoteIpValve` (`sudo docker exec dhis2-core-1 cat /usr/local/tomcat/conf/context.xml`) o Caddy no manda `X-Forwarded-Port`.
- **La API responde `409` al crear una cuenta o cambiar una clave.** El mensaje dice qué regla de la política falla, por ejemplo `Password must not have any generic word`. Se prueba una clave con `curl -u admin:<clave> -X POST http://127.0.0.1:8080/api/account/validatePassword --data-urlencode password=<clave nueva>`.
- **`curl` falla con `fields=...[...]`.** Los corchetes los interpreta `curl`; se usa `curl -g`.
- **Un usuario no ve pacientes en Capture.** Tiene que estar en el grupo "Personal clínico" y en la unidad del kit para captura y búsqueda (`/api/users/<id>?fields=userGroups,organisationUnits,teiSearchOrganisationUnits`).
