# Consulta de prerregistros en clinica01

Vista del personal clínico para los prerregistros que la gente llena en `https://registro.salud.movil` (R8, D-07). Se entra con el usuario de Samba AD y solo pasa el grupo `clinicos` (R10). Muestra quién está por atender, con su código de turno, y deja marcar a cada persona como atendida. Caddy la publica en `https://consultas.salud.movil` ([`../caddy/`](../caddy/)), al que llega solo la Interna (F-05).

| Archivo | Qué es |
|---|---|
| [`app.py`](app.py) | App en Flask. `GET /entrar` y `POST /entrar` (login), `GET /` (lista y búsqueda), `POST /atendido/<id>` (marcar o deshacer), `POST /salir` y `GET /salud`, que responde `ok` sin tocar la base ni AD |
| [`templates/`](templates/) y [`static/estilo.css`](static/estilo.css) | Páginas en español, sin JavaScript ni recursos externos. En pantalla ancha cada prerregistro es una fila, y en celular una tarjeta |
| [`Dockerfile`](Dockerfile) | `python:3.12.14-slim-bookworm` con usuario sin privilegios (`10001`) y gunicorn con 2 workers, `--preload` y sin socket de control |
| [`requirements.txt`](requirements.txt) | Flask 3.1.3, gunicorn 26.2.0, psycopg 3.3.6 y ldap3 2.9.1 |
| [`compose.yml`](compose.yml) | Imagen `kitsalud/consultas:1` construida en la VM, con la red del host y escuchando solo en `127.0.0.1:8200`. Sistema de archivos de solo lectura, límite de 256 MB, healthcheck, la raíz del kit montada en `/certs/raiz.crt` y el log por journald con la etiqueta `consultas` |
| [`.env.example`](.env.example) | Base (`DB_*`) y Samba AD (`LDAP_*`). El `.env` real lo genera Ansible desde el vault, con permisos `600` |

## Cómo entra el personal

1. La persona escribe su usuario (`ana.rojas`, o `ana.rojas@ad.salud.movil`) y su contraseña del dominio.
2. La app hace *bind* por LDAPS en `dc01.ad.salud.movil:636` con `usuario@ad.salud.movil` y esa contraseña, igual que Grafana, sin cuenta de servicio. Verifica el certificado del DC con la raíz del kit, que es la que firmó el intermedio de clinica01 (D-16).
3. Busca al usuario por `sAMAccountName` y lo deja entrar solo si su `memberOf` incluye `CN=clinicos,CN=Users,DC=ad,DC=salud,DC=movil`.

| Caso | Respuesta |
|---|---|
| Usuario de `clinicos` con su clave | Entra a la lista |
| Usuario del dominio fuera de `clinicos` (por ejemplo `laura.gomez`, de `admins`) | `403`, "Su usuario no tiene acceso a los prerregistros" |
| Usuario o clave errados | `401` con un mensaje que no dice cuál de los dos falló. Samba AD bloquea la cuenta tras 5 intentos durante 15 minutos |
| Clave vacía | `400`. Nunca se hace un *bind* sin clave, que AD aceptaría como anónimo |
| Samba AD no responde | `503` con un aviso |

**Sesión.** Cookie `__Host-consultas` con `Secure`, `HttpOnly` y `SameSite=Strict`, firmada con una llave que se crea al arrancar y no se guarda. Así, reiniciar el contenedor cierra todas las sesiones. Sin actividad en 30 minutos hay que volver a entrar. Todos los `POST` llevan un token CSRF, y una página vieja (de antes de un reinicio) manda de nuevo a la entrada.

## Qué muestra

- **Por atender.** Los prerregistros sin atender, del más antiguo al más nuevo, con código, hora, nombre, documento, edad, motivo, detalle y celular.
- **Atendidos hoy.** Los que se marcaron hoy, del más reciente al más antiguo, con un botón para volverlos a pendientes si fue un error.
- **Buscar.** Por código (sin importar mayúsculas) o por número de documento exacto.

Las horas se muestran en `America/Bogota`. Al marcar, la app guarda `atendido = true` y `atendido_en = now()`; al deshacer, `false` y `NULL`.

## Base de datos

Usa el usuario `consultas` de la base `prerregistro` ([`../dhis2/prerregistro.sql`](../dhis2/prerregistro.sql)), que puede hacer `SELECT` en `prerregistros` y `UPDATE` solo de `atendido` y `atendido_en`. No puede insertar ni borrar. `pg_hba.conf` lo acepta solo desde las IP de clinica01 ([`../dhis2/`](../dhis2/README.md)).

La app se conecta a `10.20.20.11,fd5a:fc7e:d716:20::11` (libpq prueba la IPv4 y después la IPv6) y no a `clinica01.salud.movil`. Con la red del host el contenedor usa el `/etc/hosts` de la VM, que resuelve su propio nombre a `127.0.1.1`, donde no se publica el 5432. La conexión va sin TLS porque no sale de clinica01.

## Registro de accesos

Cada entrada, salida, rechazo y cambio de estado queda en journald con la etiqueta `consultas`, y rsyslog lo reenvía a kit01 (F-15). Ahí se ve en `/var/log/kitsalud/clinica01/syslog.log`.

```
consultas[937]: Entrada: ana.rojas desde 10.20.10.50
consultas[937]: Entrada rechazada: laura.gomez desde 10.20.10.50 (no está en clinicos)
consultas[937]: Atendido: R7P9 ana.rojas desde 10.20.10.50
```

La IP es la del cliente, que Caddy manda en `X-Forwarded-For` (la app confía en un solo proxy, el de `127.0.0.1`).

## Cómo se despliega

Desde `platform/ansible/`, con el rol `consultas` de `apps/ansible/roles/`. El usuario y la base los crea el rol `dhis2`, que va antes en el mismo playbook.

```bash
ansible-playbook playbooks/clinica01.yml    # base, usuario consultas, la app y Caddy
```

El rol copia el código a `/srv/consultas/`, genera `.env` y ejecuta `docker compose up -d --build` si cambió el código o el `.env`. La imagen se construye en la VM, así que la primera vez y cada vez que cambia `requirements.txt` necesita salida a Internet por F-17 (en base, R-05). La clave de `consultas` está en el vault (`vault_consultas_db_password`).

## Cómo se ve desde la máquina propia

```bash
ssh -L 8443:10.20.20.11:443 kitsalud@100.90.225.113
echo '127.0.0.1 consultas.salud.movil' | sudo tee -a /etc/hosts
# después, https://consultas.salud.movil:8443 (la raíz del kit está en http://ca.salud.movil)
```

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En clinica01, `sudo docker ps` | `consultas-app-1` en `healthy` |
| En clinica01, `curl -s 127.0.0.1:8200/salud` | `ok` |
| Desde kit01, `curl -4 --cacert /etc/kitsalud/ca/raiz.crt --resolve consultas.salud.movil:443:10.20.20.11 https://consultas.salud.movil/entrar`, y con `-6` y `[fd5a:fc7e:d716:20::11]` | `200` con la página de entrada y el certificado válido |
| Login con `curl` (token de `/entrar` y `POST /entrar`) como `ana.rojas` | `302` a `/` y la lista con los pendientes |
| El mismo login como `laura.gomez` | `403` y ningún dato |
| `POST /atendido/<id>` y otra vez la lista | El prerregistro pasa a "Atendidos hoy"; con `accion=deshacer` vuelve |
| Un `POST` sin token | `302` a `/entrar?vencida=1` |
| En kit01, `grep consultas /var/log/kitsalud/clinica01/syslog.log` | Las entradas, rechazos y cambios con usuario e IP |
| Desde la Interna (sw01), `/tool fetch url="http://10.20.20.11:443/" keep-result=no` y con `[fd5a:fc7e:d716:20::11]` | `status 400`. Caddy contestó, así que el firewall deja pasar el 443 |
| Desde la Comunidad (`prueba01`), `curl -4` y `curl -6 https://consultas.salud.movil/` | *Timeout* y un `fw-drop` en `/var/log/kitsalud/kit01/firewall.log` (F-20) |
| En Grafana, **Estado del kit** | "Consulta de prerregistros" en verde; con el contenedor detenido, en rojo y la alerta `ServicioCaido` |

## Diagnóstico

- **"El servidor de cuentas no responde".** `sudo docker logs consultas-app-1` muestra el error de `ldap3`. Revisar que Samba esté arriba (`systemctl status samba-ad-dc`), que la VM resuelva `dc01.ad.salud.movil` y que el certificado LDAPS de Samba siga firmado por el intermedio de clinica01 (`echo | openssl s_client -connect dc01.ad.salud.movil:636 -CAfile /etc/kitsalud/tls/raiz.crt`).
- **Un usuario de `clinicos` recibe 403.** `samba-tool group listmembers clinicos`. La app mira la pertenencia directa, no los grupos anidados.
- **Un usuario no puede entrar aunque la clave es correcta.** Puede estar bloqueado por intentos fallidos: `samba-tool user show <usuario>` (`lockoutTime`), o esperar 15 minutos. Los fallos están en `/var/log/kitsalud/clinica01/auth.log` (etiqueta `samba-auth`).
- **"No se pueden leer los prerregistros".** `sudo docker logs consultas-app-1`. Si dice `127.0.1.1`, el `.env` tiene el nombre de la VM en vez de sus IP. Si dice `password authentication failed`, la clave del `.env` y la de la base no coinciden y se alinean con el playbook. Si dice `pg_hba.conf rejects`, el origen no es una IP de clinica01.
- **`502` desde Caddy.** El contenedor no está arriba: `sudo docker compose -f /srv/consultas/compose.yml ps`.
- **Después de un reinicio todos tienen que volver a entrar.** Es lo esperado, porque la llave de la sesión no se guarda.
