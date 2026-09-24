# apps

Aplicaciones del kit desplegadas con Docker Compose.

| Ruta | Host | Servicio | Nombre |
|---|---|---|---|
| `dhis2/` | apps01 | DHIS2 + PostgreSQL | `pacientes.salud.movil` |
| `dmz01/caddy/` | dmz01 | Reverse proxy y TLS interno | - |
| `dmz01/kiwix/` | dmz01 | Biblioteca de salud | `biblioteca.salud.movil` |
| `dmz01/formularios/` | dmz01 | Formularios de prerregistro | `registro.salud.movil` |

Cada servicio incluye un `.env.example`. Los valores reales nunca se versionan.
