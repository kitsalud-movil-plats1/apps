# DHIS2 en clinica01

Aplicación de pacientes del kit, con cuentas locales para que no dependa de AD (R6, D-06). DHIS2 y PostgreSQL/PostGIS corren en Docker Compose y Caddy los publica por HTTPS en `https://pacientes.salud.movil` ([`../caddy/`](../caddy/)).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `postgis/postgis:16-3.5` (límite 2 GB) y `dhis2/core:2.42.6.0` (límite 4 GB, heap `-Xms1g -Xmx2g`), healthchecks, `restart: unless-stopped` y DHIS2 solo en `127.0.0.1:8080`. PostgreSQL publica el 5432 solo en `10.20.20.11` y `[fd5a:fc7e:d716:20::11]` para los formularios y usa el `pg_hba.conf` que genera el rol. La red de Docker tiene subredes fijas (`172.30.0.0/24` y `fdc4:5a1d:7e20:1::/64`) con IPv6, así el 5432 publicado conserva la IP de origen en las dos familias |
| [`dhis.conf`](dhis.conf) | Conexión a la base con `${DB_*}`, que DHIS2 toma de las variables de entorno, y `server.base.url = https://pacientes.salud.movil` con `server.https = on`. No lleva secretos |
| [`prerregistro.sql`](prerregistro.sql) | Base `prerregistro` de los formularios (apps#6): tabla `prerregistros`, dueño `prerregistro_dueno` sin login, usuario `formularios` con solo `INSERT` y usuario `consultas` (apps#7) que lee y solo cambia `atendido` y `atendido_en`. Idempotente |
| [`context.xml`](context.xml) | El `context.xml` de Tomcat de la imagen con `RemoteIpValve`, para que DHIS2 respete `X-Forwarded-Proto`, `X-Forwarded-Port` y `X-Forwarded-For` de Caddy. Sin él, DHIS2 redirige a `http://` |
| [`metadatos/kit.json`](metadatos/kit.json) | Metadatos del kit con UID fijos (ver abajo) |
| [`metadatos/pacientes-ficticios.json`](metadatos/pacientes-ficticios.json) | 20 pacientes ficticios (S-09) con su inscripción y una consulta |
| [`metadatos/pacientes-demostracion.json`](metadatos/pacientes-demostracion.json) | 200 pacientes ficticios de demostración (`PacDemo0001` a `PacDemo0200`, documentos `DEMO-0001`…) con 300 consultas entre el 21 de septiembre y el 27 de octubre de 2026, para el dashboard de la brigada (apps#12) |
| [`metadatos/generar-demostracion.py`](metadatos/generar-demostracion.py) | Genera el archivo anterior con una semilla fija; ejecutarlo otra vez da el mismo archivo. No corre en la VM |
| [`metadatos/brigada.json`](metadatos/brigada.json) | Indicadores de programa, visualizaciones, la lista de consultas y el dashboard "Brigada de salud", con UID fijos (ver abajo) |
| [`.env.example`](.env.example) | Variables que lee Compose (`DATOS`, `DB_*`, las subredes `RED4`/`RED6` y las IP de publicación `IP4`/`IP6`). El `.env` real lo genera Ansible desde el inventario y el vault, con permisos `600` |
| [`prueba-humo/`](prueba-humo/) | `carga.py` y `medir.sh` de la prueba de humo (apps#1) |

## Programa y cuentas

| Elemento | Valor |
|---|---|
| Unidad organizativa | Kit de salud móvil (`KitSalud001`) |
| Tipo de entidad | Paciente, con nombre, apellido, documento (único), fecha de nacimiento y sexo (femenino, masculino u otro) |
| Programa tracker | Atención primaria (`ProgAtenPr1`), con registro y una inscripción por paciente. Los primeros tres atributos son obligatorios |
| Etapa | Consulta, repetible, con motivo principal (opcional, con las mismas opciones del prerregistro: control o revisión, fiebre o malestar, dolor, embarazo, vacunación u otro), motivo de consulta (texto, obligatorio), peso (kg), temperatura (°C) y observaciones |
| Acceso | Los metadatos son de lectura pública para las cuentas. Los datos de pacientes solo los leen y escriben las cuentas del grupo "Personal clínico" (`GrpPersCli1`) |
| Roles | "Personal clínico" (apps Capture, Dashboard, Data Visualizer y Line Listing, registrar y actualizar pacientes, y ver la analítica de eventos) y "Administrador" (todas las autoridades) |
| Cuentas | `admin` (superusuario de la imagen), `ana.rojas` y `carlos.perez` con "Personal clínico", `laura.gomez` con "Administrador". Las tres del personal están en el grupo y en la unidad del kit. `kit.json` define el grupo sin miembros, así que cada importación lo vacía y el rol vuelve a meter a cada cuenta |

Las cuentas son locales de DHIS2 y no dependen de AD; tienen los mismos nombres que en el dominio para que sea fácil saber quién es quién. Las contraseñas están en el vault (`vault_dhis2_admin_password` y `vault_dhis2_usuarios_password`) y siguen la convención del grupo (R-14). La política de DHIS2 exige mayúscula, número y símbolo y rechaza palabras genéricas como `password` o `admin` (`Password must not have any generic word`), así que usa la clave alternativa de la convención.

## PostgreSQL y los formularios

La misma instancia de PostgreSQL guarda DHIS2 y los prerregistros de los formularios de comunidad01 (D-07, F-11), en bases separadas. La consulta de prerregistros ([`../consultas/`](../consultas/)) los lee desde la propia clinica01. `pg_hba.conf` (plantilla `pg_hba.conf.j2` del rol) rechaza todo lo que no está en esta tabla.

| Base | Usuario | Desde | Para qué |
|---|---|---|---|
| `dhis2` | `dhis` | Red de Docker de DHIS2 | DHIS2 |
| `prerregistro` | `formularios` | Solo comunidad01 (`10.20.20.12/32` y `fd5a:fc7e:d716:20::12/128`) | Insertar prerregistros. No puede leer, cambiar ni borrar |
| `prerregistro` | `consultas` | Solo clinica01 (`10.20.20.11/32` y `fd5a:fc7e:d716:20::11/128`), porque la consulta usa la red del host | Leer los prerregistros y marcar `atendido` y `atendido_en`. No puede insertar ni borrar |
| Todas | Todos | Socket local del contenedor | `docker exec` y el healthcheck |

El 5432 publicado por Docker no pasa por ufw. Lo protegen `pg_hba.conf`, los permisos de cada usuario y kit01, que no deja llegar a la Interna ni a la Comunidad al 5432; el filtro entre VMs en el bridge llega con network#10. Los prerregistros guardan la hora en UTC (`timestamptz`).

## Cómo se despliega

Con Ansible, desde `platform/ansible/`. Los roles `docker`, `dhis2` y `caddy` están en `apps/ansible/roles/` y las cuentas en `inventarios/kit/group_vars/all/dhis2.yml`.

```bash
ansible-playbook playbooks/clinica01.yml                          # Docker, DHIS2, su configuración y Caddy
ansible-playbook playbooks/clinica01.yml -e dhis2_estado=stopped  # docker compose down; los datos quedan
```

- **Archivos.** El rol copia `compose.yml`, `dhis.conf` y `context.xml` a `/srv/dhis2/` y genera `.env` con la contraseña de la base. Los datos quedan en `/srv/dhis2/postgres` y `/srv/dhis2/files` (este último del usuario `65534`, con el que corre la imagen). Si cambia `dhis.conf` o `context.xml` el rol reinicia `core`, porque van montados archivo por archivo. Si cambia `pg_hba.conf` reinicia `db` y espera a que `/api/me` responda con la clave de `admin`, porque `/api/system/ping` no toca la base y mientras DHIS2 recupera sus conexiones responde `401` a todo.
- **Configuración por la API.** Se hace desde la VM contra `127.0.0.1:8080`, después de esperar a que `/api/system/ping` responda. Cada paso solo actúa si hace falta, así que una segunda ejecución termina con `changed=0`.
  - Si `admin` todavía tiene la clave de fábrica, la cambia por la del vault (`PUT /api/me/changePassword`).
  - Importa `kit.json` (`POST /api/metadata`, `CREATE_AND_UPDATE`) si el archivo cambió o si falta el programa (base nueva).
  - Crea las cuentas que falten. La clave solo se pone al crear la cuenta.
  - Le asigna a `admin` la unidad del kit para captura y búsqueda.
  - Vuelve a meter a cada cuenta del personal en el grupo "Personal clínico" si no está.
  - Carga los pacientes ficticios si falta `PacFict0001`, y los de demostración si falta `PacDemo0001` (`atomicMode=ALL`, todo o nada).
  - Importa `brigada.json` si el archivo cambió o si falta el indicador `PiAtenTot01`.
  - Crea el trabajo de las tablas analíticas (`TrabAnalit1`) si falta, o lo actualiza si cambiaron su intervalo o sus parámetros.
  - Crea la base `prerregistro`, su tabla y sus roles con `prerregistro.sql` si el archivo cambió o falta la base. Las claves de `formularios` y `consultas` salen del vault (`vault_formularios_db_password` y `vault_consultas_db_password`).
- **Cambio de la red de Docker.** Si cambian las subredes, Compose no puede recrear la red con los contenedores encima: antes hay que `docker compose down` en `/srv/dhis2` (los datos quedan).

Docker y Compose vienen de los paquetes de Ubuntu (`docker.io` 29.1.3 y `docker-compose-v2` 2.40.3), retenidos con `hold`. Las imágenes se descargan por F-17 (las VMs salen a Internet por 80 y 443, solo IPv4).

## Dashboard de la brigada (apps#12)

El dashboard **Brigada de salud** muestra cómo va la jornada. Lo ve el grupo "Personal clínico" desde la app Dashboard, y todos sus elementos se pueden abrir en Data Visualizer o Line Listing.

| Elemento | Tipo | Periodo |
|---|---|---|
| Atenciones esta semana | Cifra | Esta semana |
| Consultas con fiebre esta semana | Cifra | Esta semana |
| Atenciones por sexo | Torta | Últimas 12 semanas y la actual |
| Atenciones por día | Columnas | Últimos 14 días y hoy |
| Atenciones y pacientes nuevos por semana | Líneas | Últimas 12 semanas y la actual |
| Motivos de consulta | Barras | Últimas 12 semanas y la actual |
| Atenciones por edad | Columnas | Últimas 12 semanas y la actual |
| Últimas consultas | Lista (fecha, nombre, apellido, motivo principal, motivo y temperatura) | Últimos 14 días y hoy, de la más reciente a la más antigua |

Los periodos relativos de DHIS2 no incluyen el periodo en curso (`LAST_12_WEEKS` no trae esta semana y `LAST_14_DAYS` no trae hoy), así que cada visualización suma `thisWeek` o `today`.

**Indicadores de programa.** Todos son de tipo `EVENT` y cuentan consultas (`V{event_count}`), salvo "Pacientes nuevos", que es `ENROLLMENT` y cuenta inscripciones. Cada uno lleva sus límites de periodo (`analyticsPeriodBoundaries`) por la fecha de la consulta o de la inscripción.

| Indicador | Filtro |
|---|---|
| Atenciones (`PiAtenTot01`) | Ninguno |
| Pacientes nuevos (`PiPacNuev01`) | Ninguno |
| Consultas con fiebre (`PiFiebre001`) | Temperatura de 38 °C o más |
| Atenciones de mujeres, hombres y otro sexo (`PiSexo*`) | Atributo sexo |
| Atenciones de 0 a 4, 5 a 14, 15 a 49 y 50 años o más (`PiEdad*`) | `d2:yearsBetween` entre la fecha de nacimiento y la de la consulta |
| Motivo: control o revisión, fiebre o malestar, dolor, embarazo, vacunación u otro (`PiMot*`) | Motivo principal |

**Tablas analíticas (R-03).** El trabajo **Tablas analíticas de la brigada** (`TrabAnalit1`, `CONTINUOUS_ANALYTICS_TABLE`) recalcula el periodo más reciente cada 30 minutos y todas las tablas a las 2:00, así que el dashboard va como mucho media hora atrás. Usa `skipOutliers: true` porque el kit no tiene datos agregados. Con 221 pacientes y 321 consultas, la generación completa tardó 4,6 s y dejó a `core` en 1861 MiB de 4096 y a `db` en 140 MiB de 2048. Una pasada del trabajo continuo tardó 3,9 s con picos de 1900 y 165 MiB. Bajo demanda se generan desde la app Data Administration o con `POST /api/resourceTables/analytics`.

## Cómo se accede

Desde la Interna, en `https://pacientes.salud.movil` (F-05). El certificado lo firma la CA del kit; para que el navegador no muestre la advertencia se instala la raíz desde `http://ca.salud.movil`. La app para registrar pacientes es **Capture**.

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
| `curl -gs -u admin:<clave> 'http://127.0.0.1:8080/api/tracker/trackedEntities?program=ProgAtenPr1&orgUnits=KitSalud001&pageSize=1&totalPages=true'` | `pager.total` de 220 o más |
| `curl -gs -u admin:<clave> 'http://127.0.0.1:8080/api/users?filter=username:eq:ana.rojas&fields=userGroups[name]'` | `Personal clínico` |
| Como `ana.rojas`, `GET /api/analytics?dimension=dx:PiAtenTot01;PiFiebre001;PiPacNuev01&filter=pe:2026&filter=ou:KitSalud001` y el mismo conteo por `/api/tracker/trackedEntities` | Las mismas cifras (los 16 indicadores coinciden) |
| Como `ana.rojas`, `GET /api/analytics/events/query/ProgAtenPr1?stage=EtapaConsu1&dimension=pe:LAST_14_DAYS&dimension=ou:KitSalud001&dimension=AtrNombre01&desc=eventdate` | Las consultas de las últimas dos semanas |
| `ana.rojas` registra una consulta hoy, `POST /api/jobConfigurations/TrabAnalit1/execute` y `GET /api/analytics?dimension=dx:PiAtenTot01&filter=pe:TODAY&filter=ou:KitSalud001` | Sube en 1 |
| En `https://pacientes.salud.movil`, como `ana.rojas`, la app Dashboard | **Brigada de salud** con sus 8 elementos y datos |
| Desde la Interna, `curl -4` y `curl -6 --cacert <raíz> https://pacientes.salud.movil/` | `302` hacia `https://pacientes.salud.movil/dhis-web-login/` |
| Como `ana.rojas`, `POST /api/tracker?async=false` con un paciente y `GET /api/tracker/trackedEntities?...&filter=AtrDocumen1:eq:<documento>` (P6) | `status OK` y el paciente con `createdBy` `ana.rojas` |
| `cd /srv/dhis2 && sudo docker compose down && sudo docker compose up -d` y otra vez el conteo | El mismo número de pacientes |
| `sudo docker exec dhis2-db-1 psql -U dhis -d prerregistro -c '\dp prerregistros'` | `formularios=a/prerregistro_dueno` y `consultas=r/prerregistro_dueno`, con `atendido` y `atendido_en` en `consultas=w` por columna |
| En clinica01, `sudo docker run --rm -it --network host postgis/postgis:16-3.5 psql "host=10.20.20.11 dbname=prerregistro user=consultas"` (y con `fd5a:fc7e:d716:20::11`) con `SELECT`, `UPDATE` de `atendido` (con `ROLLBACK`), `INSERT`, `UPDATE` de otra columna y `DELETE` | El `SELECT` y el `UPDATE` de `atendido` funcionan; los otros dan `permission denied`. `inet_client_addr()` es la IP de clinica01 |
| Desde comunidad01, el mismo `psql` con `user=consultas` | `pg_hba.conf rejects connection for host "10.20.20.12"` |
| Desde comunidad01, `psql "host=10.20.20.11 dbname=prerregistro user=formularios"` (y con `fd5a:fc7e:d716:20::11`) e `INSERT`, `SELECT` y `DELETE` | Solo el `INSERT` funciona; los otros dan `permission denied` |
| Desde comunidad01, `psql "host=10.20.20.11 dbname=dhis2 user=dhis"` | `pg_hba.conf rejects connection for host "10.20.20.12"` |
| `sudo docker stats --no-stream` | Memoria de cada contenedor dentro de su límite |
| `stat -c '%a' /srv/dhis2/.env` | `600` |

## Diagnóstico

- **`core` se queda en `health: starting`.** El primer arranque tarda alrededor de un minuto y el healthcheck espera hasta 10 minutos. `sudo docker logs -f dhis2-core-1` muestra el avance hasta `Server startup in`.
- **`core` no conecta con la base.** Revisar que `.env` tenga `DB_PASSWORD` y que `db` esté `healthy`. Si se cambió la contraseña después de crear la base, PostgreSQL conserva la anterior; hay que cambiarla también dentro de la base.
- **No descarga las imágenes.** Revisar la salida a Internet de las VMs (F-17) y el DNS (`resolvectl query registry-1.docker.io`).
- **`no pg_hba.conf entry` o `pg_hba.conf rejects connection`.** El origen, la base o el usuario no están en `pg_hba.conf`. `sudo docker exec dhis2-db-1 psql -U dhis -d dhis2 -c 'select * from pg_hba_file_rules'` muestra las reglas cargadas.
- **El 5432 por IPv6 llega con la IP de la red de Docker.** La red no tiene IPv6 (`docker network inspect dhis2_default`) y Docker usa su proxy, que cambia el origen.
- **El rol falla al cambiar la clave de fábrica de `admin` con `401` justo después de reiniciar `db`.** DHIS2 todavía no había recuperado sus conexiones. El rol ya espera a `/api/me`; si pasa igual, se vuelve a ejecutar el playbook.
- **Un indicador de consultas sale vacío y el log de `core` dice `bad SQL grammar [... where and ...]`.** Al indicador le faltan los `analyticsPeriodBoundaries`, que la interfaz agrega sola y la API no. Están en `brigada.json`.
- **El dashboard dice que el usuario no puede ver la analítica de eventos (`User is not allowed to view event analytics data`).** Al rol le falta `F_VIEW_EVENT_ANALYTICS`.
- **`ana.rojas` o `carlos.perez` no pueden leer datos del programa (`not allowed to read data for Program`).** No están en el grupo "Personal clínico". Una importación de `kit.json` vacía el grupo; se vuelve a ejecutar el playbook.
- **El trabajo de las tablas analíticas termina en milisegundos y el log dice `job parameters not aligned with existing outlier data`.** `skipOutliers` del trabajo no coincide con el de la última generación. El rol lo deja en `true`, que coincide con `POST /api/resourceTables/analytics` sin parámetros.
- **El dashboard no muestra lo de hoy.** El trabajo continuo corre cada 30 minutos (`GET /api/jobConfigurations/TrabAnalit1?fields=lastExecuted,lastExecutedStatus`). Para no esperar, se ejecuta a mano.
- **`files` sin permisos.** `/srv/dhis2/files` tiene que ser del usuario `65534`.
- **Después del login el navegador va a `http://` o pierde el puerto del túnel.** Falta el `RemoteIpValve` (`sudo docker exec dhis2-core-1 cat /usr/local/tomcat/conf/context.xml`) o Caddy no manda `X-Forwarded-Port`.
- **La API responde `409` al crear una cuenta o cambiar una clave.** El mensaje dice qué regla de la política falla, por ejemplo `Password must not have any generic word`. Se prueba una clave con `curl -u admin:<clave> -X POST http://127.0.0.1:8080/api/account/validatePassword --data-urlencode password=<clave nueva>`.
- **`curl` falla con `fields=...[...]`.** Los corchetes los interpreta `curl`; se usa `curl -g`.
- **Un usuario no ve pacientes en Capture.** Tiene que estar en el grupo "Personal clínico" y en la unidad del kit para captura y búsqueda (`/api/users/<id>?fields=userGroups,organisationUnits,teiSearchOrganisationUnits`).
