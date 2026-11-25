# Nombres y apellidos: YOMAR CRISTHIAN SORAS QUISPE
# Código de matrícula: 2024200530J
# Tema N.º 56 del temario: Métodos de evaluación de inversiones — Determinantes macroeconómicos de la inversión privada en el Perú
# Fecha de extracción: 2026-11-07 (Vía 1) y 2026-11-24 (Vía 2)
"""
03_limpieza_datos.py — Limpieza, armonización de frecuencias e integración de las dos vías.

Entradas (sin modificarlas):
  datos_crudos/datos_crudos_api_<CODIGO>.csv       Vía 1 (API BCRPData)
  datos_crudos/datos_crudos_scraping_<CODIGO>.csv  Vía 2 (web scraping de la Encuesta de Expectativas)
Salidas en datos_procesados/:
  datos_procesados_<CODIGO>.csv    BASE PRINCIPAL: mensual 2000-01 a 2025-12 (formato ancho)
  datos_trimestrales_<CODIGO>.csv  la misma base agregada a trimestres (inversión oficial, sin desagregar)
  datos_largos_<CODIGO>.csv        base principal en formato largo (fecha, variable, valor, fuente)
Decisiones (todas declaradas y marcadas con variables indicadoras *_imputada):
  1. Fechas: los periodos del BCRP ("Ene.2000", "Abr02", "T1.00") se convierten a fechas.
  2. Inversión privada (trimestral) -> mensual por desagregación de Denton (primeras
     diferencias): la suma de los 3 meses reproduce EXACTAMENTE el dato trimestral oficial.
  3. Tasa corporativa (publicada desde ago-2010) -> retropolación 2000-01..2010-07 con una
     regresión MCO sobre la TAMN y la tasa interbancaria estimada en el periodo común.
  4. Expectativas a 3 meses (publicada desde abr-2002) -> los 27 meses previos se completan
     con el primer valor publicado (extrapolación constante hacia atrás).
  5. Huecos internos (n.d.) -> interpolación lineal.
  6. Valores atípicos: se MARCAN (regla del rango intercuartílico sobre la variación mensual),
     no se eliminan. covid = 1 en 2020-03..2020-06 (confinamiento).
  7. Los logaritmos y tasas de variación se calculan en 04_analisis.py.
"""

import hashlib
import logging
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# 1. PARÁMETROS
# ----------------------------------------------------------------------------
CODIGO = "2024200530J"
FECHA_INICIO = "2000-01"
FECHA_CORTE = "2025-12"
COVID = ("2020-03", "2020-06")
MIN_PERIODOS = 60            # mínimo de la consigna para series de tiempo mensuales
MIN_FILAS_LARGO = 1000       # meta propia: más de 1 000 observaciones en formato largo

# Código de serie -> nombre de variable (ver diccionario_variables.md)
VIA1 = {"PN02533AQ": "inv_priv_real", "PN01770AM": "pbi_idx", "PN07809NM": "tasa_corp",
        "PN01206PM": "tc", "PN38923BM": "tot", "PN07819NM": "aux_tasa_interb", "PN07807NM": "aux_tamn"}
VIA2 = {"PD38045AM": "exp_eco_3m", "PD37981AM": "exp_eco_12m", "PD38046AM": "exp_sector_3m"}

# Nombres internos -> nombres finales de la base procesada (orden de las columnas)
NOMBRES = {
    "inv_priv_real": "inversion_privada",          # millones de S/ de 2007 (mensualizada por Denton)
    "pbi_idx": "pbi",                              # índice 2007 = 100
    "tasa_corp": "tasa_corporativa",               # % anual, preferencial corporativa 90 días MN
    "tc": "tipo_cambio",                           # S/ por US$
    "tot": "terminos_intercambio",                 # índice 2007 = 100
    "exp_eco_3m": "expectativa_economia_3m",       # índice 0-100 (> 50 = optimista)
    "exp_eco_12m": "expectativa_economia_12m",     # índice 0-100 (robustez; desde jun-2008)
    "exp_sector_3m": "expectativa_sector_3m",      # índice 0-100 (robustez; desde jun-2002)
    "tasa_corp_imputada": "tasa_imputada",         # 1 = valor reconstruido (2000-01 a 2010-07)
    "exp_eco_3m_imputada": "expectativa_imputada", # 1 = valor completado (2000-01 a 2002-03)
    "covid": "covid",                              # 1 = 2020-03 a 2020-06
    "atipico": "atipico",                          # 1 = alguna variable del modelo tuvo un salto atípico ese mes
}

MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7,
         "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12}

# ----------------------------------------------------------------------------
# 2. RUTAS Y REGISTRO
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent
DIR_CRUDOS = BASE / "datos_crudos"
DIR_PROC = BASE / "datos_procesados"
DIR_PROC.mkdir(exist_ok=True)
ARCHIVO_LOG = BASE / "log_ejecucion.txt"
SALIDA = DIR_PROC / f"datos_procesados_{CODIGO}.csv"
SALIDA_TRIM = DIR_PROC / f"datos_trimestrales_{CODIGO}.csv"
SALIDA_LARGO = DIR_PROC / f"datos_largos_{CODIGO}.csv"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | 03_limpieza_datos | %(message)s",
    handlers=[logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger()


# ----------------------------------------------------------------------------
# 3. FUNCIONES
# ----------------------------------------------------------------------------
def a_fecha(periodo):
    """Convierte un periodo del BCRP en fecha (primer día del mes o del trimestre)."""
    p = str(periodo).strip()
    m = re.match(r"^T([1-4])\.?\s?(\d{2}|\d{4})$", p)                     # trimestral: T1.00
    if m:
        anio = int(m.group(2)); anio += 2000 if anio < 100 else 0
        return pd.Timestamp(anio, 3 * int(m.group(1)) - 2, 1)
    m = re.match(r"^([A-Za-zé]{3})\.?\s?(\d{2}|\d{4})$", p)                 # mensual: Ene.2000 / Abr02
    if m and m.group(1).lower() in MESES:
        anio = int(m.group(2)); anio += 2000 if anio < 100 else 0
        return pd.Timestamp(anio, MESES[m.group(1).lower()], 1)
    return pd.NaT


def a_numero(valor):
    """'n.d.' y vacíos -> NaN; el resto a float."""
    return pd.to_numeric(str(valor).strip().replace(",", ""), errors="coerce")


def leer_crudo(ruta, mapa, col_codigo="codigo_serie"):
    """Lee un crudo en formato largo y devuelve una tabla ancha por fecha."""
    df = pd.read_csv(ruta, dtype=str)
    df = df[df[col_codigo].isin(mapa)].copy()
    df["fecha"] = df["periodo"].map(a_fecha)
    df["valor_num"] = df["valor"].map(a_numero)
    sin_fecha = df["fecha"].isna().sum()
    if sin_fecha:
        log.warning(f"{ruta.name}: {sin_fecha} periodos no reconocidos (se descartan)")
    df["variable"] = df[col_codigo].map(mapa)
    return df.dropna(subset=["fecha"]).pivot_table(index="fecha", columns="variable",
                                                   values="valor_num", aggfunc="first")


def denton_suma(y_trim, n_meses=3):
    """Desagregación de Denton (primeras diferencias, aditiva): serie mensual lo más suave
    posible cuya suma por trimestre es exactamente y_trim."""
    m, n = len(y_trim), len(y_trim) * n_meses
    A = np.kron(np.eye(m), np.ones((1, n_meses)))                  # suma de 3 meses = trimestre
    D = np.diff(np.eye(n), axis=0)                                  # primeras diferencias
    K = np.block([[2 * D.T @ D, A.T], [A, np.zeros((m, m))]])
    sol = np.linalg.solve(K, np.concatenate([np.zeros(n), y_trim]))
    return sol[:n]


def marcar_atipicos(serie):
    """1 si la variación mensual cae fuera de [Q1 - 3*RIC, Q3 + 3*RIC]."""
    d = serie.diff()
    q1, q3 = d.quantile([0.25, 0.75])
    ric = q3 - q1
    return ((d < q1 - 3 * ric) | (d > q3 + 3 * ric)).astype(int)


def sha256(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


# ----------------------------------------------------------------------------
# 4. EJECUCIÓN
# ----------------------------------------------------------------------------
def main():
    log.info("=" * 70)
    log.info(f"Inicio limpieza | pandas {pd.__version__} | numpy {np.__version__} | "
             f"muestra {FECHA_INICIO} a {FECHA_CORTE}")
    meses = pd.date_range(FECHA_INICIO, FECHA_CORTE, freq="MS")

    # 4.1 Lectura y tipificación de las dos vías
    api = leer_crudo(DIR_CRUDOS / f"datos_crudos_api_{CODIGO}.csv", VIA1)
    scr = leer_crudo(DIR_CRUDOS / f"datos_crudos_scraping_{CODIGO}.csv", VIA2)
    log.info(f"Vía 1 leída: {api.shape[1]} series | Vía 2 leída: {scr.shape[1]} series")

    # 4.2 Inversión privada: trimestral -> mensual (Denton)
    trimestres = pd.date_range(FECHA_INICIO, FECHA_CORTE, freq="QS")
    inv_q = api["inv_priv_real"].reindex(trimestres)
    if inv_q.isna().any():
        sys.exit(f"Faltan trimestres de inversión: {list(inv_q[inv_q.isna()].index.date)}")
    inv_m = pd.Series(denton_suma(inv_q.values), index=meses)
    error = np.abs(inv_m.groupby(inv_m.index.to_period("Q")).sum().values - inv_q.values).max()
    log.info(f"Denton inversión: {len(inv_q)} trimestres -> {len(inv_m)} meses | "
             f"error máximo al reagregar = {error:.2e} | mínimo mensual = {inv_m.min():,.1f}")

    # 4.3 Base mensual ancha (llave común: fecha)
    df = pd.DataFrame(index=meses)
    df.index.name = "fecha"
    df["inv_priv_real"] = inv_m
    for v in ["pbi_idx", "tasa_corp", "tc", "tot", "aux_tasa_interb", "aux_tamn"]:
        df[v] = api[v].reindex(meses)
    for v in VIA2.values():
        df[v] = scr[v].reindex(meses)
    for v in df.columns:
        log.info(f"Faltantes antes de imputar | {v}: {int(df[v].isna().sum())} de {len(df)}")

    # 4.4 Tasa corporativa: retropolación con TAMN y tasa interbancaria
    df["tasa_corp_imputada"] = df["tasa_corp"].isna().astype(int)
    comun = df.dropna(subset=["tasa_corp", "aux_tamn", "aux_tasa_interb"])
    X = np.column_stack([np.ones(len(comun)), comun["aux_tamn"], comun["aux_tasa_interb"]])
    beta, *_ = np.linalg.lstsq(X, comun["tasa_corp"].values, rcond=None)
    ajuste = X @ beta
    r2 = 1 - ((comun["tasa_corp"] - ajuste) ** 2).sum() / ((comun["tasa_corp"] - comun["tasa_corp"].mean()) ** 2).sum()
    faltan = df["tasa_corp"].isna() & df["aux_tamn"].notna() & df["aux_tasa_interb"].notna()
    df.loc[faltan, "tasa_corp"] = (beta[0] + beta[1] * df.loc[faltan, "aux_tamn"]
                                   + beta[2] * df.loc[faltan, "aux_tasa_interb"])
    log.info(f"Retropolación tasa_corp = {beta[0]:.3f} + {beta[1]:.3f}*TAMN + {beta[2]:.3f}*interbancaria "
             f"| R2 = {r2:.3f} | n = {len(comun)} | meses imputados = {int(faltan.sum())} "
             f"| rango imputado = [{df.loc[faltan, 'tasa_corp'].min():.2f}, {df.loc[faltan, 'tasa_corp'].max():.2f}]")

    # 4.5 Expectativa principal: extrapolación constante hacia atrás antes de su primer dato
    df["exp_eco_3m_imputada"] = df["exp_eco_3m"].isna().astype(int)
    primero = df["exp_eco_3m"].first_valid_index()
    df.loc[:primero, "exp_eco_3m"] = df.loc[:primero, "exp_eco_3m"].bfill()
    log.info(f"exp_eco_3m: primer dato publicado {primero:%Y-%m}; "
             f"{int(df['exp_eco_3m_imputada'].sum())} meses previos completados con ese valor")

    # 4.6 Huecos internos en las variables del modelo -> interpolación lineal
    modelo = ["inv_priv_real", "pbi_idx", "tasa_corp", "tc", "tot", "exp_eco_3m"]
    for v in modelo:
        huecos = int(df[v].isna().sum())
        if huecos:
            df[v] = df[v].interpolate(method="linear", limit_area="inside")
            log.info(f"{v}: {huecos} huecos internos interpolados linealmente")
    if df[modelo].isna().any().any():
        sys.exit(f"Quedan faltantes en variables del modelo: {df[modelo].isna().sum().to_dict()}")

    # 4.7 Atípicos (marcados, no eliminados) y dummy COVID
    df["covid"] = ((df.index >= COVID[0]) & (df.index <= COVID[1])).astype(int)
    marcas = pd.DataFrame({v: marcar_atipicos(df[v]) for v in modelo})
    for v in modelo:
        log.info(f"Atípicos marcados en {v}: {int(marcas[v].sum())}")
    df["atipico"] = marcas.max(axis=1)                       # 1 si alguna variable del modelo es atípica ese mes

    # 4.8 Nombres finales (claros, en español) y guardado de la base principal
    df = df.rename(columns=NOMBRES)
    final = df[list(NOMBRES.values())].round(4)
    final.index = final.index.strftime("%Y-%m")
    final.to_csv(SALIDA, encoding="utf-8")
    log.info(f"Guardado {SALIDA.name}: {final.shape[0]} filas x {final.shape[1] + 1} columnas (incluye fecha)")

    # 4.9 Base trimestral (inversión oficial, demás variables en promedio del trimestre)
    trimestre = df.index.to_period("Q")
    promedios = [c for c in list(NOMBRES.values())[1:8]]
    trim = df[promedios].groupby(trimestre).mean()
    trim.insert(0, "inversion_privada", inv_q.values)
    trim["covid"] = df["covid"].groupby(trimestre).max()
    trim.index = trim.index.astype(str)
    trim.index.name = "trimestre"
    trim.round(4).to_csv(SALIDA_TRIM, encoding="utf-8")
    log.info(f"Guardado {SALIDA_TRIM.name}: {trim.shape[0]} trimestres x {trim.shape[1] + 1} columnas")

    # 4.10 Formato largo (una fila por mes y variable)
    fuente = {v: "API BCRPData" for v in list(NOMBRES.values())[:5]}
    fuente.update({v: "Scraping Encuesta BCRP" for v in list(NOMBRES.values())[5:8]})
    largo = (final[list(fuente)].reset_index()
             .melt(id_vars="fecha", var_name="variable", value_name="valor").dropna())
    largo["fuente"] = largo["variable"].map(fuente)
    largo.to_csv(SALIDA_LARGO, index=False, encoding="utf-8")
    log.info(f"Guardado {SALIDA_LARGO.name}: {len(largo)} filas")

    # 4.11 Verificación de requisitos de tamaño y hash
    assert len(final) >= MIN_PERIODOS, f"Solo {len(final)} meses (mínimo {MIN_PERIODOS})"
    assert len(largo) >= MIN_FILAS_LARGO, f"Solo {len(largo)} filas en formato largo"
    log.info(f"Tamaño: {len(final)} periodos mensuales >= {MIN_PERIODOS} y {len(largo)} "
             f"observaciones en formato largo >= {MIN_FILAS_LARGO}: CUMPLE")
    hash_ = sha256(SALIDA)
    log.info(f"SHA-256 de {SALIDA.name}: {hash_}")
    readme = BASE / "README.md"
    if readme.exists():
        texto = readme.read_text(encoding="utf-8")
        texto = re.sub(rf"(SHA-256 de `datos_procesados/{SALIDA.name}`:).*", rf"\1 {hash_}", texto)
        readme.write_text(texto, encoding="utf-8")
        log.info("SHA-256 copiado en README.md")
    log.info("Fin de 03_limpieza_datos.py: OK")


if __name__ == "__main__":
    main()
