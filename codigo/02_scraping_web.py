# Nombres y apellidos: YOMAR CRISTHIAN SORAS QUISPE
# Código de matrícula: 2024200530J
# Tema N.º 56 del temario: Métodos de evaluación de inversiones — Determinantes macroeconómicos de la inversión privada en el Perú
# Fecha de extracción: 2026-11-27
"""
02_scraping_web.py — Vía 2: web scraping de la Encuesta de Expectativas
Macroeconómicas del BCRP (índices de expectativas empresariales).

Pasos:
  1. Revisa robots.txt de los dominios consultados y registra el resultado.
  2. Scraping de la página de la Encuesta en BCRPData: con BeautifulSoup se leen los
     enlaces a las series de expectativas (código y nombre) y los enlaces .xlsx publicados.
  3. Intenta descargar el XLSX "Índices de confianza empresarial" (www.bcrp.gob.pe).
     Ese servidor exige verificación anti-bot con JavaScript: si la respuesta no es
     Excel, se guarda la evidencia y se registra en incidencias_fuente.md.
  4. Para cada índice seleccionado se hace scraping de su página de resultados
     (tabla HTML) con BeautifulSoup. El HTML se guarda INTACTO como evidencia y los
     valores se copian tal como se publican (sin limpiar ni recortar fechas;
     el recorte a 2000-01/2025-12 se hace en 03_limpieza_datos.py).
No se usa la API (Vía 1) en este script. No se recolectan datos personales (Ley N.º 29733).
"""

import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

# ----------------------------------------------------------------------------
# 1. PARÁMETROS
# ----------------------------------------------------------------------------
CODIGO = "2024200530J"
URL_BASE = "https://estadisticas.bcrp.gob.pe"
URL_PAGINA = f"{URL_BASE}/estadisticas/series/mensuales/expectativas-empresariales-m"
URL_RESULTADOS = f"{URL_BASE}/estadisticas/series/mensuales/resultados/{{codigo}}/html"
TEXTO_XLSX = "confianza empresarial"        # enlace .xlsx publicado en la página

# Índices de expectativas que se extraen (se verifica por scraping que estén en la página)
SERIES_OBJETIVO = {
    "PD38045AM": "exp_eco_3m",       # Índice de expectativas de la economía a 3 meses (variable principal)
    "PD37981AM": "exp_eco_12m",      # Índice de expectativas de la economía a 12 meses (robustez)
    "PD38046AM": "exp_sector_3m",    # Índice de expectativas del sector a 3 meses (robustez)
}
PAUSA_SEG = 2.0
TIMEOUT_SEG = 60
REINTENTOS = 3

# ----------------------------------------------------------------------------
# 2. RUTAS RELATIVAS
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent
DIR_CRUDOS = BASE / "datos_crudos"
DIR_ENC = DIR_CRUDOS / "encuesta_expectativas"
DIR_HTML = DIR_ENC / "html_resultados"
ARCHIVO_CSV = DIR_CRUDOS / f"datos_crudos_scraping_{CODIGO}.csv"
ARCHIVO_LOG = BASE / "log_ejecucion.txt"
ARCHIVO_INCIDENCIAS = BASE / "incidencias_fuente.md"
DIR_HTML.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# 3. REGISTRO
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | 02_scraping_web | %(message)s",
    handlers=[logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger()

# ----------------------------------------------------------------------------
# 4. SESIÓN HTTP (User-Agent identificable)
# ----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass
CONTACTO = os.getenv("USER_AGENT_CONTACTO", "").strip()
USER_AGENT = "Proyecto-academico-UNCP-Finanzas-I" + (f" ({CONTACTO})" if CONTACTO else "")
SESION = requests.Session()
SESION.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "es-PE,es;q=0.9"})

PATRON_PERIODO = re.compile(r"^[A-Za-zé]{3}\.?\s?\d{2}(\d{2})?$")   # Abr02, Abr.2002, Ene26...


# ----------------------------------------------------------------------------
# 5. FUNCIONES
# ----------------------------------------------------------------------------
def obtener(url, reintentos=REINTENTOS):
    """GET con reintentos y pausa. Devuelve la última respuesta (o None)."""
    r = None
    for intento in range(1, reintentos + 1):
        try:
            r = SESION.get(url, timeout=TIMEOUT_SEG)
            log.info(f"GET {url} -> HTTP {r.status_code} | {r.headers.get('Content-Type', '?')} "
                     f"| {len(r.content)} bytes (intento {intento})")
            if r.status_code in (200, 404):
                break
        except requests.RequestException as e:
            log.warning(f"Error en intento {intento}: {e}")
        time.sleep(PAUSA_SEG * intento)
    time.sleep(PAUSA_SEG)
    return r


def revisar_robots(url):
    """Lee robots.txt del dominio de la URL y registra si la ruta está permitida."""
    dominio = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    r = obtener(f"{dominio}/robots.txt", reintentos=1)
    if r is not None and r.status_code == 404:
        log.info(f"{dominio} no publica robots.txt (HTTP 404): no declara restricciones")
    elif r is not None and r.status_code == 200 and "text/plain" in r.headers.get("Content-Type", ""):
        import urllib.robotparser
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(r.text.splitlines())
        ok = rp.can_fetch(USER_AGENT, url)
        log.info(f"robots.txt de {dominio}: acceso a {urlparse(url).path} -> {'PERMITIDO' if ok else 'NO PERMITIDO'}")
        return ok
    else:
        log.warning(f"robots.txt de {dominio} no disponible; se procede con solicitudes pausadas e identificadas")
    return True


def registrar_incidencia(url, respuesta, detalle):
    """Documenta un bloqueo técnico de la fuente (numeral 2.4.3 de la consigna)."""
    nuevo = not ARCHIVO_INCIDENCIAS.exists()
    with open(ARCHIVO_INCIDENCIAS, "a", encoding="utf-8") as f:
        if nuevo:
            f.write("# Incidencias de la fuente\n\n| Fecha y hora | URL | HTTP | Content-Type | Detalle |\n|---|---|---|---|---|\n")
        f.write(f"| {datetime.now():%Y-%m-%d %H:%M:%S} | {url} | "
                f"{getattr(respuesta, 'status_code', 'sin respuesta')} | "
                f"{respuesta.headers.get('Content-Type', '?') if respuesta is not None else '?'} | {detalle} |\n")
    log.warning(f"Incidencia registrada en {ARCHIVO_INCIDENCIAS.name}: {detalle}")


def scraping_pagina_encuesta(html):
    """Lee de la página las series publicadas (código -> nombre) y los enlaces .xlsx."""
    soup = BeautifulSoup(html, "html.parser")
    series = {}
    for a in soup.select('a[href*="/resultados/"]'):
        m = re.search(r"/resultados/([A-Z]{2}\d{5}[A-Z]{2})/", a["href"])
        if m:
            series[m.group(1)] = a.get_text(" ", strip=True)
    xlsx = [(a.get_text(" ", strip=True), urljoin(URL_PAGINA, a["href"]))
            for a in soup.select('a[href$=".xlsx"]')]
    return series, xlsx


def tabla_desde_html(html):
    """Scraping de la tabla de resultados: devuelve DataFrame [periodo, valor] tal como se publica."""
    soup = BeautifulSoup(html, "html.parser")
    filas = []
    for tr in soup.find_all("tr"):
        celdas = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if len(celdas) >= 2 and PATRON_PERIODO.match(celdas[0]):
            filas.append((celdas[0], celdas[1]))
    return pd.DataFrame(filas, columns=["periodo", "valor"])


# ----------------------------------------------------------------------------
# 6. EJECUCIÓN
# ----------------------------------------------------------------------------
def main():
    log.info("=" * 70)
    log.info(f"Inicio Vía 2 | requests {requests.__version__} | pandas {pd.__version__} | User-Agent: {USER_AGENT}")

    # 6.1 Scraping de la página de la Encuesta
    revisar_robots(URL_PAGINA)
    r = obtener(URL_PAGINA)
    if r is None or r.status_code != 200:
        registrar_incidencia(URL_PAGINA, r, "No se pudo descargar la página de la Encuesta")
        sys.exit(1)
    (DIR_ENC / f"pagina_encuesta_{CODIGO}.html").write_bytes(r.content)      # evidencia del scraping
    series_pagina, enlaces_xlsx = scraping_pagina_encuesta(r.text)
    log.info(f"Scraping: {len(series_pagina)} series y {len(enlaces_xlsx)} enlaces .xlsx en la página")
    for cod, nom in series_pagina.items():
        log.info(f"    serie {cod}: {nom}")

    # 6.2 Intento con el XLSX publicado en www.bcrp.gob.pe (protegido con verificación anti-bot)
    for texto, url in enlaces_xlsx:
        if TEXTO_XLSX in texto.lower():
            revisar_robots(url)
            rx = obtener(url, reintentos=1)
            if rx is not None and rx.status_code == 200 and rx.content[:2] == b"PK":
                destino = DIR_ENC / f"{Path(urlparse(url).path).stem}_{CODIGO}.xlsx"
                destino.write_bytes(rx.content)
                log.info(f"XLSX publicado descargado: {destino.name}")
            else:
                if rx is not None:
                    (DIR_ENC / f"respuesta_bloqueada_xlsx_{CODIGO}.html").write_bytes(rx.content)
                registrar_incidencia(url, rx, "www.bcrp.gob.pe responde con verificación anti-bot (JavaScript) "
                                              "en vez del XLSX; se usa el scraping de las tablas HTML de BCRPData")

    # 6.3 Para cada índice: scraping de su tabla HTML de resultados
    registros = []
    for cod, variable in SERIES_OBJETIVO.items():
        if cod not in series_pagina:
            log.warning(f"{cod} no aparece en la página de la Encuesta; se omite")
            continue
        rh = obtener(URL_RESULTADOS.format(codigo=cod))
        if rh is None or rh.status_code != 200:
            registrar_incidencia(URL_RESULTADOS.format(codigo=cod), rh, f"No se pudo descargar la tabla de {cod}")
            continue
        (DIR_HTML / f"{cod}_{CODIGO}.html").write_bytes(rh.content)          # HTML intacto
        tabla = tabla_desde_html(rh.text)
        log.info(f"{cod} ({variable}) | tabla HTML: {len(tabla)} periodos")
        for _, f in tabla.iterrows():
            registros.append({"codigo_serie": cod, "variable": variable, "nombre_serie": series_pagina[cod],
                              "periodo": f["periodo"], "valor": f["valor"], "fuente": "html_bcrpdata"})

    if not registros:
        registrar_incidencia(URL_PAGINA, None, "No se obtuvo ninguna serie de expectativas")
        sys.exit(1)
    crudo = pd.DataFrame(registros)
    crudo.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8")
    log.info(f"Guardado {ARCHIVO_CSV.name}: {len(crudo)} filas x {crudo.shape[1]} columnas")
    for (cod, var), g in crudo.groupby(["codigo_serie", "variable"], sort=False):
        log.info(f"Resumen {cod} -> {var} | {len(g)} periodos, desde {g['periodo'].iloc[0]} hasta {g['periodo'].iloc[-1]}")
    log.info("Fin de 02_scraping_web.py: OK")


if __name__ == "__main__":
    main()
