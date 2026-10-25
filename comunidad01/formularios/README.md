# Formularios de prerregistro en comunidad01

Prerregistro mínimo y asistido para la sala de espera (R8, D-07). La persona llena unos pocos datos desde su celular, o el personal la ayuda, y recibe un código corto con el que la llaman. Los datos se guardan en PostgreSQL de clinica01 con un usuario que solo puede insertar, así que comunidad01 nunca guarda ni puede leer los prerregistros. Caddy lo publica en `https://registro.salud.movil` ([`../caddy/`](../caddy/)).

| Archivo | Qué es |
|---|---|
| [`app.py`](app.py) | App en Flask. `GET /` muestra el formulario, `POST /` valida y guarda, `GET /salud` responde `ok` sin tocar la base |
| [`templates/`](templates/) y [`static/estilo.css`](static/estilo.css) | Páginas en lenguaje simple, sin JavaScript ni recursos externos, con botones grandes |
| [`Dockerfile`](Dockerfile) | `python:3.12.14-slim-bookworm` con usuario sin privilegios (`10001`) y gunicorn con 2 workers |
| [`requirements.txt`](requirements.txt) | Flask 3.1.3, gunicorn 26.2.0 y psycopg 3.3.6 |
| [`compose.yml`](compose.yml) | Imagen `kitsalud/formularios:1` construida en la VM, solo en `127.0.0.1:8100`, sistema de archivos de solo lectura, límite de 256 MB y healthcheck |
| [`.env.example`](.env.example) | `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` y `DB_PASSWORD`. El `.env` real lo genera Ansible desde el vault, con permisos `600` |

## Datos que pide

| Campo | Obligatorio | Validación |
|---|---|---|
| Nombres y apellidos | Sí | Hasta 80 caracteres cada uno |
| Tipo de documento | Sí | CC, TI, RC, CE, otro o "no tengo documento" |
| Número de documento | Si tiene documento | Letras, números y guiones, de 3 a 20 |
| Fecha de nacimiento | No | Entre 1900 y hoy |
| Celular | No | De 7 a 15 dígitos |
| Motivo | Sí | Control, fiebre o malestar, dolor, embarazo, vacunación u otro |
| Detalle | No | Hasta 200 caracteres |
| Autorización de datos | Sí | Texto breve según la Ley 1581 de 2012 |

La tabla `prerregistros` de clinica01 repite estas reglas con `CHECK` ([`../../clinica01/dhis2/prerregistro.sql`](../../clinica01/dhis2/prerregistro.sql)) y tiene la columna `atendido`, que marca el personal desde la consulta (apps#7).

**Código de turno.** Cuatro caracteres al azar de un alfabeto sin letras ni números que se confundan al decirlos (por ejemplo `R7P9`). La app lo genera, lo guarda en la fila y lo muestra; no necesita leer la base para eso.

**Sin base.** Si PostgreSQL de clinica01 no responde en 3 segundos, la app responde `503` con un aviso en lenguaje simple, conserva lo que la persona escribió y lo registra en su log (`PostgreSQL de clinica01 no responde`). Cada envío abre su propia conexión, así que la app se recupera sola cuando la base vuelve.

## Cómo se despliega

Desde `platform/ansible/`, con el rol `formularios` de `apps/ansible/roles/`. La base y el usuario los crea el rol `dhis2` en clinica01 (`playbooks/clinica01.yml`), así que ese playbook va primero.

```bash
ansible-playbook playbooks/clinica01.yml    # base prerregistro y usuario formularios
ansible-playbook playbooks/comunidad01.yml  # app, Caddy y el 443 en ufw
```

El rol copia el código a `/srv/formularios/`, genera `.env` y ejecuta `docker compose up -d --build` si cambió el código o el `.env`. La imagen se construye en la VM, así que necesita salida a Internet por F-17 (en base, R-05) la primera vez y cada vez que cambia `requirements.txt`.

## Cómo se ve desde la máquina propia

```bash
ssh -J kitsalud@100.90.225.113 -L 8443:127.0.0.1:443 kitsalud@10.20.20.12
echo '127.0.0.1 registro.salud.movil' | sudo tee -a /etc/hosts
# después, https://registro.salud.movil:8443 (la raíz del kit está en http://ca.salud.movil)
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En comunidad01, `sudo docker ps` | `formularios-app-1` en `healthy` |
| `curl --cacert /srv/caddy/pki/raiz.crt --resolve registro.salud.movil:443:10.20.20.12 https://registro.salud.movil/` y con `[fd5a:fc7e:d716:20::12]` | `200` con el formulario |
| Un `POST` con los campos obligatorios | `200` con el código de turno, y la fila en `prerregistros` de clinica01 |
| Un `POST` vacío | `400` con un mensaje por cada campo que falta |
| `sudo docker stop dhis2-db-1` en clinica01, un `POST`, `sudo docker start dhis2-db-1` y otro `POST` | `503` con el aviso y lo escrito conservado; después `200` sin reiniciar la app |
| Desde la Interna, `curl -4` y `curl -6 --cacert raiz.crt https://registro.salud.movil/` | `200` |
| Desde la Comunidad, el mismo `curl` | Bloqueado hasta que el portal autorice al cliente (F-09, network#8) |

## Diagnóstico

- **Siempre muestra el aviso de que no se pudo guardar.** `sudo docker logs formularios-app-1`. Si dice que PostgreSQL no responde, revisar desde comunidad01 `nc -zv clinica01.salud.movil 5432` y en clinica01 `pg_hba.conf` (`../../clinica01/dhis2/README.md`).
- **`password authentication failed for user "formularios"`.** La clave del `.env` y la de la base no coinciden; se vuelven a alinear con los dos playbooks.
- **`502` desde Caddy.** El contenedor no está arriba: `sudo docker compose -f /srv/formularios/compose.yml ps`.
- **La construcción falla.** La VM no llega a PyPI o a Docker Hub (F-17).
