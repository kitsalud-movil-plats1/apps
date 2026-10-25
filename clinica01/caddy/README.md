# Caddy en clinica01

Proxy inverso de clinica01 (D-16). Todo lo de clinica01 maneja datos de pacientes o del personal, así que va por HTTPS con la CA interna de Caddy (`tls internal`).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `caddy:2.11.7` con la red del host, límite de 256 MB y `restart: unless-stopped`. Igual que el de comunidad01 |
| [`Caddyfile`](Caddyfile) | `skip_install_trust`, `default_sni pacientes.salud.movil` y un bloque por servicio |

| Nombre | Destino | Protocolo |
|---|---|---|
| `pacientes.salud.movil` | DHIS2 en `127.0.0.1:8080` | HTTPS (`tls internal`); el 80 redirige a HTTPS |

- **CA.** Caddy crea su raíz local en `/srv/caddy/data/caddy/pki/authorities/local/` (`root.crt`, válida 10 años) y firma con un intermedio de 7 días certificados de 12 horas que renueva solo. La llave privada no sale de la VM. apps#3 la reemplaza por una raíz compartida con comunidad01 y la publica.
- **`default_sni`.** Un cliente que llega por IP no manda SNI (por ejemplo `/tool fetch` de sw01); así igual recibe el certificado de `pacientes`.
- **Cabeceras.** Caddy manda `X-Forwarded-For`, `X-Forwarded-Proto` y `X-Forwarded-Port`, y DHIS2 las respeta por su `context.xml` ([`../dhis2/`](../dhis2/)).

## Cómo se despliega

Con el rol `caddy` de `apps/ansible/roles/` desde `platform/ansible/` (`ansible-playbook playbooks/clinica01.yml`). El rol toma los archivos de `apps/<vm>/caddy/` y abre en ufw los puertos de `caddy_puertos` desde `caddy_origenes`, que en clinica01 son el 443 desde la Interna en las dos familias (`inventarios/kit/host_vars/clinica01.yml`, F-05). El 80 no se abre.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En clinica01, `curl -s --cacert /srv/caddy/data/caddy/pki/authorities/local/root.crt --resolve pacientes.salud.movil:443:10.20.20.11 -o /dev/null -w '%{http_code} %{redirect_url}' https://pacientes.salud.movil/` y con `[fd5a:fc7e:d716:20::11]` | `302 https://pacientes.salud.movil/dhis-web-login/` |
| `echo \| openssl s_client -connect 10.20.20.11:443 -servername pacientes.salud.movil 2>/dev/null \| openssl x509 -noout -issuer` | `CN = Caddy Local Authority - ECC Intermediate` |
| `sudo ufw status \| grep 443` | `10.20.10.0/24` y `fd5a:fc7e:d716:10::/64` |
| Desde sw01, `/tool fetch url="https://10.20.20.11/dhis-web-login/" http-header-field="Host: pacientes.salud.movil" check-certificate=no output=user` y con `[fd5a:fc7e:d716:20::11]` | `status: finished` |

## Diagnóstico

- **`curl: (60) SSL certificate problem`.** Falta `--cacert` con la raíz de clinica01, o se usa la de otra VM.
- **Error de TLS al entrar por IP.** El cliente no manda SNI y falta `default_sni`.
- **`502`.** DHIS2 no está arriba (`sudo docker compose -f /srv/dhis2/compose.yml ps`).
