# Jellyfin en comunidad01

Audio y video para la sala de espera (R7, D-08, sección 10.5). Hay dos bibliotecas: **Salud**, con contenido médico general, y **Comunidad**, con material educativo y para niños. La comunidad entra con el usuario `comunidad` y la contraseña vacía. Todo se reproduce directo, sin transcodificar, y la administración solo se puede hacer desde la Interna y por NetBird. Caddy lo publica en `http://videos.salud.movil` ([`../caddy/`](../caddy/)).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `jellyfin/jellyfin:12.3.20261023-013714` con la red del host, usuario `10020`, `config/` y `cache/` en `/srv/jellyfin`, `/srv/medios/videos` en `/media` de solo lectura y límite de 1 GB |

El rol `jellyfin` de `apps/ansible/roles/` hace el resto por la API local (`127.0.0.1:8096`). Cada paso solo actúa si hace falta.

## Red

| Ajuste | Valor | Por qué |
|---|---|---|
| Dirección de escucha | `127.0.0.1:8096` | Solo Caddy llega a Jellyfin |
| Proxy de confianza | `127.0.0.1` | Jellyfin toma la IP del cliente de `X-Forwarded-For`. Caddy la reemplaza siempre, así que un cliente no la puede falsear |
| Redes locales | La Interna (`10.20.10.0/24` y `fd5a:fc7e:d716:10::/64`) y kit01 (`10.20.20.1`, `.10`, `::1` y `::10`) | kit01 es el origen de la administración por NetBird con túnel (D-18) |
| Acceso remoto | Activado | La Comunidad llega enrutada, sin NAT, con su IP `10.20.40.x`, y para Jellyfin es remota |
| Descubrimiento y UPnP | Apagados | No escucha en el UDP 7359 ni abre puertos en el router |

## Bibliotecas y cuentas

| Biblioteca | Carpeta | Tipo |
|---|---|---|
| Salud | `/srv/medios/videos/salud` | `mixed` (audio y video) |
| Comunidad | `/srv/medios/videos/comunidad` | `mixed` |

Las bibliotecas no buscan metadatos ni imágenes en Internet (C-03) y no extraen capítulos ni miniaturas, que cargarían la CPU. El título de cada ítem sale del nombre del archivo, o de las etiquetas en los MP3.

| Cuenta | Contraseña | Política |
|---|---|---|
| `admin` | En el vault (`vault_jellyfin_admin_password`), según la convención del grupo (R-14) | Administrador, oculta en la pantalla de entrada y sin acceso remoto, así que solo entra desde las redes locales |
| `comunidad` | Vacía | Visible en la pantalla de entrada: se toca «comunidad» y después «Iniciar sesión», sin escribir nada. Solo reproduce: sin transcodificación de video ni de audio, sin remux, sin descargas, sin borrar y sin cambiar preferencias |

La pantalla de entrada no tiene Quick Connect ni «Contraseña olvidada», que no sirven en el kit (Quick Connect está apagado en el servidor y el botón se oculta con el CSS de la marca), y muestra el aviso «Toque «comunidad» y después «Iniciar sesión», sin escribir contraseña».

Desde la Comunidad, `admin` recibe `403` y el log de Jellyfin dice `remote access disabled and user not in local network`. Así queda cerrada toda la administración, interfaz y API, sin reglas de rutas en Caddy.

## Material y cómo se agrega más

La lista está en `platform/ansible/inventarios/kit/group_vars/all/contenido.yml` (`contenido_medios`), con la URL, el sha256, el autor y la licencia de cada archivo. El rol lo descarga en base (R-05) solo si falta o no coincide. Si un archivo viene en otro formato (`preparar: true`), el rol lo convierte una sola vez en comunidad01, con el `ffmpeg` de la imagen de Jellyfin, a H.264 Main y AAC estéreo en MP4, de 480p como mucho y unos 1 Mb/s (10.1). El original queda en `/srv/medios/originales`, fuera de las bibliotecas, y el MP4 se escribe con otro nombre y se renombra al final, para que Jellyfin no vea un archivo a medias.

| Biblioteca | Archivo | Autor y licencia | Duración |
|---|---|---|---|
| Salud | Lo que necesitas saber acerca del lavado de manos | CDC, dominio público | 2 min |
| Salud | Acabe con los microbios, lávese las manos | CDC, dominio público | 3 min |
| Salud | Protege la salud de tu bebé con las vacunas | CDC, dominio público | 30 s |
| Salud | Lactancia materna, extracción manual de la leche | SOS Telemedicina, Universidad Central de Venezuela, CC BY-SA 4.0 | 2 min |
| Comunidad | Caminandes, Llama Drama | Pablo Vazquez, Beorn Leonard y Francesco Siddi (Blender), CC BY 3.0 | 1,5 min |
| Comunidad | Caminandes 3, Llamigos | Blender Foundation, CC BY 3.0 | 2,5 min |
| Comunidad | La luciérnaga y el vidrio (fábula) | LibriVox, dominio público | 6 min |
| Comunidad | La liebre y el cangrejo (fábula) | LibriVox, dominio público | 9 min |

Los videos vienen de Wikimedia Commons y los audios de LibriVox (Internet Archive). Las animaciones de Caminandes no tienen diálogos. Las licencias CC BY y CC BY-SA piden citar al autor, que queda en esta tabla y en `contenido.yml`.

**Para agregar un archivo** hay que hacer tres cosas:

1. Agregar una entrada a `contenido_medios` con `archivo` (el título que se verá, terminado en `.mp4` o `.mp3`), `biblioteca` (`salud` o `comunidad`), `url`, `sha256` del archivo que se descarga (`sha256sum`), `autor` y `licencia`.
2. Si no viene ya en H.264/AAC MP4 de 480p o en MP3, agregar `preparar: true`.
3. Ejecutar `ansible-playbook playbooks/comunidad01.yml`.

Jellyfin vigila las carpetas y lo muestra solo.

**Quitar.** Al sacar una entrada de la lista, el rol borra ese archivo de su biblioteca en la siguiente ejecución. Solo borra lo que puso él (lo anota en `/srv/jellyfin/medios-del-rol.txt`), así que no toca lo que llegue por el recurso `contenido` cuando exista el flujo de publicación (platform#10).

Como `comunidad` no puede transcodificar, un archivo que llegue en otro formato por fuera del rol no se reproduce, en lugar de cargar la CPU.

## Cómo se despliega

Desde `platform/ansible/`, con `ansible-playbook playbooks/comunidad01.yml`. El rol:

1. Copia `compose.yml` a `/srv/jellyfin/`.
2. Crea `/srv/medios/videos/{salud,comunidad}` y `/srv/medios/originales`, descarga el material, prepara lo que haga falta y quita los archivos del rol que salieron de la lista.
3. Levanta el contenedor y espera a que `/health` responda `Healthy`.
4. Si el asistente inicial no se ha hecho, lo completa (español, Colombia y la cuenta `admin`).
5. Entra como `admin` y aplica la red, Quick Connect apagado, el aviso y el CSS de la pantalla de entrada, las bibliotecas que falten, la cuenta `comunidad` y las políticas. Cada ajuste solo se guarda si difiere del rol. Si cambia la red, reinicia el contenedor al final.

La imagen y el material se descargan por F-17 (en base). La primera vez, con los 6 videos para preparar, el playbook tardó unos 10 minutos.

## Cómo se ve desde la máquina propia

```bash
ssh -L 8080:10.20.20.12:80 kitsalud@100.90.225.113
echo '127.0.0.1 videos.salud.movil' | sudo tee -a /etc/hosts
# después, http://videos.salud.movil:8080
```

Por el túnel la conexión llega desde kit01, que es red local, así que `admin` también puede entrar.

## Cómo se verifica

| Comando (en comunidad01) | Resultado esperado |
|---|---|
| `sudo ss -lntup \| grep jellyfin` | Solo `127.0.0.1:8096` |
| `curl -s 127.0.0.1:8096/health` | `Healthy` |
| Desde kit01, `curl -4 --resolve videos.salud.movil:80:10.20.20.12 http://videos.salud.movil/health` y con `-6` y `[fd5a:fc7e:d716:20::12]` | `Healthy` |
| Desde sw01, `/tool fetch url="http://10.20.20.12/health" http-header-field="Host: videos.salud.movil" output=user` y con `[fd5a:fc7e:d716:20::12]` | `Healthy` |
| `POST /Users/AuthenticateByName` de `admin` a `127.0.0.1:8096` con `X-Forwarded-For` de la Interna y de la Comunidad, en las dos familias | `200` y `403` |
| El mismo login de `comunidad` con `Pw` vacío | `200` desde las dos redes |
| En el navegador, tocar «comunidad» y «Iniciar sesión» sin contraseña | La página de inicio con las bibliotecas Salud y Comunidad |
| El login de `admin` por Caddy con un `X-Forwarded-For` falso de la Interna | `403` (Jellyfin ve la IP real) |
| `POST /Items/<id>/PlaybackInfo` como `comunidad` con el perfil de un navegador móvil | `SupportsDirectPlay: true` y sin `TranscodingUrl` |
| `ffprobe` de cada MP4 | `h264` Main y `aac`, 480 de alto o menos |
| 8 descargas simultáneas de `/Videos/<id>/stream?static=true` y `/Audio/<id>/stream?static=true` a 1 Mb/s durante 60 s, con `docker stats` y `pgrep ffmpeg` | Jellyfin con 0,2 % de CPU de media (pico 0,6 %), unos 270 MB y ningún `ffmpeg` |
| En el panel de Jellyfin, una reproducción en curso | "Reproducción directa" |

## Diagnóstico

- **`admin` no puede entrar.** Si entra desde la Comunidad, es lo esperado. Si entra desde la Interna, revisar en el log (`sudo docker logs jellyfin-jellyfin-1`) con qué IP llegó. Si es `127.0.0.1`, Caddy no está mandando `X-Forwarded-For` o falta `127.0.0.1` en los proxies de confianza.
- **La pantalla pide la contraseña de `comunidad`.** Es lo esperado. En Jellyfin 12 una contraseña vacía cuenta como configurada (`HasPassword: true`), así que la pantalla muestra el formulario. Se deja vacía y se toca «Iniciar sesión».
- **Un video no se reproduce.** No está en H.264/AAC, o el navegador no lo reproduce directo. `ffprobe` (está en la imagen, en `/usr/lib/jellyfin-ffmpeg/ffprobe`) muestra los códecs.
- **Una reproducción falla con `500` y el log dice `The process cannot access the file '/cache/transcodes/.jellyfin-transcode'`.** Jellyfin crea ese marcador con el primer pedido y varios a la vez chocan. Pasa una sola vez, porque el marcador queda en `/srv/jellyfin/cache`; se vuelve a intentar.
- **La biblioteca no muestra un archivo nuevo.** Jellyfin vigila las carpetas, pero se puede forzar con "Escanear todas las bibliotecas" en el panel o `POST /Library/Refresh`.
