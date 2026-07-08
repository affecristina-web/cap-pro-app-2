# cap-pro-app-2
## Cobertura de comunidades autónomas

Sistema automatizado para **15 de 19** comunidades/ciudades autónomas.

**Excluidas de la automatización (gestión manual):**
- Baleares, Cantabria, Navarra, Ceuta

Motivo: todas sus fuentes oficiales (portal de trámites, sede electrónica y
boletín oficial) bloquean el acceso automatizado vía `robots.txt`, sin
dominio alternativo disponible. Se decidió respetar esa política en vez de
forzar el acceso mediante proxy. Revisado en profundidad probando entre 2 y
5 dominios por comunidad.
