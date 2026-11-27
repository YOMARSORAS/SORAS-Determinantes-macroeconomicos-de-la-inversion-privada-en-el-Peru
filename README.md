# Determinantes macroeconómicos de la inversión privada en el Perú

| Dato | Detalle |
|---|---|
| Autor | Yomar Cristhian Soras Quispe |
| Código de matrícula | 2024200530J |
| Curso | Finanzas I (055D) — Unidad II — UNCP, 2026-II |
| Tema del temario | N.º 56: Métodos de evaluación de inversiones |
| Repositorio | https://github.com/YOMARSORAS/SORAS-Determinantes-macroeconomicos-de-la-inversion-privada-en-el-Peru |

**Objetivo:** estimar el efecto de la tasa de interés corporativa, el tipo de cambio y las expectativas empresariales sobre la inversión privada real del Perú (enero 2000 – diciembre 2025), mediante un modelo ARDL con corrección de errores.

## 1. Fuentes de datos y endpoints

### Vía 1 — API REST de BCRPData (`codigo/01_extraccion_api.py`)
Una solicitud por serie, formato JSON. No requiere clave.

| Código | Serie | Endpoint |
|---|---|---|
| PN02533AQ | Inversión bruta fija privada (millones S/ 2007), trimestral | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN02533AQ/json/2000-1/2025-4/esp` |
| PN01770AM | PBI, índice 2007=100 | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01770AM/json/2000-1/2025-12/esp` |
| PN07809NM | Tasa preferencial corporativa a 90 días, MN (%) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07809NM/json/2000-1/2025-12/esp` |
| PN01206PM | Tipo de cambio interbancario venta, promedio (S/ por US$) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01206PM/json/2000-1/2025-12/esp` |
| PN38923BM | Términos de intercambio, índice 2007=100 | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN38923BM/json/2000-1/2025-12/esp` |
| PN07819NM | Auxiliar: tasa interbancaria promedio, MN (%) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07819NM/json/2000-1/2025-12/esp` |
| PN07807NM | Auxiliar: TAMN (%) | `https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07807NM/json/2000-1/2025-12/esp` |

### Vía 2 — Web scraping de la Encuesta de Expectativas Macroeconómicas del BCRP (`codigo/02_scraping_web.py`)
- Página índice: https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/expectativas-empresariales-m
- Tablas HTML: `https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/{código}/html` para PD38045AM (expectativas de la economía a 3 meses), PD37981AM (a 12 meses) y PD38046AM (del sector a 3 meses).
- Selectores (BeautifulSoup): `a[href*="/resultados/"]`, `a[href$=".xlsx"]`, `tr` / `td` / `th`. Pausa de 2 s entre solicitudes; User-Agent identificable; revisión de `robots.txt`.
- El XLSX «Índices de confianza empresarial» se intenta descargar, pero el servidor responde con verificación anti-bot: ver `incidencias_fuente.md`.

## 2. Parámetros congelados
- `FECHA_INICIO = "2000-01"` y `FECHA_CORTE = "2025-12"` (declarados al inicio de cada script).
- Semilla: `0530` (últimos 4 dígitos del código de matrícula; `04_analisis.py`).

## 3. Orden de ejecución
Desde la carpeta del proyecto (rutas relativas):
```
pip install -r requirements.txt
python codigo/01_extraccion_api.py     # Vía 1  -> datos_crudos/datos_crudos_api_2024200530J.csv
python codigo/02_scraping_web.py       # Vía 2  -> datos_crudos/datos_crudos_scraping_2024200530J.csv
python codigo/03_limpieza_datos.py     # base   -> datos_procesados/datos_procesados_2024200530J.csv
python codigo/04_analisis.py           # tablas y figuras -> salidas/
```
Cada script agrega su registro a `log_ejecucion.txt` (fecha y hora, URL, código HTTP y filas).

## 4. Entorno
- Python 3.13.18 (Google Colab).
- Librerías con versión exacta en `requirements.txt`.
- Clave de API: **no se requiere** (BCRPData es abierto). Opcional: copiar `.env.example` a `.env` y escribir un correo en `USER_AGENT_CONTACTO` para identificarse en el User-Agent.

## 5. Estructura
```
codigo/              01_extraccion_api.py, 02_scraping_web.py, 03_limpieza_datos.py, 04_analisis.py
datos_crudos/        salidas de la API y del scraping, sin editar (JSON, HTML y CSV)
datos_procesados/    datos_procesados_2024200530J.csv (mensual, 312 filas), datos_trimestrales_2024200530J.csv, datos_largos_2024200530J.csv
salidas/             tablas (.csv, .tex) y figuras (.pdf, .png) del artículo
diccionario_variables.md, incidencias_fuente.md, log_ejecucion.txt, requirements.txt, .env.example
```

## 6. Integridad
- SHA-256 de `datos_procesados/datos_procesados_2024200530J.csv`: 05b9a6f057a082e1ab8f23ee69bebd5a4400637778ea864bfd8ffbd7e52d22d0

## 7. Guía de cotejo con la fuente
`datos_procesados_2024200530J.csv` combina datos observados y datos construidos; estos últimos se identifican así:

| Columna | Cómo cotejarla con el BCRP |
|---|---|
| pbi, tipo_cambio, terminos_intercambio | Igual al valor publicado en BCRPData para ese mes |
| tasa_corporativa | Igual a PN07809NM cuando `tasa_imputada = 0` (desde 2010-08). Con `tasa_imputada = 1` (2000-01 a 2010-07) es una retropolación MCO sobre TAMN e interbancaria (ver log de `03_limpieza_datos.py`) |
| expectativa_economia_3m, _12m, expectativa_sector_3m | Igual a la tabla HTML del BCRP cuando `expectativa_imputada = 0` (desde 2002-04) |
| inversion_privada | Desagregación de Denton: la **suma de los 3 meses de cada trimestre es igual** a PN02533AQ. El dato trimestral oficial está en `datos_trimestrales_2024200530J.csv` |

Las fuentes se actualizan y pueden revisar sus series; el hash se coteja contra el archivo entregado (numeral 2.4.5).
