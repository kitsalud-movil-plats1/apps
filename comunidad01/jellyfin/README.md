# Jellyfin en comunidad01

Audio y video para la sala de espera (R7, D-08, sección 10.5). Hay dos bibliotecas: **Salud**, con contenido médico general, y **Comunidad**, con material educativo y para niños. La comunidad entra sin contraseña con el usuario `comunidad`. Todo se reproduce directo, sin transcodificar, y la administración solo se puede hacer desde la Interna y por NetBird. Caddy lo publica en `http://videos.salud.movil` ([`../caddy/`](../caddy/)).

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
| `comunidad` | Ninguna | Visible en la pantalla de entrada. Solo reproduce: sin transcodificación de video ni de audio, sin remux, sin descargas, sin borrar y sin cambiar preferencias |

Desde la Comunidad, `admin` recibe `403` y el log de Jellyfin dice `remote access disabled and user not in local network`. Así queda cerrada toda la administración, interfaz y API, sin reglas de rutas en Caddy.

## Material de prueba

La lista está en `platform/ansible/inventarios/kit/group_vars/all/contenido.yml` (`contenido_medios`), con la URL, el sha256 y la licencia de cada archivo. El rol los descarga en base (R-05) solo si faltan o no coinciden. Todo es de dominio público (Internet Archive y LibriVox) y viene en H.264 Constrained Baseline con AAC, a 480p o menos y unos 0,8 Mb/s, o en MP3 a 64 kb/s.

| Biblioteca | Archivo | Formato |
|---|---|---|
| Salud | Resfriados y estornudos (1955) | 640×480, 9 min |
| Salud | Higiene y cuidado personal (1941) | 640×480, 10 min |
| Comunidad | Sorpresa de Navidad (1947) | 320×240, 8 min |
| Comunidad | La luciérnaga y el vidrio (fábula) | MP3, 6 min |
| Comunidad | La liebre y el cangrejo (fábula) | MP3, 9 min |

Los dos videos de salud están en inglés. El flujo de publicación desde el recurso `contenido` (platform#10) cambiará este material por contenido propio. Un video nuevo tiene que venir ya en H.264/AAC a 480p (≈ 1 Mb/s) y un audio en MP3. Como `comunidad` no puede transcodificar, un archivo en otro formato no se reproduce, en lugar de cargar la CPU.

## Cómo se despliega

Desde `platform/ansible/`, con `ansible-playbook playbooks/comunidad01.yml`. El rol:

1. Crea `/srv/medios/videos/{salud,comunidad}` y descarga el material.
2. Copia `compose.yml` a `/srv/jellyfin/`, levanta el contenedor y espera a que `/health` responda `Healthy`.
3. Si el asistente inicial no se ha hecho, lo completa (español, Colombia y la cuenta `admin`).
4. Entra como `admin` y aplica la red, las bibliotecas que falten, la cuenta `comunidad` y las políticas. La red y las políticas solo se guardan si difieren de las del rol. Si cambia la red, reinicia el contenedor al final.

La imagen se descarga por F-17 (en base).

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
| El login de `admin` por Caddy con un `X-Forwarded-For` falso de la Interna | `403` (Jellyfin ve la IP real) |
| `POST /Items/<id>/PlaybackInfo` como `comunidad` con el perfil de un navegador móvil | `SupportsDirectPlay: true` y sin `TranscodingUrl` |
| 5 descargas de `/Videos/<id>/stream?static=true` a 1 Mb/s durante 60 s, con `docker stats` y `pgrep ffmpeg` | Jellyfin con 0,3 % de CPU de media (pico 1,8 %), unos 190 MB y ningún `ffmpeg` |
| En el panel de Jellyfin, una reproducción en curso | "Reproducción directa" |

## Diagnóstico

- **`admin` no puede entrar.** Si entra desde la Comunidad, es lo esperado. Si entra desde la Interna, revisar en el log (`sudo docker logs jellyfin-jellyfin-1`) con qué IP llegó. Si es `127.0.0.1`, Caddy no está mandando `X-Forwarded-For` o falta `127.0.0.1` en los proxies de confianza.
- **Un video no se reproduce.** No está en H.264/AAC, o el navegador no lo reproduce directo. `ffprobe` (está en la imagen, en `/usr/lib/jellyfin-ffmpeg/ffprobe`) muestra los códecs.
- **Una reproducción falla con `500` y el log dice `The process cannot access the file '/cache/transcodes/.jellyfin-transcode'`.** Jellyfin crea ese marcador con el primer pedido y varios a la vez chocan. Pasa una sola vez, porque el marcador queda en `/srv/jellyfin/cache`; se vuelve a intentar.
- **La biblioteca no muestra un archivo nuevo.** Jellyfin vigila las carpetas, pero se puede forzar con "Escanear todas las bibliotecas" en el panel o `POST /Library/Refresh`.
