# Determinantes macroeconómicos de la inversión privada en el Perú

- **Autor:** Yomar Cristhian Soras Quispe
- **Código de matrícula:** 2024200530J
- **Curso:** Finanzas I (055D) — Unidad II — UNCP 2026-II
- **Tema N.º 56 del temario:** Métodos de evaluación de inversiones
- **Repositorio:** https://github.com/YOMARSORAS/SORAS-Determinantes-macroeconomicos-de-la-inversion-privada-en-el-Peru

## Fuentes de datos
| Vía | Fuente | Endpoint / URL |
|---|---|---|
| 1 — API | BCRPData | https://estadisticas.bcrp.gob.pe/estadisticas/series/api/... |
| 2 — Web scraping | BCRP — Encuesta de Expectativas Macroeconómicas (tablas HTML de BCRPData) | https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-empresariales-m |

## Parámetros
- FECHA_INICIO: 2000-01
- FECHA_CORTE: 2025-12

## Orden de ejecución
1. `python codigo/01_extraccion_api.py`
2. `python codigo/02_scraping_web.py`
3. `python codigo/03_limpieza_datos.py`
4. `python codigo/04_analisis.py`

## Entorno
- Python: (por completar)
- Librerías: ver `requirements.txt`
- Clave de API: no se requiere (BCRPData es abierto). Copiar `.env.example` a `.env` y completar el contacto.

## Integridad
- SHA-256 de `datos_procesados/datos_procesados_2024200530J.csv`: (por completar)

## Vía 2 — Web scraping (numeral 2.4.3: rastreo de HTML con selectores y pausas)
- **Fuente:** Encuesta de Expectativas Macroeconómicas del BCRP, publicada en BCRPData.
- **Página índice:** https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-empresariales-m
- **Selectores (BeautifulSoup):** `a[href*="/resultados/"]` (series), `a[href$=".xlsx"]` (enlaces Excel), `tr`/`td`/`th` (filas de cada tabla).
- **Navegación:** página índice -> página de resultados de cada serie (`/resultados/{código}/html`); cada tabla se publica completa en una sola página (sin paginación numerada).
- **Pausas:** 2 s entre solicitudes; reintentos con espera creciente. **User-Agent:** `Proyecto-academico-UNCP-Finanzas-I`.
- **Crudo guardado intacto:** `datos_crudos/encuesta_expectativas/` (HTML) y `datos_crudos/datos_crudos_scraping_<código>.csv`.
- **Incidencia:** el XLSX «Índices de confianza empresarial» se intenta descargar, pero www.bcrp.gob.pe responde con verificación anti-bot (JavaScript); ver `incidencias_fuente.md`.
