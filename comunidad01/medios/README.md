# Carpeta de medios de comunidad01

`/srv/medios/` guarda lo que sirven Kiwix y Jellyfin. Lo que sube el personal llega desde el recurso SMB `contenido` de clinica01 por la publicación (R9, sección 10.5, F-12), que corre en clinica01 ([`platform/clinica01/publicacion/`](https://github.com/kitsalud-movil-plats1/platform/tree/main/clinica01/publicacion)). Lo prepara el rol `publicacion_destino` de [`../../ansible/roles/`](../../ansible/roles/), que se aplica con `playbooks/publicacion.yml` de `platform/ansible`.

| Carpeta | Qué guarda | Dueño |
|---|---|---|
| `zim/` | ZIM de la biblioteca (módulo `zim`). Kiwix sirve todos los `*.zim` | `publicacion` |
| `videos/salud/` y `videos/comunidad/` | Bibliotecas de Jellyfin (módulo `videos`). Lo publicado y los medios del rol `jellyfin` | `publicacion` (los medios del rol son de `root`) |
| `originales/` | Originales que el rol `jellyfin` convierte a 480p, fuera de las bibliotecas | `root` |

Los roles `kiwix` y `jellyfin` crean `zim/` y las carpetas de las bibliotecas sin fijar el dueño, y `publicacion_destino` se las da a `publicacion`. Así ningún rol cambia lo que dejó el otro.

## Quién puede escribir y cómo

| Elemento | Valor |
|---|---|
| Usuario | `publicacion`, de sistema, sin contraseña (`!`), con `/bin/sh` para que sshd ejecute el comando forzado. Su home es `/etc/kitsalud/publicacion`, de root, donde no puede escribir |
| Llave autorizada | `/etc/ssh/publicacion/authorized_keys`, de root, con la llave pública de clinica01 y `command="rsync --server --daemon --config=/etc/kitsalud/publicacion/rsyncd.conf .",restrict,from="10.20.20.11,fd5a:fc7e:d716:20::11"` |
| sshd | `/etc/ssh/sshd_config.d/20-publicacion.conf`. Desde las IP de clinica01 solo entra `publicacion` (`AllowUsers`). `publicacion` solo entra con su llave, con el mismo comando forzado, sin PTY, túneles ni reenvíos |
| ufw | `22/tcp` desde `10.20.20.11` y `fd5a:fc7e:d716:20::11` (comentario `publicacion`, F-12), además del SSH de kit01 |
| Demonio de rsync | `/etc/kitsalud/publicacion/rsyncd.conf`. Lo lanza sshd por cada conexión y corre como `publicacion`. Sin chroot y con `munge symlinks`, así que un enlace simbólico que llegue no apunta a nada. Módulos `write only` (no se puede leer nada) y `list = no`. Lo que llega queda con `644` y las carpetas con `755`, legibles para Jellyfin y Kiwix. Registra en syslog con la etiqueta `publicacion`, que llega al log central de kit01 |
| Protección de los medios del rol | El módulo `videos` excluye lo que anota el rol `jellyfin` en `/srv/jellyfin/medios-del-rol.txt` y su temporal `.preparando.mp4`. Un archivo excluido por el demonio no se recibe ni se borra, así que `--delete` no lo toca |

comunidad01 no tiene credenciales hacia clinica01 para este flujo. No guarda llaves ni claves SMB, y ufw en clinica01 solo deja entrar el 22 desde kit01 y el 445 desde la Interna. La única credencial de comunidad01 hacia clinica01 es el usuario `formularios` de PostgreSQL, que solo puede hacer `INSERT` (F-11, D-07).

## Reindexado

- **Kiwix.** `kiwix-serve` lee los ZIM al arrancar. `kiwix-recarga.path` (rol `kiwix`) vigila `/srv/medios/zim` y, cuando algo cambia, `kiwix-recarga.service` espera 30 s y reinicia el contenedor. Con `kiwix_estado=stopped` la vigilancia se apaga, para no volver a levantarlo.
- **Jellyfin.** Las bibliotecas tienen el monitor de cambios activo (`EnableRealtimeMonitor`), así que un archivo nuevo o borrado aparece o desaparece solo.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| `ls -ld /srv/medios/zim /srv/medios/videos/*` | `zim`, `salud` y `comunidad` de `publicacion` |
| `sudo sshd -T -C user=publicacion,host=x,addr=10.20.20.11 \| grep -E 'forcecommand\|permittty\|authenticationmethods'` | El comando de rsync, `permittty no` y `publickey` |
| `sudo sshd -T -C user=kitsalud,host=x,addr=10.20.20.11 \| grep allowusers` | `allowusers publicacion` |
| `sudo ufw status \| grep publicacion` | El 22 desde las dos IP de clinica01 |
| `systemctl is-active kiwix-recarga.path` | `active` |
| `journalctl -t publicacion` | `connect from clinica01.salud.movil` y una línea por archivo recibido o borrado |
| `journalctl -u kiwix-recarga` | `Restarting` y `Started` unos 30 s después de cada cambio en los ZIM |

## Diagnóstico

- **`daemon refused to receive file` en el log.** El archivo tiene el nombre de un medio del rol `jellyfin` en esa biblioteca. Se renombra en `contenido`.
- **Un ZIM nuevo no aparece en la biblioteca.** `systemctl status kiwix-recarga.path kiwix-recarga.service`. Se puede reiniciar a mano con `sudo systemctl start kiwix-recarga.service`.
- **`Permission denied` al recibir.** La carpeta del módulo no es de `publicacion`. Se vuelve a ejecutar `playbooks/publicacion.yml`.
- **La conexión se cierra sin errores en clinica01.** `journalctl -u ssh` en comunidad01. `not listed in AllowUsers` significa que se intentó entrar con otro usuario desde clinica01.
