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
| 2 — Descarga programática | BCRP — Encuesta de Expectativas Macroeconómicas | (por completar) |

## Parámetros
- FECHA_INICIO: 2004-01
- FECHA_CORTE: 2026-06

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
