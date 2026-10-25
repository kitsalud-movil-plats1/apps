# Biblioteca Kiwix en comunidad01

Portal de literatura para la sala de espera (R7, D-08, sección 10.5). `kiwix-serve` publica una biblioteca médica en español, una enciclopedia para niños y simulaciones educativas, sin Internet. Caddy la publica como `http://biblioteca.salud.movil` ([`../caddy/`](../caddy/)).

| Archivo | Qué es |
|---|---|
| [`compose.yml`](compose.yml) | `ghcr.io/kiwix/kiwix-serve:3.8.2`, límite de 512 MB, `restart: unless-stopped`, solo en `127.0.0.1:8090`. Sirve todos los `*.zim` de `/srv/medios/zim`, montada en solo lectura |

## ZIM

La lista está en `platform/ansible/inventarios/kit/group_vars/all/contenido.yml`, con el archivo, la carpeta de origen en <https://download.kiwix.org/zim/> y el sha256.

| Libro | Archivo | Fecha | Tamaño |
|---|---|---|---|
| Wikipedia Médica en español (con imágenes) | `wikipedia_es_medicine_maxi_2026-07.zim` | 2026-07 | 626 MiB (656 736 045 B) |
| Vikidia, enciclopedia para niños (con imágenes) | `vikidia_es_all_maxi_2026-09.zim` | 2026-09 | 127 MiB (133 548 765 B) |
| Simulaciones PhET en español | `phet_es_all_2026-08.zim` | 2026-08 | 104 MiB (109 215 764 B) |

En total ocupan unos 857 MiB en el disco de datos de comunidad01. La Wikipedia Médica de 2026-10 pesa 447 MiB, menos que la de julio, así que se mantiene la de julio, que es la más completa.

## Cómo se despliega

Desde `platform/ansible/`, con el rol `kiwix` de `apps/ansible/roles/`.

```bash
ansible-playbook playbooks/comunidad01.yml                         # Docker, Kiwix y Caddy
ansible-playbook playbooks/comunidad01.yml -e kiwix_estado=stopped # docker compose down; los ZIM quedan
```

- **Descarga.** Cada ZIM se baja por F-17 (HTTPS, solo IPv4) a `/srv/medios/zim` y se verifica con su sha256. Si el archivo ya está y coincide no se vuelve a bajar. Se descarga en base, nunca en campo (R-05).
- **Lista.** Para cambiar un libro se edita `contenido.yml` con el archivo y el sha256 nuevos (el sha256 está en `<url del ZIM>.sha256`). El rol quita los ZIM que salen de la lista y reinicia `kiwix-serve`, que lee la carpeta al arrancar.
- **Carpeta de medios.** `/srv/medios/` es la carpeta a la que llegará el contenido publicado desde clinica01 (platform#10). Hasta entonces, los ZIM se cargan directamente en comunidad01.

## Cómo se verifica

| Comando | Resultado esperado |
|---|---|
| En comunidad01, `cd /srv/medios/zim && sha256sum *.zim` | Los mismos valores de `contenido.yml` |
| `curl -s http://127.0.0.1:8090/catalog/v2/entries \| grep -o '<title>[^<]*'` | Wikipedia Médica, Vikidia y Simulaciones interactivas de PhET |
| `curl -s 'http://127.0.0.1:8090/search?content=wikipedia_es_medicine_maxi_2026-07&pattern=diabetes' \| grep -c '/content/'` | Varios resultados (25 en la primera página) |
| Desde la Interna, `curl -4` y `curl -6 http://biblioteca.salud.movil/` | `200` |
| `sudo docker stats --no-stream kiwix-kiwix-1` | Unos pocos MB en reposo, dentro del límite de 512 MB |

**Sin Internet.** Con el reenvío hacia `enp170s0` cortado en kit01 y los contenedores reiniciados, la página, la búsqueda y los artículos siguen respondiendo, porque los ZIM, las imágenes de Docker y el DNS de `salud.movil` son locales.

## Diagnóstico

- **`502` desde Caddy.** `kiwix-serve` no está arriba. `sudo docker compose -f /srv/kiwix/compose.yml ps` y `sudo docker logs kiwix-kiwix-1`, que imprime la línea con la que arrancó y, si falla, el contenido de `/data`.
- **Falta un libro.** El ZIM no está en `/srv/medios/zim` o no es legible por el usuario de la imagen (`1001`); los ZIM quedan con `644`.
- **`Fulltext search unavailable` o `Invalid request` en la búsqueda.** La búsqueda se pide con `content=<nombre del archivo sin .zim>`. Los tres ZIM traen índice de texto completo.
- **La descarga falla.** La VM sale a Internet solo por 80 y 443 en IPv4 (F-17). Desde comunidad01, `curl -sI https://download.kiwix.org/zim/`.
