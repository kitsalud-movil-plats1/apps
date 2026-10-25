# Caddy en comunidad01

Proxy inverso de comunidad01 (D-16). Publica el contenido de la comunidad por nombre y, más adelante, el registro por HTTPS con la CA interna (apps#3).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `caddy:2.11.7` con la red del host (`network_mode: host`), límite de 256 MB y `restart: unless-stopped`. Monta la carpeta `conf/` y no el archivo, para que una recarga vea el Caddyfile nuevo |
| [`Caddyfile`](Caddyfile) | Un bloque por nombre de servicio |

| Nombre | Destino | Protocolo |
|---|---|---|
| `biblioteca.salud.movil` | Kiwix en `127.0.0.1:8090` | HTTP |

Caddy usa la red del host para escuchar en IPv4 e IPv6 y ver la IP real del cliente en el log de acceso (`log`, a la salida del contenedor). Los servicios quedan publicados solo en `127.0.0.1`. La API de administración de Caddy escucha solo en `127.0.0.1:2019`.

## Cómo se despliega

Con el rol `caddy` de `apps/ansible/roles/`, desde `platform/ansible/` (`ansible-playbook playbooks/comunidad01.yml`). El rol deja todo en `/srv/caddy/` (`compose.yml`, `conf/Caddyfile`, `data/` y `config/`), recarga Caddy cuando cambia el Caddyfile y abre en ufw el 80 desde la Interna y la Comunidad, en las dos familias. En kit01 la Interna llega por F-07 y la Comunidad llegará por F-09 cuando el portal la autorice (network#8).

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En comunidad01, `curl -s -o /dev/null -w '%{http_code}' -H 'Host: biblioteca.salud.movil' http://127.0.0.1/` y con `http://[::1]/` | `200` |
| `sudo ss -tlnp \| grep caddy` | `*:80` y `127.0.0.1:2019` |
| `sudo ufw status \| grep 80` | `10.20.10.0/24`, `fd5a:fc7e:d716:10::/64`, `10.20.40.0/24` y `fd5a:fc7e:d716:40::/64` |
| Desde sw01, `/tool fetch url="http://10.20.20.12/" http-header-field="Host: biblioteca.salud.movil" output=user` y con `http://[fd5a:fc7e:d716:20::12]/` | `status: finished` |
| `sudo docker logs caddy-caddy-1 2>&1 \| tail -1` | Una línea JSON por petición, con `remote_ip` del cliente |

## Cómo se ve desde la máquina propia

Con un túnel a través de kit01 hasta el 80 de comunidad01. El nombre tiene que llegar en la cabecera `Host`, así que se agrega una línea a `/etc/hosts` de la máquina propia.

```bash
ssh -J kitsalud@100.90.225.113 -L 8080:127.0.0.1:80 kitsalud@10.20.20.12
echo '127.0.0.1 biblioteca.salud.movil' | sudo tee -a /etc/hosts
# después, http://biblioteca.salud.movil:8080
```

## Diagnóstico

- **Respuesta vacía con `200`.** El nombre no coincide con ningún bloque del Caddyfile. Revisar la cabecera `Host` y el DNS (`dig biblioteca.salud.movil`).
- **No responde desde la Interna.** En kit01, `sudo nft list chain inet filtro forward | grep 'dport 80'` (el contador sube) y `journalctl -k | grep fw-drop`; en comunidad01, `sudo ufw status`.
- **Un cambio del Caddyfile no se aplica.** `sudo docker compose -f /srv/caddy/compose.yml exec caddy caddy validate --config /etc/caddy/Caddyfile` y `sudo docker logs caddy-caddy-1`.
