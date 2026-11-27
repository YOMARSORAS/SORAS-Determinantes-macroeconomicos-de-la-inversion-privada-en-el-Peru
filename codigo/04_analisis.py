# Nombres y apellidos: YOMAR CRISTHIAN SORAS QUISPE
# Código de matrícula: 2024200530J
# Tema N.º 56 del temario: Métodos de evaluación de inversiones — Determinantes macroeconómicos de la inversión privada en el Perú
# Fecha de extracción: 2026-11-07 (Vía 1) y 2026-11-24 (Vía 2)
"""
04_analisis.py — Análisis empírico según el documento «Diseño del análisis empírico (Tema 56)».
Lee datos_procesados/datos_procesados_<CODIGO>.csv (mensual 2000-01 a 2025-12) y genera en
/salidas las 6 tablas (.csv y .tex) y las 10 figuras (.pdf y .png) del artículo.

Modelo: ARDL con prueba de límites (Pesaran, Shin y Smith, 2001) y corrección de errores (ARDL-ECM)
  ln IPR = b0 + b1 ln PBI + b2 TASA + b3 ln TC + b4 EXP + b5 ln TI
  Rezagos: hasta 12 (inversión) y 6 (explicativas, rezago común), elegidos por BIC.
  11 dummies estacionales, d_covid y d_crisis; caso III; errores HAC (Newey-West).
Bloques:
  A. Descriptiva: Tabla 2, Tabla 3, Figuras 1 a 5.
  B. Inferencial: raíz unitaria (Tabla 4), ARDL-ECM y robustez (Tabla 5, Figuras 7 a 9),
     Granger, diagnóstico e hipótesis (Tabla 6), estabilidad (Figura 10).
  C. Puente con el VAN (Clase 09): Figura 6.
  Tabla 1 (definición y fuente de las variables).
"""

import contextlib
import io
import logging
import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch.unitroot import PhillipsPerron
from scipy import stats
from statsmodels.stats.diagnostic import acorr_breusch_godfrey, het_breuschpagan, linear_reset
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.stattools import jarque_bera
from statsmodels.tsa.ardl import ARDL, UECM
from statsmodels.tsa.stattools import adfuller, grangercausalitytests, kpss, zivot_andrews

warnings.simplefilter("ignore")              # avisos de versión de las librerías (no afectan resultados)

# ----------------------------------------------------------------------------
# 1. PARÁMETROS
# ----------------------------------------------------------------------------
CODIGO = "2024200530J"
SEMILLA = int("".join(c for c in CODIGO if c.isdigit())[-4:])   # últimos 4 dígitos del código
MAX_P, MAX_Q = 12, 6                 # rezagos máximos: inversión y explicativas
HAC = {"cov_type": "HAC", "cov_kwds": {"maxlags": 12}}
COVID = ("2020-03", "2020-06")
CRISIS = ("2008-10", "2009-06")
SUBMUESTRA = "2010-08"               # robustez: solo tasa corporativa observada
ETAPAS = {"E1 2000-2003": ("2000", "2003"), "E2 2004-2013": ("2004", "2013"),
          "E3 2014-2019": ("2014", "2019"), "E4 2020-2021": ("2020", "2021"),
          "E5 2022-2025": ("2022", "2025")}
COLORES_ETAPA = ["#EEF3F8", "#E2ECF5", "#EEF3F8", "#F8E5E5", "#E2ECF5"]
PROYECTO = [-100_000, 30_000, 35_000, 40_000, 45_000]   # proyecto ilustrativo de la Clase 09

# Variables del modelo: nombre corto -> (etiqueta, signo esperado)
X_VARS = {"ln_pbi": ("ln PBI", "+"), "tasa": ("Tasa corporativa", "−"), "ln_tc": ("ln Tipo de cambio", "−"),
          "exp": ("Expectativas", "+"), "ln_ti": ("ln Términos de intercambio", "+")}
Y_VAR = "ln_ipr"
NOMBRE = {"ln_ipr": "ln Inversión privada", **{k: v[0] for k, v in X_VARS.items()}}

BASE = Path(__file__).resolve().parent.parent
DIR_PROC, DIR_SAL = BASE / "datos_procesados", BASE / "salidas"
DIR_SAL.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | 04_analisis | %(message)s",
                    handlers=[logging.FileHandler(BASE / "log_ejecucion.txt", mode="a", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])
log = logging.getLogger()
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 300, "font.size": 9,
                     "axes.spines.top": False, "axes.spines.right": False})
AZUL, NARANJA, GRIS = "#1F4E79", "#C55A11", "#7F7F7F"


# ----------------------------------------------------------------------------
# 2. UTILIDADES
# ----------------------------------------------------------------------------
def guardar_tabla(df, nombre, titulo):
    df.to_csv(DIR_SAL / f"{nombre}.csv", encoding="utf-8")
    df.to_latex(DIR_SAL / f"{nombre}.tex", caption=titulo, label=f"tab:{nombre}", escape=True, na_rep="")
    log.info(f"Tabla guardada: {nombre}")


def guardar_figura(fig, nombre):
    fig.tight_layout()
    fig.savefig(DIR_SAL / f"{nombre}.pdf")
    fig.savefig(DIR_SAL / f"{nombre}.png")
    plt.close(fig)
    log.info(f"Figura guardada: {nombre}")


def estrellas(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def sombrear_etapas(ax):
    for (etq, (a, b)), c in zip(ETAPAS.items(), COLORES_ETAPA):
        ax.axvspan(pd.Timestamp(f"{a}-01-01"), pd.Timestamp(f"{b}-12-31"), color=c, zorder=0)


def cargar():
    m = pd.read_csv(DIR_PROC / f"datos_procesados_{CODIGO}.csv", parse_dates=["fecha"], index_col="fecha")
    m.index.freq = "MS"
    d = pd.DataFrame(index=m.index)
    d["ln_ipr"] = np.log(m["inversion_privada"])
    d["ln_pbi"] = np.log(m["pbi"])
    d["tasa"] = m["tasa_corporativa"]
    d["ln_tc"] = np.log(m["tipo_cambio"])
    d["exp"] = m["expectativa_economia_3m"]
    d["ln_ti"] = np.log(m["terminos_intercambio"])
    d["g_ipr"] = 100 * (d["ln_ipr"] - d["ln_ipr"].shift(12))          # crecimiento interanual (%)
    d["d_covid"] = ((d.index >= COVID[0]) & (d.index <= COVID[1])).astype(int)
    d["d_crisis"] = ((d.index >= CRISIS[0]) & (d.index <= CRISIS[1])).astype(int)
    d["etapa"] = ""
    for etq, (a, b) in ETAPAS.items():
        d.loc[a:b, "etapa"] = etq
    return m, d


# ----------------------------------------------------------------------------
# 3. TABLA 1: DEFINICIÓN Y FUENTE DE LAS VARIABLES
# ----------------------------------------------------------------------------
def tabla1():
    filas = [
        ("Inversión privada real (ln_ipr)", "Inversión bruta fija privada, mensualizada por Denton", "Millones de S/ 2007 (ln)", "Trimestral → mensual", "BCRP, PN02533AQ", "API", "Dependiente"),
        ("PBI (ln_pbi)", "Producto bruto interno real", "Índice 2007=100 (ln)", "Mensual", "BCRP, PN01770AM", "API", "+"),
        ("Tasa corporativa (tasa)", "Tasa preferencial corporativa a 90 días en MN (retropolada antes de ago-2010)", "% anual", "Mensual", "BCRP/SBS, PN07809NM", "API", "−"),
        ("Tipo de cambio (ln_tc)", "Interbancario venta, promedio del mes", "S/ por US$ (ln)", "Mensual", "BCRP, PN01206PM", "API", "−"),
        ("Expectativas (exp)", "Índice de expectativas de la economía a 3 meses", "Puntos 0-100", "Mensual", "BCRP, Encuesta de Expectativas, PD38045AM", "Web scraping", "+"),
        ("Términos de intercambio (ln_ti)", "Índice de términos de intercambio", "Índice 2007=100 (ln)", "Mensual", "BCRP, PN38923BM", "API", "+"),
    ]
    t = pd.DataFrame(filas, columns=["Variable", "Definición", "Unidad", "Frecuencia", "Fuente", "Vía", "Signo esperado"]).set_index("Variable")
    guardar_tabla(t, "tabla1_variables", "Definición y fuente de las variables")


# ----------------------------------------------------------------------------
# 4. BLOQUE A: ESTADÍSTICA DESCRIPTIVA
# ----------------------------------------------------------------------------
def descriptiva(m, d):
    cols = {"inversion_privada": "Inversión privada (mill. S/ 2007)", "pbi": "PBI (2007=100)",
            "tasa_corporativa": "Tasa corporativa (%)", "tipo_cambio": "Tipo de cambio (S/ por US$)",
            "expectativa_economia_3m": "Expectativas (puntos)", "terminos_intercambio": "Términos de intercambio (2007=100)"}
    serie = {cols[c]: m[c] for c in cols}
    serie["Crecimiento interanual de la inversión (%)"] = d["g_ipr"]
    filas = {}
    for k, s in serie.items():
        s = s.dropna()
        filas[k] = {"N": len(s), "Media": s.mean(), "Mediana": s.median(), "DE": s.std(), "Mínimo": s.min(),
                    "Máximo": s.max(), "CV (%)": 100 * s.std() / abs(s.mean()), "Asimetría": stats.skew(s),
                    "Curtosis": stats.kurtosis(s, fisher=False)}
    t2 = pd.DataFrame(filas).T.round(3)
    t2["N"] = t2["N"].astype(int)
    guardar_tabla(t2, "tabla2_descriptivos", "Estadísticos descriptivos, enero 2000 - diciembre 2025")

    # Tabla 3: Pearson con estrellas
    vs = ["ln_ipr"] + list(X_VARS)
    corto = {"ln_ipr": "Inversión", "ln_pbi": "PBI", "tasa": "Tasa", "ln_tc": "TC", "exp": "Expectativas", "ln_ti": "TI"}
    r = pd.DataFrame(index=[corto[v] for v in vs], columns=[corto[v] for v in vs], dtype=object)
    rnum = pd.DataFrame(index=r.index, columns=r.columns, dtype=float)
    for a in vs:
        for b in vs:
            rr, pp = stats.pearsonr(d[a], d[b])
            rnum.loc[corto[a], corto[b]] = rr
            r.loc[corto[a], corto[b]] = f"{rr:.3f}{estrellas(pp) if a != b else ''}"
    guardar_tabla(r, "tabla3_correlaciones", "Matriz de correlaciones de Pearson (* p<0.10, ** p<0.05, *** p<0.01)")
    vif = [variance_inflation_factor(sm.add_constant(d[list(X_VARS)]).values, i + 1) for i in range(len(X_VARS))]
    log.info("VIF: " + ", ".join(f"{NOMBRE[v]}={x:.2f}" for v, x in zip(X_VARS, vif)))

    # Figura 1: evolución de las 6 variables con etapas
    fig, ejes = plt.subplots(3, 2, figsize=(7.5, 7.2), sharex=True)
    for ax, (c, etq) in zip(ejes.flat, cols.items()):
        sombrear_etapas(ax)
        ax.plot(m.index, m[c], color=AZUL, lw=1)
        ax.set_title(etq, fontsize=9)
    for etq_e, (a, b) in ETAPAS.items():
        ejes[0, 0].text(pd.Timestamp(f"{a}-03-01"), ejes[0, 0].get_ylim()[1], etq_e.split()[0], fontsize=7, va="top")
    fig.suptitle("Figura 1. Evolución de las variables, 2000-2025 (etapas sombreadas)", fontsize=10)
    guardar_figura(fig, "figura1_evolucion")

    # Figura 2: crecimiento de la inversión y tasa corporativa
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 4.8), sharex=True)
    for ax in (a1, a2):
        sombrear_etapas(ax)
    a1.plot(d.index, d["g_ipr"], color=AZUL, lw=1.1)
    a1.axhline(0, color=GRIS, lw=0.7)
    a1.set_ylabel("Inversión: crec. interanual (%)")
    a2.plot(d.index, d["tasa"], color=NARANJA, lw=1.1)
    imp = m.index[m["tasa_imputada"] == 1]
    a2.axvspan(imp.min(), imp.max(), color="none", hatch="///", edgecolor=GRIS, lw=0, label="Tasa reconstruida")
    a2.set_ylabel("Tasa corporativa (%)")
    a2.legend(frameon=False, fontsize=7)
    fig.suptitle("Figura 2. Inversión privada y tasa de interés corporativa", fontsize=10)
    guardar_figura(fig, "figura2_inversion_tasa")

    # Figura 3: cajas por etapa + Kruskal-Wallis
    grupos = [d.loc[d["etapa"] == e, "g_ipr"].dropna() for e in ETAPAS]
    kw = stats.kruskal(*grupos)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.boxplot(grupos, patch_artist=True,
               boxprops={"facecolor": "#DCE6F1", "color": AZUL}, medianprops={"color": NARANJA, "lw": 1.5})
    ax.set_xticks(range(1, len(ETAPAS) + 1), list(ETAPAS))
    ax.axhline(0, color=GRIS, lw=0.7, ls=":")
    ax.set_ylabel("Crecimiento interanual de la inversión (%)")
    ax.set_title(f"Figura 3. Crecimiento de la inversión por etapas (Kruskal-Wallis: H = {kw.statistic:.2f}; p = {kw.pvalue:.4f})", fontsize=9)
    guardar_figura(fig, "figura3_etapas")
    log.info(f"Kruskal-Wallis entre etapas: H = {kw.statistic:.3f}, p = {kw.pvalue:.4f}")

    # Figura 4: mapa de calor
    fig, ax = plt.subplots(figsize=(5.6, 4.6))
    im = ax.imshow(rnum.values.astype(float), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(rnum)), rnum.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(rnum)), rnum.index)
    for i in range(len(rnum)):
        for j in range(len(rnum)):
            v = rnum.iloc[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=8, color="white" if abs(v) > 0.6 else "black")
    fig.colorbar(im, ax=ax, shrink=0.8, label="r de Pearson")
    ax.set_title("Figura 4. Correlación de Pearson", fontsize=10)
    guardar_figura(fig, "figura4_correlaciones")

    # Figura 5: correlograma cruzado exp(t-k) vs crecimiento de la inversión (t)
    z = d[["exp", "g_ipr"]].dropna()
    ks = range(-12, 13)
    cc = [z["exp"].shift(k).corr(z["g_ipr"]) for k in ks]
    banda = 1.96 / np.sqrt(len(z))
    fig, ax = plt.subplots(figsize=(7, 3.3))
    ax.bar(list(ks), cc, color=[NARANJA if k > 0 else AZUL for k in ks])
    ax.axhline(banda, color=GRIS, ls="--", lw=0.8)
    ax.axhline(-banda, color=GRIS, ls="--", lw=0.8)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("k (meses): k > 0 = expectativas de hace k meses frente a la inversión de hoy")
    ax.set_ylabel("Correlación")
    kmax = list(ks)[int(np.nanargmax(cc))]
    ax.set_title(f"Figura 5. Las expectativas se adelantan a la inversión (máxima correlación en k = {kmax})", fontsize=9)
    guardar_figura(fig, "figura5_correlograma")
    log.info(f"Correlograma cruzado: máxima correlación en k = {kmax} meses (r = {np.nanmax(cc):.3f})")


# ----------------------------------------------------------------------------
# 5. BLOQUE B1: RAÍZ UNITARIA (TABLA 4)
# ----------------------------------------------------------------------------
def raiz_unitaria(d):
    filas = []
    for v in [Y_VAR] + list(X_VARS):
        f = {"Variable": NOMBRE[v]}
        for etq, s in [("niv", d[v]), ("dif", d[v].diff())]:
            s = s.dropna()
            f[f"ADF {etq}"] = adfuller(s, regression="c", autolag="AIC")[1]
            f[f"PP {etq}"] = PhillipsPerron(s, trend="c").pvalue
            f[f"KPSS {etq}"] = kpss(s, regression="c", nlags="auto")[1]
        za = zivot_andrews(d[v].dropna(), regression="c", autolag="AIC")
        f["ZA estad."] = za[0]
        f["ZA p"] = za[1]
        f["Quiebre ZA"] = d[v].dropna().index[za[4]].strftime("%Y-%m")
        votos_niv = (f["ADF niv"] < 0.05) + (f["PP niv"] < 0.05) + (f["KPSS niv"] > 0.05)
        estac_dif = f["ADF dif"] < 0.05 or f["PP dif"] < 0.05
        f["Conclusión"] = "I(0)" if votos_niv >= 2 else ("I(1)" if estac_dif else "I(2)?")
        filas.append(f)
        log.info(f"Raíz unitaria {NOMBRE[v]}: ADF={f['ADF niv']:.3f} PP={f['PP niv']:.3f} KPSS={f['KPSS niv']:.3f} "
                 f"(niveles) | ZA quiebre {f['Quiebre ZA']} | {f['Conclusión']}")
    t4 = pd.DataFrame(filas).set_index("Variable")
    num = t4.select_dtypes("number").columns
    t4[num] = t4[num].round(3)
    guardar_tabla(t4, "tabla4_raiz_unitaria",
                  "Pruebas de raíz unitaria (p-valores de ADF, PP y KPSS en niveles y diferencias; Zivot-Andrews con quiebre)")
    if (t4["Conclusión"] == "I(2)?").any():
        log.warning("Alguna variable parece I(2): revisar antes de aplicar ARDL")
    return t4


# ----------------------------------------------------------------------------
# 6. BLOQUE B2: ARDL-ECM
# ----------------------------------------------------------------------------
def estimar_ardl(d, desde=None, etiqueta="Base"):
    """Elige p (1..12) y q común (0..6) por BIC, estima ARDL y UECM con HAC y calcula el largo plazo."""
    z = d.loc[desde:] if desde else d
    y, X, fx = z[Y_VAR], z[list(X_VARS)], z[["d_covid", "d_crisis"]]
    fx = fx.loc[:, fx.sum() > 0]                                   # quita dummies sin variación en la submuestra
    mejor = None
    for p in range(1, MAX_P + 1):
        for q in range(0, MAX_Q + 1):
            r = ARDL(y, p, X, q, trend="c", fixed=fx, seasonal=True, hold_back=MAX_P).fit()
            if mejor is None or r.bic < mejor[0]:
                mejor = (r.bic, p, q)
    _, p, q = mejor
    q = max(q, 1)                                                  # el ECM necesita al menos un rezago en X
    modelo = ARDL(y, p, X, q, trend="c", fixed=fx, seasonal=True)
    ardl = modelo.fit(**HAC)
    uecm = UECM.from_ardl(modelo).fit(**HAC)
    bt = UECM.from_ardl(modelo).fit().bounds_test(case=3)
    lam = uecm.params[f"{Y_VAR}.L1"]
    lr, se = {}, {}
    cov = uecm.cov_params()
    for v in X_VARS:
        pi = uecm.params[f"{v}.L1"]
        lr[v] = -pi / lam
        g = pd.Series(0.0, index=uecm.params.index)
        g[f"{v}.L1"], g[f"{Y_VAR}.L1"] = -1 / lam, pi / lam ** 2      # método delta
        se[v] = float(np.sqrt(g @ cov @ g))
    pval = {v: 2 * (1 - stats.norm.cdf(abs(lr[v] / se[v]))) for v in X_VARS}
    log.info(f"ARDL {etiqueta}: ARDL({p},{q}) | n = {int(ardl.nobs)} | F bounds = {bt.statistic:.3f} | "
             f"lambda = {lam:.4f} | " + ", ".join(f"{v}={lr[v]:.4f}" for v in X_VARS))
    return {"p": p, "q": q, "modelo": modelo, "ardl": ardl, "uecm": uecm, "bt": bt, "lam": lam,
            "lam_p": uecm.pvalues[f"{Y_VAR}.L1"], "lr": lr, "se": se, "pval": pval, "n": int(ardl.nobs),
            "r2": uecm.rsquared, "etiqueta": etiqueta}


def estimar_dols(d, k=2):
    """Mínimos cuadrados dinámicos: niveles + adelantos y rezagos de las diferencias (±k), HAC."""
    X = d[list(X_VARS)].copy()
    for v in X_VARS:
        for j in range(-k, k + 1):
            X[f"d{v}_{j}"] = d[v].diff().shift(j)
    X[["d_covid", "d_crisis"]] = d[["d_covid", "d_crisis"]]
    z = pd.concat([d[Y_VAR], X], axis=1).dropna()
    r = sm.OLS(z[Y_VAR], sm.add_constant(z.drop(columns=Y_VAR))).fit(**HAC)
    log.info("DOLS: " + ", ".join(f"{v}={r.params[v]:.4f}" for v in X_VARS))
    return {"lr": {v: r.params[v] for v in X_VARS}, "se": {v: r.bse[v] for v in X_VARS},
            "pval": {v: r.pvalues[v] for v in X_VARS}, "n": int(r.nobs), "r2": r.rsquared}


def tabla5(base, sub, dols):
    def celda(c, v):
        return f"{c['lr'][v]:.3f}{estrellas(c['pval'][v])} ({c['se'][v]:.3f})"
    filas = []
    for v in X_VARS:
        filas.append(["A. Largo plazo", NOMBRE[v], celda(base, v), celda(sub, v), celda(dols, v)])
    u = base["uecm"]
    for v in X_VARS:
        n = f"D.{v}.L0"
        if n in u.params:
            filas.append(["B. Corto plazo", f"Δ {NOMBRE[v]}", f"{u.params[n]:.3f}{estrellas(u.pvalues[n])} ({u.bse[n]:.3f})",
                          _sr(sub, n), ""])
    filas.append(["B. Corto plazo", "λ (ECT t-1)", f"{base['lam']:.3f}{estrellas(base['lam_p'])} ({u.bse[f'{Y_VAR}.L1']:.3f})",
                  f"{sub['lam']:.3f}{estrellas(sub['lam_p'])}", ""])
    for c in (base, sub):
        c["vida_media"] = np.log(0.5) / np.log(1 + c["lam"]) if -1 < c["lam"] < 0 else np.nan
    cv = base["bt"].critical_values
    filas += [
        ["C. Bounds test", "Estadístico F", f"{base['bt'].statistic:.3f}", f"{sub['bt'].statistic:.3f}", ""],
        ["C. Bounds test", "Límites 5 % [I(0); I(1)]", f"[{cv.loc[95.0, 'lower']:.2f}; {cv.loc[95.0, 'upper']:.2f}]", "", ""],
        ["C. Bounds test", "p-valor (límite I(1))", f"{base['bt'].pvalue['upper']:.4f}", f"{sub['bt'].pvalue['upper']:.4f}", ""],
        ["C. Ajuste", "Meses para corregir la mitad", f"{base['vida_media']:.1f}", f"{sub['vida_media']:.1f}", ""],
        ["C. Ajuste", "Orden ARDL (p, q)", f"({base['p']}, {base['q']})", f"({sub['p']}, {sub['q']})", "±2 adel./rez."],
        ["C. Ajuste", "R²", f"{base['r2']:.3f}", f"{sub['r2']:.3f}", f"{dols['r2']:.3f}"],
        ["C. Ajuste", "N", str(base["n"]), str(sub["n"]), str(dols["n"])],
    ]
    t5 = pd.DataFrame(filas, columns=["Panel", "Variable", "(1) Base 2000-2025", "(2) 2010-2025", "(3) DOLS"]).set_index(["Panel", "Variable"])
    guardar_tabla(t5, "tabla5_ardl_ecm",
                  "Estimación del modelo ARDL-ECM (coeficiente, error estándar HAC entre paréntesis; * p<0.10, ** p<0.05, *** p<0.01)")


def _sr(c, n):
    u = c["uecm"]
    return f"{u.params[n]:.3f}{estrellas(u.pvalues[n])}" if n in u.params else ""


def figuras_modelo(base):
    # Figura 7: bounds test
    cv, F = base["bt"].critical_values, base["bt"].statistic
    niveles = [90.0, 95.0, 99.0]
    x = np.arange(len(niveles))
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.bar(x - 0.2, [cv.loc[n, "lower"] for n in niveles], 0.4, color="#BDD7EE", label="Límite I(0)")
    ax.bar(x + 0.2, [cv.loc[n, "upper"] for n in niveles], 0.4, color=AZUL, label="Límite I(1)")
    ax.axhline(F, color=NARANJA, lw=2, label=f"F calculado = {F:.2f}")
    ax.set_xticks(x, ["10 %", "5 %", "1 %"])
    ax.set_xlabel("Nivel de significancia")
    ax.legend(frameon=False)
    ax.set_title("Figura 7. Prueba de límites de Pesaran, Shin y Smith (caso III)", fontsize=10)
    guardar_figura(fig, "figura7_bounds_test")

    # Figura 8: efectos de largo plazo ante choques interpretables (% de cambio en la inversión)
    choque = {"ln_pbi": (1, "PBI +1 %"), "tasa": (100, "Tasa +1 p.p."), "ln_tc": (1, "Tipo de cambio +1 %"),
              "exp": (1000, "Expectativas +10 puntos"), "ln_ti": (1, "Términos de intercambio +1 %")}
    ef = [base["lr"][v] * choque[v][0] for v in X_VARS]
    ic = [1.96 * base["se"][v] * choque[v][0] for v in X_VARS]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    yy = np.arange(len(ef))[::-1]
    ax.errorbar(ef, yy, xerr=ic, fmt="o", color=AZUL, ecolor=GRIS, capsize=4)
    ax.axvline(0, color="black", lw=0.7)
    ax.set_yticks(yy, [choque[v][1] for v in X_VARS])
    ax.set_xlabel("Cambio de largo plazo en la inversión privada (%), con IC 95 %")
    ax.set_title("Figura 8. Efectos de largo plazo", fontsize=10)
    guardar_figura(fig, "figura8_largo_plazo")

    # Figura 9: multiplicadores dinámicos acumulados (24 meses) ante choques permanentes
    par = base["ardl"].params
    phi = [par.get(f"{Y_VAR}.L{i}", 0.0) for i in range(1, base["p"] + 1)]
    choques = {"tasa": (1, "Tasa +1 p.p.", NARANJA), "ln_tc": (0.01, "Tipo de cambio +1 %", GRIS),
               "exp": (10, "Expectativas +10 puntos", AZUL)}
    H = 24
    fig, ax = plt.subplots(figsize=(6.8, 3.6))
    for v, (tam, etq, col) in choques.items():
        theta = [par.get(f"{v}.L{j}", 0.0) for j in range(0, base["q"] + 1)]
        resp = np.zeros(H + 1)
        for t in range(H + 1):
            resp[t] = sum(phi[i] * resp[t - 1 - i] for i in range(len(phi)) if t - 1 - i >= 0) \
                + tam * sum(theta[j] for j in range(len(theta)) if j <= t)
        ax.plot(range(H + 1), 100 * resp, color=col, lw=1.8, label=etq)
        ax.axhline(100 * base["lr"][v] * tam, color=col, ls=":", lw=0.9)
    ax.axhline(0, color="black", lw=0.6)
    ax.set_xlabel("Meses después del choque")
    ax.set_ylabel("Cambio acumulado en la inversión (%)")
    ax.legend(frameon=False)
    ax.set_title("Figura 9. Respuesta de la inversión mes a mes (líneas punteadas: efecto de largo plazo)", fontsize=9)
    guardar_figura(fig, "figura9_multiplicadores")

    # Figura 10: CUSUM y CUSUMSQ (residuos recursivos del ARDL estimado por MCO)
    mod = base["modelo"]
    w = residuos_recursivos(np.asarray(mod._y, float), np.asarray(mod._x, float))
    nres = len(w)
    cusum = np.cumsum(w) / np.std(w, ddof=1)
    t = np.arange(1, nres + 1)
    banda = 0.948 * np.sqrt(nres) * (1 + 2 * t / nres)
    sq = np.cumsum(w ** 2) / np.sum(w ** 2)
    c0 = 1.358 / np.sqrt(nres / 2)                                 # aproximación asintótica al 5 %
    fechas = base["ardl"].fittedvalues.index[-nres:]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(8, 3.2))
    a1.plot(fechas, cusum, color=AZUL)
    a1.plot(fechas, banda, color=NARANJA, ls="--")
    a1.plot(fechas, -banda, color=NARANJA, ls="--")
    a1.set_title("CUSUM", fontsize=9)
    a2.plot(fechas, sq, color=AZUL)
    a2.plot(fechas, t / nres + c0, color=NARANJA, ls="--")
    a2.plot(fechas, t / nres - c0, color=NARANJA, ls="--")
    a2.set_title("CUSUMSQ", fontsize=9)
    fig.suptitle("Figura 10. Estabilidad de los coeficientes (bandas al 5 %)", fontsize=10)
    guardar_figura(fig, "figura10_cusum")
    dentro = bool(np.all(np.abs(cusum) <= banda)), bool(np.all(np.abs(sq - t / nres) <= c0))
    log.info(f"Estabilidad: CUSUM dentro de bandas = {dentro[0]} | CUSUMSQ dentro de bandas = {dentro[1]}")
    return dentro


def residuos_recursivos(y, X):
    """Residuos recursivos estandarizados (Brown, Durbin y Evans, 1975). Se usa la pseudo-inversa
    porque las dummies (crisis, COVID) valen cero al inicio de la muestra."""
    k, w = X.shape[1], []
    for t in range(k + 1, len(y)):
        Xt, yt = X[:t], y[:t]
        XtX_inv = np.linalg.pinv(Xt.T @ Xt)
        b = XtX_inv @ Xt.T @ yt
        x = X[t]
        w.append((y[t] - x @ b) / np.sqrt(1 + x @ XtX_inv @ x))
    return np.array(w)


# ----------------------------------------------------------------------------
# 7. BLOQUE B3: GRANGER, DIAGNÓSTICO E HIPÓTESIS (TABLA 6)
# ----------------------------------------------------------------------------
def tabla6(d, base, estable):
    filas = []
    dy = d[Y_VAR].diff()
    granger = {}
    for v in ["exp", "tasa", "ln_tc"]:
        z = pd.concat([dy, d[v].diff()], axis=1).dropna()
        with contextlib.redirect_stdout(io.StringIO()):            # silencia la impresión de la función
            res = grangercausalitytests(z, maxlag=[6])[6][0]["ssr_ftest"]
        granger[v] = res[1]
        filas.append(["A. Granger (6 rezagos)", f"{NOMBRE[v]} → Inversión", f"F = {res[0]:.3f}", f"{res[1]:.4f}",
                      "Sí la anticipa" if res[1] < 0.05 else "No la anticipa"])
    ols = sm.OLS(base["modelo"]._y, base["modelo"]._x).fit()
    bg = acorr_breusch_godfrey(ols, nlags=12)
    bp = het_breuschpagan(ols.resid, ols.model.exog)
    jb = jarque_bera(ols.resid)
    reset = linear_reset(ols, power=2, use_f=True)
    for nombre, est, p, ok in [("Breusch-Godfrey (12): autocorrelación", bg[2], bg[3], "Sin autocorrelación"),
                               ("Breusch-Pagan: heterocedasticidad", bp[0], bp[1], "Homocedástico"),
                               ("Jarque-Bera: normalidad", jb[0], jb[1], "Residuos normales"),
                               ("RESET de Ramsey: forma funcional", float(reset.fvalue), float(reset.pvalue), "Bien especificado")]:
        filas.append(["B. Diagnóstico de residuos", nombre, f"{est:.3f}", f"{p:.4f}",
                      ok if p > 0.05 else "Problema (se usan errores HAC)"])
    filas.append(["B. Diagnóstico de residuos", "CUSUM / CUSUMSQ", "", "",
                  f"{'Estable' if estable[0] else 'Inestable'} / {'Estable' if estable[1] else 'Inestable'}"])
    lr, pv = base["lr"], base["pval"]
    bt = base["bt"]
    h = {
        "H1: la tasa reduce la inversión": lr["tasa"] < 0 and pv["tasa"] < 0.05,
        "H2: la depreciación reduce la inversión": lr["ln_tc"] < 0 and pv["ln_tc"] < 0.05,
        "H3: las expectativas aumentan y anticipan la inversión": lr["exp"] > 0 and pv["exp"] < 0.05 and granger["exp"] < 0.05,
        "H4: existe equilibrio de largo plazo": bt.statistic > bt.critical_values.loc[95.0, "upper"] and -1 < base["lam"] < 0 and base["lam_p"] < 0.05,
    }
    evid = {"H1: la tasa reduce la inversión": f"β = {lr['tasa']:.4f}, p = {pv['tasa']:.4f}",
            "H2: la depreciación reduce la inversión": f"β = {lr['ln_tc']:.4f}, p = {pv['ln_tc']:.4f}",
            "H3: las expectativas aumentan y anticipan la inversión": f"β = {lr['exp']:.4f}, p = {pv['exp']:.4f}; Granger p = {granger['exp']:.4f}",
            "H4: existe equilibrio de largo plazo": f"F = {bt.statistic:.2f}; λ = {base['lam']:.3f}"}
    for k, ok in h.items():
        filas.append(["C. Contraste de hipótesis", k, evid[k], "", "ACEPTADA" if ok else "RECHAZADA"])
        log.info(f"{k}: {'ACEPTADA' if ok else 'RECHAZADA'} ({evid[k]})")
    t6 = pd.DataFrame(filas, columns=["Panel", "Prueba", "Estadístico", "p-valor", "Conclusión"]).set_index(["Panel", "Prueba"])
    guardar_tabla(t6, "tabla6_granger_diagnostico_hipotesis", "Causalidad de Granger, diagnóstico de residuos y contraste de hipótesis")


# ----------------------------------------------------------------------------
# 8. BLOQUE C: PUENTE CON EL VAN (FIGURA 6)
# ----------------------------------------------------------------------------
def figura6_van(m, d):
    flujos = np.array(PROYECTO, dtype=float)
    t = np.arange(len(flujos))
    k = m["tasa_corporativa"] / 100
    van = k.apply(lambda r: float(np.sum(flujos / (1 + r) ** t)))
    tir = _tir(flujos)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.5, 5), sharex=True)
    for ax in (a1, a2):
        sombrear_etapas(ax)
    a1.plot(van.index, van / 1000, color=AZUL, lw=1.2)
    a1.axhline(0, color="black", lw=0.7)
    a1.set_ylabel("VAN (miles de S/)")
    a1.set_title(f"VAN del proyecto representativo descontado con la tasa corporativa de cada mes (TIR = {100 * tir:.1f} %)", fontsize=9)
    a2.plot(d.index, d["g_ipr"], color=NARANJA, lw=1.1)
    a2.axhline(0, color="black", lw=0.7)
    a2.set_ylabel("Inversión: crec. interanual (%)")
    fig.suptitle("Figura 6. El criterio del VAN aplicado a 26 años de datos reales", fontsize=10)
    guardar_figura(fig, "figura6_van_proyecto")
    r = van.corr(d["g_ipr"])
    log.info(f"VAN proyecto representativo: mín = {van.min():,.0f} ({van.idxmin():%Y-%m}), máx = {van.max():,.0f} "
             f"({van.idxmax():%Y-%m}); meses con VAN < 0: {int((van < 0).sum())}; TIR = {100 * tir:.2f} %; "
             f"correlación VAN vs crecimiento de la inversión = {r:.3f}")


def _tir(f):
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if np.sum(f / (1 + mid) ** np.arange(len(f))) > 0:
            lo = mid
        else:
            hi = mid
    return mid


# ----------------------------------------------------------------------------
# 9. EJECUCIÓN
# ----------------------------------------------------------------------------
def main():
    log.info("=" * 70)
    log.info(f"Inicio análisis | semilla = {SEMILLA:04d} | ARDL p<= {MAX_P}, q<= {MAX_Q}, BIC, caso III, HAC")
    np.random.seed(SEMILLA)
    m, d = cargar()
    tabla1()
    descriptiva(m, d)
    raiz_unitaria(d)
    base = estimar_ardl(d, etiqueta="Base 2000-2025")
    sub = estimar_ardl(d, desde=SUBMUESTRA, etiqueta="Submuestra 2010-2025")
    dols = estimar_dols(d)
    tabla5(base, sub, dols)
    estable = figuras_modelo(base)
    tabla6(d, base, estable)
    figura6_van(m, d)
    log.info("Fin de 04_analisis.py: OK (6 tablas y 10 figuras en /salidas)")


if __name__ == "__main__":
    main()
