# Incidencias de la fuente

| Fecha y hora | URL | HTTP | Content-Type | Detalle |
|---|---|---|---|---|
| 2026-11-08 01:37:39 | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-empresariales-m | 403 | text/html | No se pudo descargar la página de enlaces |
| 2026-11-08 01:53:54 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html; charset=UTF-8 | La respuesta no es un archivo Excel (posible bloqueo anti-bot) |
| 2026-11-08 02:02:02 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html; charset=UTF-8 | Con requests la respuesta no es Excel (verificación anti-bot con JavaScript); se intenta con navegador automatizado |
| 2026-11-08 02:10:39 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html; charset=UTF-8 | Con requests la respuesta no es Excel (verificación anti-bot con JavaScript); se intenta con navegador automatizado |
| 2026-11-08 02:12:21 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | sin respuesta | ? | El navegador automatizado tampoco obtuvo el Excel |
| 2026-11-08 02:29:45 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html | www.bcrp.gob.pe responde con verificación anti-bot (JavaScript) en vez del XLSX; se usa la descarga Excel de BCRPData |
| 2026-11-08 02:47:49 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html | www.bcrp.gob.pe responde con verificación anti-bot (JavaScript) en vez del XLSX; se usa el scraping de las tablas HTML de BCRPData |
| 2026-11-25 03:30:39 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html | www.bcrp.gob.pe responde con verificación anti-bot (JavaScript) en vez del XLSX; se usa el scraping de las tablas HTML de BCRPData |

## Resumen y solución adoptada
| Elemento | Detalle |
|---|---|
| URL bloqueada | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx |
| Respuesta | HTTP 200 con `text/html` (≈1 KB): página de verificación anti-bot (JavaScript) en lugar del archivo Excel. Copia guardada en `datos_crudos/encuesta_expectativas/respuesta_bloqueada_xlsx_<código>.html` |
| robots.txt | www.bcrp.gob.pe: la ruta del XLSX está PERMITIDA. estadisticas.bcrp.gob.pe: no publica robots.txt (HTTP 404) |
| Bloqueo por IP | El 2026-11-08 una IP de Google Colab recibió HTTP 403 en todo el dominio (incluida la API); al cambiar de máquina se recuperó el acceso |
| Intentos descartados | (1) navegador automatizado Playwright: tampoco obtuvo el Excel; (2) descarga `/api/.../xls` de BCRPData: descartada porque usa la misma API de la Vía 1 |
| Solución definitiva | Web scraping (BeautifulSoup) de las tablas HTML de BCRPData con las mismas series de la Encuesta: PD38045AM, PD37981AM y PD38046AM. Cumple el numeral 2.4.3 (rastreo de HTML con selectores y pausas) |
| Captura de pantalla | `2 DESARROLLO .../captura_bloqueo_xlsx.png` |
| 2026-11-27 17:09:52 | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-empresariales-m | 403 | text/html | No se pudo descargar la página de la Encuesta |
| 2026-11-27 17:20:56 | https://www.bcrp.gob.pe/docs/Estadisticas/Encuestas/expectativas-series-de-indices.xlsx | 200 | text/html | www.bcrp.gob.pe responde con verificación anti-bot (JavaScript) en vez del XLSX; se usa el scraping de las tablas HTML de BCRPData |
