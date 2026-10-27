# Caddy en clinica01

Proxy inverso de clinica01 (D-16). Todo lo de clinica01 maneja datos de pacientes o del personal, así que va por HTTPS con `tls internal`, firmado por el intermedio de clinica01 de la CA del kit ([`platform/kit01/ca/`](../../../platform/kit01/ca/README.md)).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `caddy:2.11.7` con la red del host, límite de 256 MB y `restart: unless-stopped`, y `pki/` montada en `/pki` (raíz e intermedio). Igual que el de comunidad01 |
| [`Caddyfile`](Caddyfile) | `skip_install_trust`, `default_sni pacientes.salud.movil`, la CA `local` con la raíz (solo el certificado) y el intermedio de la VM, y un bloque por servicio |

| Nombre | Destino | Protocolo |
|---|---|---|
| `pacientes.salud.movil` | DHIS2 en `127.0.0.1:8080` | HTTPS (`tls internal`); el 80 redirige a HTTPS |
| `consultas.salud.movil` | Consulta de prerregistros en `127.0.0.1:8200` ([`../consultas/`](../consultas/)) | HTTPS (`tls internal`) |

- **CA.** Caddy firma certificados de 12 horas, que renueva solo, con el intermedio de clinica01 (`/srv/caddy/pki/intermedio.crt` y `.key`), que solo vale para `pacientes`, `consultas` y `archivos`. La raíz está en `/srv/caddy/pki/raiz.crt` sin su llave, que solo vive en kit01. La raíz se instala en los equipos desde `http://ca.salud.movil`.
- **`default_sni`.** Un cliente que llega por IP no manda SNI (por ejemplo `/tool fetch` de sw01); así igual recibe el certificado de `pacientes`.
- **Cabeceras.** Caddy manda `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Forwarded-Port`. DHIS2 las respeta por su `context.xml` ([`../dhis2/`](../dhis2/)) y la consulta por `ProxyFix`.

## Cómo se despliega

Con el rol `caddy` de `apps/ansible/roles/` desde `platform/ansible/` (`ansible-playbook playbooks/clinica01.yml`). El rol toma los archivos de `apps/<vm>/caddy/` y abre en ufw los puertos de `caddy_puertos` desde `caddy_origenes`, que en clinica01 son el 443 desde la Interna en las dos familias (`inventarios/kit/host_vars/clinica01.yml`, F-05). El 80 no se abre.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En clinica01, `curl -s --cacert /srv/caddy/pki/raiz.crt --resolve pacientes.salud.movil:443:10.20.20.11 -o /dev/null -w '%{http_code} %{redirect_url}' https://pacientes.salud.movil/` y con `[fd5a:fc7e:d716:20::11]` | `302 https://pacientes.salud.movil/dhis-web-login/` |
| Lo mismo con `consultas.salud.movil` y la ruta `/entrar` | `200` |
| `echo \| openssl s_client -connect 10.20.20.11:443 -servername pacientes.salud.movil -CAfile /srv/caddy/pki/raiz.crt` | Cadena hoja → `Kit de salud movil - clinica01` → `Kit de salud movil - Raiz` y `Verify return code: 0 (ok)` |
| `sudo ufw status \| grep 443` | `10.20.10.0/24` y `fd5a:fc7e:d716:10::/64` |
| Desde sw01, `/tool fetch url="http://10.20.20.11:443/" keep-result=no` y con `[fd5a:fc7e:d716:20::11]` | `Fetch failed with status 400`. Caddy contestó en el 443, así que la Interna llega. Por HTTPS, `/tool fetch` de RouterOS 7.13 no completa el handshake con este Caddy (`ssl: decode error`; ver `contexto/problemas-conocidos.md` en `workspace`) |

## Diagnóstico

- **`curl: (60) SSL certificate problem`.** Falta `--cacert` con la raíz del kit o se usa una raíz vieja. La de `http://ca.salud.movil/raiz.crt` es la buena.
- **Error de TLS al entrar por IP.** El cliente no manda SNI y falta `default_sni`.
- **`502`.** DHIS2 no está arriba (`sudo docker compose -f /srv/dhis2/compose.yml ps`).
