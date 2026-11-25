# Diccionario de variables

| Variable | Definición | Unidad | Frecuencia | Fuente | Código de serie / URL |
|---|---|---|---|---|---|
| inv_priv_real | Inversión bruta fija privada real (se desagrega a mensual por Denton en 03) | Millones de S/ de 2007 | Trimestral | BCRPData (API) | PN02533AQ — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN02533AQ/json |
| pbi_idx | Producto bruto interno real | Índice 2007=100 | Mensual | BCRPData (API) | PN01770AM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01770AM/json |
| tasa_corp | Tasa activa preferencial corporativa a 90 días en MN (publicada desde ago-2010; retropolada antes en 03) | % efectivo anual | Mensual | BCRPData (API), fuente SBS | PN07809NM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07809NM/json |
| tc | Tipo de cambio interbancario venta, promedio del periodo | S/ por US$ | Mensual | BCRPData (API) | PN01206PM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN01206PM/json |
| tot | Términos de intercambio de comercio exterior | Índice 2007=100 | Mensual | BCRPData (API) | PN38923BM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN38923BM/json |
| aux_tasa_interb | AUXILIAR: tasa interbancaria promedio en MN (solo para retropolar tasa_corp) | % anual | Mensual | BCRPData (API) | PN07819NM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07819NM/json |
| aux_tamn | AUXILIAR: TAMN, tasa activa promedio en MN (solo para retropolar tasa_corp) | % efectivo anual | Mensual | BCRPData (API), fuente SBS | PN07807NM — https://estadisticas.bcrp.gob.pe/estadisticas/series/api/PN07807NM/json |

| exp_eco_3m | Índice de expectativas de la economía a 3 meses (VARIABLE PRINCIPAL de expectativas; publicado desde abr-2002) | Índice (0–100; >50 = optimista) | Mensual | Encuesta de Expectativas Macroeconómicas, BCRP (scraping HTML) | PD38045AM — https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PD38045AM/html |
| exp_eco_12m | Índice de expectativas de la economía a 12 meses (robustez; desde jun-2008) | Índice (0–100; >50 = optimista) | Mensual | Encuesta de Expectativas Macroeconómicas, BCRP (scraping HTML) | PD37981AM — https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PD37981AM/html |
| exp_sector_3m | Índice de expectativas del sector a 3 meses (robustez; desde jun-2002) | Índice (0–100; >50 = optimista) | Mensual | Encuesta de Expectativas Macroeconómicas, BCRP (scraping HTML) | PD38046AM — https://estadisticas.bcrp.gob.pe/estadisticas/series/mensuales/resultados/PD38046AM/html |

_Vía 1 (API): series PN*. Vía 2 (scraping HTML): series PD*._

## Variables procesadas (datos_procesados_<código>.csv, mensual 2000-01 a 2025-12)
| Columna | Definición | Unidad | Origen |
|---|---|---|---|
| fecha | Mes (AAAA-MM) | — | — |
| inversion_privada | Inversión bruta fija privada real, mensualizada por Denton (la suma de cada trimestre = dato oficial) | Millones de S/ de 2007 | PN02533AQ (API) |
| pbi | Producto bruto interno real | Índice 2007=100 | PN01770AM (API) |
| tasa_corporativa | Tasa preferencial corporativa a 90 días en MN (retropolada antes de ago-2010) | % anual | PN07809NM (API) |
| tipo_cambio | Tipo de cambio interbancario venta, promedio del mes | S/ por US$ | PN01206PM (API) |
| terminos_intercambio | Términos de intercambio | Índice 2007=100 | PN38923BM (API) |
| expectativa_economia_3m | Expectativa empresarial de la economía a 3 meses (variable principal) | Índice 0–100 (>50 optimista) | PD38045AM (scraping) |
| expectativa_economia_12m | Expectativa de la economía a 12 meses (robustez; vacía antes de jun-2008) | Índice 0–100 | PD37981AM (scraping) |
| expectativa_sector_3m | Expectativa del sector a 3 meses (robustez; vacía antes de jun-2002) | Índice 0–100 | PD38046AM (scraping) |
| tasa_imputada | 1 = tasa reconstruida por MCO con TAMN e interbancaria (2000-01 a 2010-07) | 0/1 | Construida |
| expectativa_imputada | 1 = expectativa completada con el primer valor publicado (2000-01 a 2002-03) | 0/1 | Construida |
| covid | 1 = confinamiento (2020-03 a 2020-06) | 0/1 | Construida |
| atipico | 1 = alguna variable del modelo tuvo una variación mensual fuera de [Q1 − 3·RIC, Q3 + 3·RIC]; se marca, no se elimina | 0/1 | Construida |

`datos_trimestrales_<código>.csv` usa los mismos nombres (inversión oficial; resto en promedio del trimestre). `datos_largos_<código>.csv` tiene una fila por mes y variable: fecha, variable, valor, fuente.
