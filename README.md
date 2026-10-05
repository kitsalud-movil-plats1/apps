# apps

Aplicaciones del kit desplegadas con Docker Compose dentro de las VMs.

| Ruta | VM | Servicio | Nombre |
|---|---|---|---|
| `clinica01/dhis2/` | clinica01 | DHIS2 + PostgreSQL (también guarda los formularios) | `pacientes.salud.movil` |
| `clinica01/consultas/` | clinica01 | Consulta de formularios para el grupo AD `clinicos` | `consultas.salud.movil` |
| `comunidad01/caddy/` | comunidad01 | Reverse proxy; HTTPS con la CA interna para `registro`, HTTP para el contenido público | - |
| `comunidad01/kiwix/` | comunidad01 | Biblioteca de salud y contenido infantil (ZIM) | `biblioteca.salud.movil` |
| `comunidad01/jellyfin/` | comunidad01 | Audio y video: contenido médico general y contenido para la comunidad, sin transcodificación | `videos.salud.movil` |
| `comunidad01/formularios/` | comunidad01 | Prerregistro mínimo y asistido | `registro.salud.movil` |

comunidad01 es la única VM a la que llega la comunidad (80/443). No guarda datos de pacientes: los formularios se escriben en PostgreSQL de clinica01 con un usuario que solo tiene permiso de `INSERT` (D-07 en `docs`). El contenido llega desde el recurso SMB `contenido` de clinica01 por `rsync`.

Cada servicio incluye un `.env.example`. Los valores reales nunca se versionan.
