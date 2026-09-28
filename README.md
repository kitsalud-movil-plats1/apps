# apps

Aplicaciones del kit desplegadas con Docker Compose.

| Ruta | Host | Servicio | Nombre |
|---|---|---|---|
| `dhis2/` | apps01 | DHIS2 + PostgreSQL | `pacientes.salud.movil` |
| `web01/caddy/` | web01 | Reverse proxy y TLS interno (CA interna compartida con apps01) | - |
| `web01/kiwix/` | web01 | Biblioteca de salud (ZIM por NFS de solo lectura desde files01) | `biblioteca.salud.movil` |
| `web01/formularios/` | web01 | Formularios de prerregistro (datos en PostgreSQL de apps01) | `registro.salud.movil` |

web01 es el único servidor de la VLAN 20 al que llegan los invitados (80/443). No guarda datos: los formularios se escriben en apps01 con un usuario que solo tiene permiso de `INSERT` (ver D-15 y R-06 en `docs`).

Cada servicio incluye un `.env.example`. Los valores reales nunca se versionan.
