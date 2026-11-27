# Nombres y apellidos: YOMAR CRISTHIAN SORAS QUISPE
# Código de matrícula: 2024200530J
# Tema N.º 56 del temario: Métodos de evaluación de inversiones — Determinantes macroeconómicos de la inversión privada en el Perú
# Fecha de extracción: 2026-11-07 (Vía 1) y 2026-11-24 (Vía 2)
"""
04_analisis.py — Análisis empírico según el «Diseño del análisis empírico (Tema 56)».
Lee datos_procesados/datos_procesados_<CODIGO>.csv (mensual 2000-01 a 2025-12) y genera en
/salidas 6 tablas (.csv, .tex e imagen) y 11 figuras (.pdf vectorial y .png a 600 ppp).

Modelo: ARDL con prueba de límites (Pesaran, Shin y Smith, 2001) y corrección de errores (ARDL-ECM)
  ln IPR = b0 + b1 ln PBI + b2 TASA + b3 ln TC + b4 EXP + b5 ln TI
  Rezagos: hasta 12 (inversión) y 6 (explicativas, rezago común), elegidos por BIC.
  11 dummies estacionales, d_covid y d_crisis; caso III; errores HAC (Newey-West).
Estilo de figuras (formato de revista): sin título dentro de la imagen (va en el pie de figura
de LaTeX), paleta apta para daltónicos (Okabe-Ito), ancho de doble columna (17.8 cm),
letra de 8 pt, paneles rotulados (a), (b)... y eventos sombreados (crisis 2008-09 y COVID-19).
"""

import contextlib
import io
import logging
import re
import sys
import textwrap
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.ticker
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
SEMILLA = int("".join(c for c in CODIGO if c.isdigit())[-4:])   # últimos 4 dígitos del código: 0530
MAX_P, MAX_Q = 12, 6                 # rezagos máximos: inversión y explicativas
HAC = {"cov_type": "HAC", "cov_kwds": {"maxlags": 12}}
COVID = ("2020-03", "2020-06")
CRISIS = ("2008-10", "2009-06")
SUBMUESTRA = "2010-08"               # robustez: solo tasa corporativa observada
N_BOOT = 1000                        # simulaciones para las bandas de los multiplicadores
ETAPAS = {"E1": ("2000", "2003"), "E2": ("2004", "2013"), "E3": ("2014", "2019"),
          "E4": ("2020", "2021"), "E5": ("2022", "2025")}
NOMBRE_ETAPA = {"E1": "E1\n2000-03", "E2": "E2\n2004-13", "E3": "E3\n2014-19",
                "E4": "E4\n2020-21", "E5": "E5\n2022-25"}
PROYECTO = [-100_000, 30_000, 35_000, 40_000, 45_000]   # proyecto ilustrativo de la Clase 09

X_VARS = {"ln_pbi": "ln PBI", "tasa": "Tasa corporativa", "ln_tc": "ln Tipo de cambio",
          "exp": "Expectativas", "ln_ti": "ln Términos de intercambio"}
Y_VAR = "ln_ipr"
NOMBRE = {"ln_ipr": "ln Inversión privada", **X_VARS}

BASE = Path(__file__).resolve().parent.parent
DIR_PROC, DIR_SAL = BASE / "datos_procesados", BASE / "salidas"
DIR_SAL.mkdir(exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | 04_analisis | %(message)s",
                    handlers=[logging.FileHandler(BASE / "log_ejecucion.txt", mode="a", encoding="utf-8"),
                              logging.StreamHandler(sys.stdout)])
log = logging.getLogger()
for ruidoso in ("fontTools", "matplotlib"):                 # evita mensajes técnicos al guardar los PDF
    logging.getLogger(ruidoso).setLevel(logging.WARNING)

# ----------------------------------------------------------------------------
# 2. ESTILO DE LAS FIGURAS (formato de revista científica)
# ----------------------------------------------------------------------------
ANCHO_DOBLE, ANCHO_SIMPLE = 7.0, 3.5          # pulgadas: doble columna (17.8 cm) y simple (8.9 cm)
C = {"inversion": "#0B3C5D", "pbi": "#009E73", "tasa": "#D55E00", "tc": "#CC79A7",
     "exp": "#E69F00", "ti": "#56B4E9", "gris": "#8C8C8C", "evento": "#D9D9D9", "neg": "#D55E00"}
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8, "axes.titlesize": 8.5, "axes.titleweight": "bold",
    "axes.labelsize": 8, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5, "legend.fontsize": 7.5,
    "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": "#E6E6E6", "grid.linewidth": 0.5,
    "lines.linewidth": 1.1, "legend.frameon": False, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "savefig.dpi": 600, "savefig.bbox": "tight", "savefig.pad_inches": 0.03,
    "pdf.fonttype": 42, "ps.fonttype": 42, "figure.dpi": 110,
})


# ----------------------------------------------------------------------------
# 3. UTILIDADES
# ----------------------------------------------------------------------------
def guardar_tabla(df, nombre, titulo):
    """Guarda la tabla en .csv, en .tex (formato booktabs para el artículo) y como imagen
    (.pdf y .png) con estilo de revista, lista para el artículo o la exposición."""
    df.to_csv(DIR_SAL / f"{nombre}.csv", encoding="utf-8")
    df.to_latex(DIR_SAL / f"{nombre}.tex", caption=titulo, label=f"tab:{nombre}", escape=True, na_rep="")
    tabla_imagen(df, nombre)
    log.info(f"Tabla guardada: {nombre} (.csv, .tex, .pdf, .png)")


def tabla_imagen(df, nombre, max_car=30):
    """Dibuja la tabla al estilo de las revistas: solo tres filetes horizontales (superior, bajo el
    encabezado e inferior), sin líneas verticales, encabezado en negrita y texto ajustado."""
    t = df.reset_index()
    for c in t.columns[: df.index.nlevels]:                  # no repetir el nombre del panel
        t[c] = t[c].where(t[c] != t[c].shift(), "")
    t = t.astype(str).replace({"nan": "", "None": ""})
    envolver = lambda x, w: textwrap.fill(str(x), w) if len(str(x)) > w else str(x)
    filas = [[envolver(c, max_car) for c in t.columns]] + [[envolver(x, max_car) for x in fila] for fila in t.values]
    ancho_col = [max(max(len(l) for l in f[j].split("\n")) for f in filas) + 2 for j in range(len(t.columns))]
    lineas = [max(c.count("\n") + 1 for c in f) for f in filas]
    es_num = lambda x: bool(re.match(r"^\s*[-−+]?[\d\[(]", x))   # columna numérica: alinear a la derecha
    derecha = [j >= df.index.nlevels and np.mean([es_num(x) for x in t.iloc[:, j] if x]) > 0.5
               for j in range(len(t.columns))]
    pulg_car, pulg_linea = 0.058, 0.17
    fig_w, fig_h = sum(ancho_col) * pulg_car, sum(lineas) * pulg_linea + 0.15
    fig = plt.figure(figsize=(fig_w, fig_h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    ax.set_xlim(0, sum(ancho_col))
    ax.set_ylim(sum(lineas) + 0.6, 0)
    y = 0.3
    for i, (f, nl) in enumerate(zip(filas, lineas)):
        if i > 0 and i % 2 == 0:
            ax.axhspan(y, y + nl, color="#F5F7FA", lw=0, zorder=0)
        x = 0
        for j, celda in enumerate(f):
            numerico = derecha[j]
            ax.text(x + (ancho_col[j] - 1 if numerico else 0.5), y + nl / 2, celda,
                    ha="right" if numerico else "left", va="center", fontsize=7,
                    fontweight="bold" if i == 0 else "normal", linespacing=1.05)
            x += ancho_col[j]
        y += nl
        if i == 0:
            ax.axhline(y, color="black", lw=0.6)
    ax.axhline(0.3, color="black", lw=1.0)
    ax.axhline(y, color="black", lw=1.0)
    fig.savefig(DIR_SAL / f"{nombre}.pdf")
    fig.savefig(DIR_SAL / f"{nombre}.png")
    plt.close(fig)


def guardar_figura(fig, nombre):
    fig.savefig(DIR_SAL / f"{nombre}.pdf")
    fig.savefig(DIR_SAL / f"{nombre}.png")
    plt.close(fig)
    log.info(f"Figura guardada: {nombre}")


def estrellas(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def rotulo(ax, letra, x=-0.08, y=1.06):
    """Rótulo de panel (a), (b)... en la esquina superior izquierda."""
    ax.text(x, y, f"({letra})", transform=ax.transAxes, fontsize=9, fontweight="bold", va="bottom")


def eventos(ax, etiquetas=False):
    """Sombrea la crisis financiera 2008-09 y el confinamiento por COVID-19; marca el inicio de cada etapa."""
    for (a, b), txt in [(CRISIS, "Crisis\n2008-09"), (COVID, "COVID-19")]:
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b) + pd.offsets.MonthEnd(0), color=C["evento"], lw=0, zorder=0)
        if etiquetas:
            ax.text(pd.Timestamp(a), 1.0, txt, transform=ax.get_xaxis_transform(), fontsize=6.5,
                    color="#595959", ha="right", va="top")
    for etq, (a, _) in list(ETAPAS.items())[1:]:
        ax.axvline(pd.Timestamp(f"{a}-01-01"), color="#BFBFBF", lw=0.6, ls=(0, (3, 3)), zorder=0)


def etapas_arriba(ax):
    """Escribe E1...E5 sobre el panel, centradas en cada etapa."""
    for etq, (a, b) in ETAPAS.items():
        medio = pd.Timestamp(f"{a}-01-01") + (pd.Timestamp(f"{b}-12-31") - pd.Timestamp(f"{a}-01-01")) / 2
        ax.text(medio, 1.02, etq, transform=ax.get_xaxis_transform(), ha="center", va="bottom",
                fontsize=7, color="#595959")


def miles(ax):
    """Separador de miles con espacio fino en el eje vertical (700 000)."""
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:,.0f}".replace(",", "\u2009")))


def eje_anios(ax, cada=4):
    ax.xaxis.set_major_locator(mdates.YearLocator(cada))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.set_xlim(pd.Timestamp("2000-01-01"), pd.Timestamp("2025-12-31"))


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
# 4. TABLA 1: DEFINICIÓN Y FUENTE DE LAS VARIABLES
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
# 5. BLOQUE A: ESTADÍSTICA DESCRIPTIVA (Tablas 2-3, Figuras 1-5)
# ----------------------------------------------------------------------------
SERIES = [  # columna, título del panel, unidad, color
    ("inversion_privada", "Inversión privada", "Millones de S/ de 2007", C["inversion"]),
    ("pbi", "PBI real", "Índice 2007 = 100", C["pbi"]),
    ("tasa_corporativa", "Tasa de interés corporativa", "% anual", C["tasa"]),
    ("tipo_cambio", "Tipo de cambio", "S/ por US$", C["tc"]),
    ("expectativa_economia_3m", "Expectativas empresariales (3 meses)", "Puntos (50 = neutral)", C["exp"]),
    ("terminos_intercambio", "Términos de intercambio", "Índice 2007 = 100", C["ti"]),
]


def descriptiva(m, d):
    # Tabla 2: estadísticos descriptivos
    serie = {f"{t} ({u})": m[c] for c, t, u, _ in SERIES}
    serie["Crecimiento interanual de la inversión (%)"] = d["g_ipr"]
    filas = {}
    for k, s in serie.items():
        s = s.dropna()
        filas[k] = {"N": len(s), "Media": s.mean(), "Mediana": s.median(), "DE": s.std(), "Mínimo": s.min(),
                    "Máximo": s.max(), "CV (%)": 100 * s.std() / abs(s.mean()), "Asimetría": stats.skew(s),
                    "Curtosis": stats.kurtosis(s, fisher=False)}
    t2 = pd.DataFrame(filas).T.round(3)
    t2["N"] = t2["N"].astype(int)
    t2.index.name = "Variable"
    guardar_tabla(t2, "tabla2_descriptivos", "Estadísticos descriptivos, enero 2000 - diciembre 2025")

    # Tabla 3: correlación de Pearson con estrellas (+ VIF en el log)
    vs = ["ln_ipr"] + list(X_VARS)
    corto = {"ln_ipr": "Inversión", "ln_pbi": "PBI", "tasa": "Tasa", "ln_tc": "Tipo de cambio",
             "exp": "Expectativas", "ln_ti": "Térm. intercambio"}
    r = pd.DataFrame(index=[corto[v] for v in vs], columns=[corto[v] for v in vs], dtype=object)
    rnum = pd.DataFrame(index=r.index, columns=r.columns, dtype=float)
    pnum = rnum.copy()
    for a in vs:
        for b in vs:
            rr, pp = stats.pearsonr(d[a], d[b])
            rnum.loc[corto[a], corto[b]], pnum.loc[corto[a], corto[b]] = rr, pp
            r.loc[corto[a], corto[b]] = f"{rr:.3f}{estrellas(pp) if a != b else ''}"
    guardar_tabla(r, "tabla3_correlaciones", "Matriz de correlaciones de Pearson (* p<0.10, ** p<0.05, *** p<0.01)")
    vif = [variance_inflation_factor(sm.add_constant(d[list(X_VARS)]).values, i + 1) for i in range(len(X_VARS))]
    log.info("VIF: " + ", ".join(f"{NOMBRE[v]}={x:.2f}" for v, x in zip(X_VARS, vif)))

    figura1_evolucion(m)
    figura1b_mapa_evolucion(m)
    figura2_inversion_tasa(m, d)
    figura3_etapas(d)
    figura4_correlaciones(rnum, pnum)
    figura5_correlograma(d)


def figura1_evolucion(m):
    """Figura 1: evolución de las 6 variables (pequeños múltiplos), con etapas y eventos."""
    fig, ejes = plt.subplots(3, 2, figsize=(ANCHO_DOBLE, 6.6), sharex=True)
    for i, (ax, (c, t, u, col)) in enumerate(zip(ejes.flat, SERIES)):
        eventos(ax, etiquetas=(i == 0))
        if c == "tasa_corporativa":                          # tramo reconstruido en línea discontinua
            obs = m["tasa_imputada"] == 0
            ax.plot(m.index[~obs], m.loc[~obs, c], color=col, lw=1.0, ls=(0, (2, 1.5)), label="Reconstruida")
            ax.plot(m.index[obs], m.loc[obs, c], color=col, lw=1.1, label="Observada")
            ax.legend(loc="upper right", handlelength=2.2)
        elif c == "expectativa_economia_3m":
            ax.axhline(50, color=C["gris"], lw=0.7, ls=":")
            ax.fill_between(m.index, 50, m[c], where=m[c] >= 50, color=col, alpha=0.18, lw=0)
            ax.fill_between(m.index, 50, m[c], where=m[c] < 50, color=C["neg"], alpha=0.18, lw=0)
            ax.plot(m.index, m[c], color=col)
        else:
            ax.plot(m.index, m[c], color=col)
        ax.set_title(t, loc="left", pad=14 if i < 2 else 6)
        ax.set_ylabel(u)
        if c in ("inversion_privada",):
            miles(ax)
        rotulo(ax, "abcdef"[i], x=-0.16, y=1.1 if i < 2 else 1.06)
        if i < 2:
            etapas_arriba(ax)
        eje_anios(ax)
    fig.align_ylabels(ejes[:, 0])
    fig.tight_layout(h_pad=1.6)
    guardar_figura(fig, "figura1_evolucion")


def figura1b_mapa_evolucion(m):
    """Figura 1b: mapa de calor de la evolución (promedio anual estandarizado de cada variable)."""
    anual = m[[c for c, *_ in SERIES]].groupby(m.index.year).mean()
    z = (anual - anual.mean()) / anual.std()
    fig, ax = plt.subplots(figsize=(ANCHO_DOBLE, 2.6))
    im = ax.imshow(z.T.values, aspect="auto", cmap="RdBu_r", vmin=-2.5, vmax=2.5)
    ax.set_yticks(range(len(SERIES)), [t for _, t, *_ in SERIES])
    ax.set_xticks(range(0, len(z), 2), z.index[::2])
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    for i, (etq, (a, b)) in enumerate(ETAPAS.items()):
        x0 = list(z.index).index(int(a)) - 0.5
        if i > 0:
            ax.axvline(x0, color="white", lw=2)
        x1 = list(z.index).index(int(b)) + 0.5
        ax.text((x0 + x1) / 2, -0.75, etq, ha="center", va="bottom", fontsize=7.5, color="#404040")
    cb = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.01)
    cb.set_label("Desviaciones estándar\nrespecto de la media", fontsize=7)
    cb.outline.set_visible(False)
    fig.tight_layout()
    guardar_figura(fig, "figura1b_mapa_evolucion")


def figura2_inversion_tasa(m, d):
    """Figura 2: (a) crecimiento interanual de la inversión; (b) tasa corporativa."""
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(ANCHO_DOBLE, 4.6), sharex=True, height_ratios=[1.15, 1])
    g = d["g_ipr"]
    eventos(a1, etiquetas=True)
    a1.bar(g.index, g.where(g >= 0), width=31, color=C["inversion"], lw=0)
    a1.bar(g.index, g.where(g < 0), width=31, color=C["neg"], lw=0)
    a1.axhline(0, color="black", lw=0.6)
    a1.set_ylabel("Crecimiento interanual (%)")
    a1.set_title("Inversión privada real", loc="left", pad=14)
    etapas_arriba(a1)
    rotulo(a1, "a", y=1.1)
    eventos(a2)
    obs = m["tasa_imputada"] == 0
    a2.plot(m.index[~obs], m.loc[~obs, "tasa_corporativa"], color=C["tasa"], ls=(0, (2, 1.5)), label="Reconstruida (MCO)")
    a2.plot(m.index[obs], m.loc[obs, "tasa_corporativa"], color=C["tasa"], lw=1.3, label="Observada (BCRP)")
    a2.set_ylabel("% anual")
    a2.set_title("Tasa de interés corporativa", loc="left")
    a2.legend(loc="upper right")
    rotulo(a2, "b")
    eje_anios(a2)
    fig.align_ylabels([a1, a2])
    fig.tight_layout(h_pad=1.4)
    guardar_figura(fig, "figura2_inversion_tasa")


def figura3_etapas(d):
    """Figura 3: crecimiento de la inversión por etapas (cajas + puntos) y prueba de Kruskal-Wallis."""
    grupos = [d.loc[d["etapa"] == e, "g_ipr"].dropna() for e in ETAPAS]
    kw = stats.kruskal(*grupos)
    fig, ax = plt.subplots(figsize=(ANCHO_SIMPLE * 1.45, 3.2))
    rng = np.random.default_rng(SEMILLA)
    colores = ["#9ECAE1", "#4292C6", "#9ECAE1", "#F4A582", "#4292C6"]
    for i, (g, col) in enumerate(zip(grupos, colores), start=1):
        ax.scatter(i + rng.uniform(-0.18, 0.18, len(g)), g, s=4, color=col, alpha=0.55, lw=0, zorder=2)
    bp = ax.boxplot(grupos, widths=0.5, patch_artist=True, showfliers=False, zorder=3,
                    medianprops={"color": "black", "lw": 1.4}, whiskerprops={"lw": 0.8}, capprops={"lw": 0.8})
    for caja in bp["boxes"]:
        caja.set(facecolor="none", edgecolor="#404040", lw=0.9)
    for i, g in enumerate(grupos, start=1):
        ax.text(i, g.max() + 1, f"Me = {g.median():.1f}", ha="center", va="bottom", fontsize=6.8)
    ax.axhline(0, color=C["gris"], lw=0.7, ls=":")
    ax.set_xticks(range(1, len(ETAPAS) + 1), [NOMBRE_ETAPA[e] for e in ETAPAS])
    ax.set_ylabel("Crecimiento interanual de la inversión (%)")
    p_txt = "p < 0.001" if kw.pvalue < 0.001 else f"p = {kw.pvalue:.3f}"
    ax.text(0.99, 0.02, f"Kruskal-Wallis: H = {kw.statistic:.1f}; {p_txt}", transform=ax.transAxes,
            ha="right", va="bottom", fontsize=7, bbox={"facecolor": "white", "edgecolor": "#BFBFBF", "lw": 0.5})
    fig.tight_layout()
    guardar_figura(fig, "figura3_etapas")
    log.info(f"Kruskal-Wallis entre etapas: H = {kw.statistic:.3f}, p = {kw.pvalue:.4f}")


def figura4_correlaciones(rnum, pnum):
    """Figura 4: mapa de calor (triángulo inferior, sin diagonal) con r y estrellas de significancia."""
    r, p = rnum.iloc[1:, :-1], pnum.iloc[1:, :-1]
    n = len(r)
    mascara = np.triu(np.ones((n, n), dtype=bool), k=1)
    datos = np.ma.array(r.values.astype(float), mask=mascara)
    fig, ax = plt.subplots(figsize=(ANCHO_DOBLE * 0.62, 3.5))
    im = ax.imshow(datos, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(n), r.columns, rotation=35, ha="right")
    ax.set_yticks(range(n), r.index)
    ax.grid(False)
    for s_ in ax.spines.values():
        s_.set_visible(False)
    ax.tick_params(length=0)
    for i in range(n):
        for j in range(i + 1):
            v = r.iloc[i, j]
            ax.text(j, i, f"{v:.2f}\n{estrellas(p.iloc[i, j])}", ha="center", va="center", fontsize=7,
                    linespacing=1.1, color="white" if abs(v) > 0.6 else "black")
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.set_label("r de Pearson   (* p<0.10; ** p<0.05; *** p<0.01)", fontsize=7)
    cb.outline.set_visible(False)
    fig.tight_layout()
    guardar_figura(fig, "figura4_correlaciones")


def figura5_correlograma(d):
    """Figura 5: correlación entre las expectativas de hace k meses y el crecimiento de la inversión."""
    z = d[["exp", "g_ipr"]].dropna()
    ks = np.arange(-12, 13)
    cc = np.array([z["exp"].shift(k).corr(z["g_ipr"]) for k in ks])
    banda = 1.96 / np.sqrt(len(z))
    sig = np.abs(cc) > banda
    kmax = int(ks[np.nanargmax(cc)])
    fig, ax = plt.subplots(figsize=(ANCHO_SIMPLE * 1.6, 3.0))
    ax.axhspan(-banda, banda, color="#F0F0F0", lw=0, zorder=0, label="Banda al 95 % (no significativa)")
    col = np.where(sig, np.where(ks > 0, C["exp"], C["inversion"]), C["gris"])
    ax.vlines(ks, 0, cc, colors=col, lw=1.6)
    ax.scatter(ks, cc, color=col, s=16, zorder=3)
    ax.axhline(0, color="black", lw=0.6)
    ax.axvline(0, color="#BFBFBF", lw=0.6, ls=":")
    ax.annotate(f"Máximo: k = {kmax}\nr = {np.nanmax(cc):.2f}", xy=(kmax, np.nanmax(cc)),
                xytext=(kmax + (3 if kmax < 6 else -6), np.nanmax(cc)), fontsize=7,
                arrowprops={"arrowstyle": "-", "lw": 0.6, "color": "#595959"}, va="center")
    ax.text(0.99, 0.03, "Expectativas adelantadas →", transform=ax.transAxes, ha="right", fontsize=6.8, color=C["exp"])
    ax.text(0.01, 0.03, "← Inversión adelantada", transform=ax.transAxes, ha="left", fontsize=6.8, color=C["inversion"])
    ax.set_ylim(min(-banda * 1.3, np.nanmin(cc) * 1.15), np.nanmax(cc) * 1.22)
    ax.set_xticks(ks[::2])
    ax.set_xlabel("Desfase k (meses): correlación entre Expectativas(t − k) y Crecimiento de la inversión(t)")
    ax.set_ylabel("Correlación")
    ax.legend(loc="upper left")
    fig.tight_layout()
    guardar_figura(fig, "figura5_correlograma")
    log.info(f"Correlograma cruzado: máxima correlación en k = {kmax} meses (r = {np.nanmax(cc):.3f})")

# ----------------------------------------------------------------------------
# 6. BLOQUE B1: RAÍZ UNITARIA (Tabla 4)
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
        f["ZA estad."], f["ZA p"] = za[0], za[1]
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
# 7. BLOQUE B2: ARDL-ECM, DOLS Y TABLA 5
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


def _sr(c, n):
    u = c["uecm"]
    return f"{u.params[n]:.3f}{estrellas(u.pvalues[n])}" if n in u.params else ""


def tabla5(base, sub, dols):
    def celda(c, v):
        return f"{c['lr'][v]:.3f}{estrellas(c['pval'][v])} ({c['se'][v]:.3f})"
    filas = [["A. Largo plazo", NOMBRE[v], celda(base, v), celda(sub, v), celda(dols, v)] for v in X_VARS]
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

# ----------------------------------------------------------------------------
# 8. FIGURAS DEL MODELO (7 a 10)
# ----------------------------------------------------------------------------
CHOQUES_LP = {"ln_pbi": (1, "PBI +1 %"), "tasa": (100, "Tasa +1 p.p."), "ln_tc": (1, "Tipo de cambio +1 %"),
              "exp": (1000, "Expectativas +10 puntos"), "ln_ti": (1, "Términos de intercambio +1 %")}
CHOQUES_DIN = {"tasa": (1, "Tasa de interés +1 p.p.", C["tasa"]),
               "ln_tc": (0.01, "Tipo de cambio +1 %", C["tc"]),
               "exp": (10, "Expectativas +10 puntos", C["exp"])}


def figura7_bounds(base):
    cv, F = base["bt"].critical_values, base["bt"].statistic
    niveles = [(90.0, "10 %"), (95.0, "5 %"), (99.0, "1 %")]
    fig, ax = plt.subplots(figsize=(ANCHO_SIMPLE, 2.8))
    x = np.arange(len(niveles))
    b0 = ax.bar(x - 0.19, [cv.loc[n, "lower"] for n, _ in niveles], 0.36, color="#C6DBEF", label="Límite inferior I(0)")
    b1 = ax.bar(x + 0.19, [cv.loc[n, "upper"] for n, _ in niveles], 0.36, color=C["inversion"], label="Límite superior I(1)")
    for barras in (b0, b1):
        ax.bar_label(barras, fmt="%.2f", fontsize=6.5, padding=1.5)
    ax.axhline(F, color=C["tasa"], lw=1.6)
    ax.text(len(niveles) - 0.5, F, f"F = {F:.2f}", color=C["tasa"], ha="right", va="bottom", fontsize=7.5, fontweight="bold")
    ax.set_xticks(x, [e for _, e in niveles])
    ax.set_xlabel("Nivel de significancia")
    ax.set_ylabel("Valor crítico / estadístico F")
    ax.set_ylim(0, max(F, cv["upper"].max()) * 1.2)
    ax.legend(loc="center left")
    fig.tight_layout()
    guardar_figura(fig, "figura7_bounds_test")


def figura8_largo_plazo(base):
    """Forest plot: efecto de largo plazo (%) ante choques interpretables, con IC al 95 %."""
    vs = list(X_VARS)
    ef = np.array([base["lr"][v] * CHOQUES_LP[v][0] for v in vs])
    ic = np.array([1.96 * base["se"][v] * CHOQUES_LP[v][0] for v in vs])
    sig = np.array([base["pval"][v] < 0.05 for v in vs])
    fig, ax = plt.subplots(figsize=(ANCHO_SIMPLE * 1.55, 2.9))
    yy = np.arange(len(vs))[::-1]
    ax.axvline(0, color="black", lw=0.7)
    for y_, e, i_, s, v in zip(yy, ef, ic, sig, vs):
        col = C["inversion"] if s else C["gris"]
        ax.errorbar(e, y_, xerr=i_, fmt="o", color=col, ecolor=col, elinewidth=1.4, capsize=3, ms=5,
                    mfc=col if s else "white")
        ax.text(1.02, y_, f"{e:+.2f} %{estrellas(base['pval'][v])}", transform=ax.get_yaxis_transform(),
                va="center", fontsize=7.5, color=col)
    ax.set_yticks(yy, [CHOQUES_LP[v][1] for v in vs])
    ax.grid(axis="x", color="#E6E6E6", lw=0.5)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Cambio de largo plazo en la inversión privada (%) e IC al 95 %")
    ax.text(0, -0.24, "Relleno: significativo al 5 %; vacío: no significativo.", transform=ax.transAxes,
            fontsize=6.5, color="#595959")
    fig.tight_layout()
    guardar_figura(fig, "figura8_largo_plazo")


def _respuesta(par, p, q, v, tam, H):
    phi = [par.get(f"{Y_VAR}.L{i}", 0.0) for i in range(1, p + 1)]
    theta = [par.get(f"{v}.L{j}", 0.0) for j in range(0, q + 1)]
    r = np.zeros(H + 1)
    for t in range(H + 1):
        r[t] = sum(phi[i] * r[t - 1 - i] for i in range(len(phi)) if t - 1 - i >= 0) \
            + tam * sum(theta[j] for j in range(len(theta)) if j <= t)
    return 100 * r


def figura9_multiplicadores(base, H=24):
    """Multiplicadores dinámicos acumulados con bandas al 95 % (simulación de los parámetros, semilla 0530)."""
    par, cov = base["ardl"].params, base["ardl"].cov_params()
    rng = np.random.default_rng(SEMILLA)
    sorteos = pd.DataFrame(rng.multivariate_normal(par.values, cov.values, size=N_BOOT), columns=par.index)
    fig, ejes = plt.subplots(1, 3, figsize=(ANCHO_DOBLE, 2.6), sharex=True)
    for ax, (letra, (v, (tam, etq, col))) in zip(ejes, zip("abc", CHOQUES_DIN.items())):
        central = _respuesta(par, base["p"], base["q"], v, tam, H)
        sims = np.array([_respuesta(s, base["p"], base["q"], v, tam, H) for _, s in sorteos.iterrows()])
        lo, hi = np.percentile(sims, [2.5, 97.5], axis=0)
        ax.fill_between(range(H + 1), lo, hi, color=col, alpha=0.18, lw=0, label="IC 95 %")
        ax.plot(range(H + 1), central, color=col, lw=1.8, label="Respuesta acumulada")
        lp = 100 * base["lr"][v] * tam
        ax.axhline(lp, color=col, ls=(0, (3, 2)), lw=0.9)
        ax.text(H, lp, f"Largo plazo: {lp:+.2f} %", ha="right", va="bottom" if lp >= 0 else "top", fontsize=6.8, color=col)
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title(etq, loc="left")
        ax.set_xlabel("Meses después del choque")
        ax.set_xticks(range(0, H + 1, 6))
        rotulo(ax, letra, x=-0.2)
    ejes[0].set_ylabel("Cambio en la inversión (%)")
    ejes[2].legend(loc="lower right", fontsize=6.8)
    fig.tight_layout(w_pad=1.5)
    guardar_figura(fig, "figura9_multiplicadores")


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


def figura10_cusum(base):
    mod = base["modelo"]
    w = residuos_recursivos(np.asarray(mod._y, float), np.asarray(mod._x, float))
    n = len(w)
    t = np.arange(1, n + 1)
    cusum = np.cumsum(w) / np.std(w, ddof=1)
    banda = 0.948 * np.sqrt(n) * (1 + 2 * t / n)
    sq = np.cumsum(w ** 2) / np.sum(w ** 2)
    c0 = 1.358 / np.sqrt(n / 2)                                    # aproximación asintótica al 5 %
    fechas = base["ardl"].fittedvalues.index[-n:]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(ANCHO_DOBLE, 2.7))
    for ax, serie, lo, hi, etq, letra in [(a1, cusum, -banda, banda, "CUSUM", "a"),
                                         (a2, sq, t / n - c0, t / n + c0, "CUSUM de cuadrados", "b")]:
        eventos(ax)
        ax.fill_between(fechas, lo, hi, color="#EEF3F8", lw=0, zorder=0)
        ax.plot(fechas, lo, color=C["tasa"], lw=0.8, ls=(0, (3, 2)))
        ax.plot(fechas, hi, color=C["tasa"], lw=0.8, ls=(0, (3, 2)), label="Bandas al 5 %")
        ax.plot(fechas, serie, color=C["inversion"], lw=1.3, label=etq)
        ax.set_title(etq, loc="left")
        ax.xaxis.set_major_locator(mdates.YearLocator(4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        rotulo(ax, letra, x=-0.12)
    a1.legend(loc="upper left")
    fig.tight_layout(w_pad=2)
    guardar_figura(fig, "figura10_cusum")
    dentro = bool(np.all(np.abs(cusum) <= banda)), bool(np.all(np.abs(sq - t / n) <= c0))
    log.info(f"Estabilidad: CUSUM dentro de bandas = {dentro[0]} | CUSUMSQ dentro de bandas = {dentro[1]}")
    return dentro


# ----------------------------------------------------------------------------
# 9. BLOQUE B3: GRANGER, DIAGNÓSTICO E HIPÓTESIS (Tabla 6)
# ----------------------------------------------------------------------------
def tabla6(d, base, estable):
    filas, granger = [], {}
    dy = d[Y_VAR].diff()
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
    lr, pv, bt = base["lr"], base["pval"], base["bt"]
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
# 10. BLOQUE C: PUENTE CON EL VAN (Figura 6, Clase 09)
# ----------------------------------------------------------------------------
def _tir(f):
    lo, hi = 0.0, 1.0
    for _ in range(100):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if np.sum(f / (1 + mid) ** np.arange(len(f))) > 0 else (lo, mid)
    return mid


def figura6_van(m, d):
    flujos = np.array(PROYECTO, dtype=float)
    t = np.arange(len(flujos))
    k = m["tasa_corporativa"] / 100
    van = k.apply(lambda r: float(np.sum(flujos / (1 + r) ** t))) / 1000
    tir = _tir(flujos)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(ANCHO_DOBLE, 4.6), sharex=True)
    eventos(a1, etiquetas=True)
    a1.fill_between(van.index, 0, van, where=van >= 0, color=C["inversion"], alpha=0.15, lw=0)
    a1.fill_between(van.index, 0, van, where=van < 0, color=C["neg"], alpha=0.25, lw=0)
    a1.plot(van.index, van, color=C["inversion"], lw=1.3)
    a1.axhline(0, color="black", lw=0.6)
    a1.set_ylabel("VAN (miles de S/)")
    a1.set_title("VAN del proyecto representativo descontado con la tasa corporativa del mes", loc="left", pad=14)
    a1.text(0.99, 0.06, f"Flujos: −100; 30; 35; 40; 45 (miles de S/)  ·  TIR = {100 * tir:.1f} %  ·  VAN < 0 si k > TIR",
            transform=a1.transAxes, ha="right", fontsize=6.8, color="#404040",
            bbox={"facecolor": "white", "edgecolor": "#BFBFBF", "lw": 0.5})
    etapas_arriba(a1)
    rotulo(a1, "a", y=1.1)
    g = d["g_ipr"]
    eventos(a2)
    a2.bar(g.index, g.where(g >= 0), width=31, color=C["inversion"], lw=0)
    a2.bar(g.index, g.where(g < 0), width=31, color=C["neg"], lw=0)
    a2.axhline(0, color="black", lw=0.6)
    a2.set_ylabel("Crecimiento interanual (%)")
    a2.set_title("Inversión privada real", loc="left")
    rotulo(a2, "b")
    eje_anios(a2)
    fig.align_ylabels([a1, a2])
    fig.tight_layout(h_pad=1.4)
    guardar_figura(fig, "figura6_van_proyecto")
    log.info(f"VAN proyecto representativo: mín = {1000 * van.min():,.0f} ({van.idxmin():%Y-%m}), máx = {1000 * van.max():,.0f} "
             f"({van.idxmax():%Y-%m}); meses con VAN < 0: {int((van < 0).sum())}; TIR = {100 * tir:.2f} %; "
             f"correlación VAN vs crecimiento de la inversión = {van.corr(g):.3f}")

# ----------------------------------------------------------------------------
# 11. EJECUCIÓN
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
    figura7_bounds(base)
    figura8_largo_plazo(base)
    figura9_multiplicadores(base)
    estable = figura10_cusum(base)
    tabla6(d, base, estable)
    figura6_van(m, d)
    log.info("Fin de 04_analisis.py: OK (6 tablas y 11 figuras en /salidas)")


if __name__ == "__main__":
    main()
