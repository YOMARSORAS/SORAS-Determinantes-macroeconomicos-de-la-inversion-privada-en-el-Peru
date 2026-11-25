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
