# Nombres y apellidos: YOMAR CRISTHIAN SORAS QUISPE
# Código de matrícula: 2024200530J
# Tema N.º 56 del temario: Métodos de evaluación de inversiones — Determinantes macroeconómicos de la inversión privada en el Perú
# Fecha de extracción: 2026-11-27
"""
01_extraccion_api.py — Vía 1: extracción programática vía API REST de BCRPData.

Descarga las series del BCRP en su frecuencia original (trimestral y mensual)
y las guarda SIN EDITAR en /datos_crudos:
  - la respuesta original exacta del servidor y su JSON válido (evidencia primaria);
  - datos_crudos_api_<CODIGO>.csv: todas las respuestas aplanadas en formato largo,
    con el valor tal como lo entrega la fuente (incluido "n.d.").
Toda la ejecución queda registrada en log_ejecucion.txt.

Endpoint: https://estadisticas.bcrp.gob.pe/estadisticas/series/api/{codigo}/json/{inicio}/{fin}/esp
No requiere clave de API.
"""

import json
import logging
import os
import platform
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# ----------------------------------------------------------------------------
# 1. PARÁMETROS (congelados: no usar fechas dinámicas)
# ----------------------------------------------------------------------------
CODIGO = "2024200530J"              # código de matrícula (va en el nombre de los archivos)
FECHA_INICIO = "2000-01"            # inicio de la muestra (año-mes)
FECHA_CORTE = "2025-12"             # fin de la muestra (año-mes)

URL_BASE = "https://estadisticas.bcrp.gob.pe/estadisticas/series/api"
PAUSA_SEG = 1.0                     # pausa entre solicitudes (uso responsable del servidor)
TIMEOUT_SEG = 60
REINTENTOS = 3

# Códigos verificados en el catálogo de BCRPData (ver diccionario_variables.md).
SERIES = {
    "trimestral": {
        "PN02533AQ": "inv_priv_real",   # Inversión bruta fija privada (millones S/ 2007) -> se lleva a mensual en 03
    },
    "mensual": {
        "PN01770AM": "pbi_idx",         # PBI, índice 2007 = 100
        "PN07809NM": "tasa_corp",       # Tasa activa preferencial corporativa a 90 días, MN (%) — publicada desde ago-2010
        "PN01206PM": "tc",              # TC interbancario venta, promedio del periodo (S/ por US$)
        "PN38923BM": "tot",             # Términos de intercambio, índice 2007 = 100
        # Series AUXILIARES: no son variables del modelo; solo sirven en 03_limpieza_datos
        # para reconstruir (retropolar) la tasa corporativa antes de ago-2010.
        "PN07819NM": "aux_tasa_interb", # Tasa interbancaria promedio, MN (%)
        "PN07807NM": "aux_tamn",        # TAMN: tasa activa promedio en MN (%)
    },
}

# ----------------------------------------------------------------------------
# 2. RUTAS RELATIVAS (el proyecto funciona en cualquier máquina)
# ----------------------------------------------------------------------------
BASE = Path(__file__).resolve().parent.parent
DIR_CRUDOS = BASE / "datos_crudos"
DIR_JSON = DIR_CRUDOS / "json_api"
ARCHIVO_LOG = BASE / "log_ejecucion.txt"
ARCHIVO_CSV = DIR_CRUDOS / f"datos_crudos_api_{CODIGO}.csv"
DIR_JSON.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# 3. REGISTRO (consola + log_ejecucion.txt)
# ----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | 01_extraccion_api | %(message)s",
    handlers=[logging.FileHandler(ARCHIVO_LOG, mode="a", encoding="utf-8"),
              logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger()

# ----------------------------------------------------------------------------
# 4. CONTACTO PARA EL USER-AGENT (se lee de .env; ver .env.example)
# ----------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv(BASE / ".env")
except ImportError:
    pass
CONTACTO = os.getenv("USER_AGENT_CONTACTO", "").strip()
USER_AGENT = "Proyecto-academico-UNCP-Finanzas-I" + (f" ({CONTACTO})" if CONTACTO else "")
SESION = requests.Session()
SESION.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


# ----------------------------------------------------------------------------
# 5. FUNCIONES
# ----------------------------------------------------------------------------
def rango_api(frecuencia, inicio, fin):
    """Convierte FECHA_INICIO/FECHA_CORTE (AAAA-MM) al formato que exige la API."""
    a_ini, m_ini = map(int, inicio.split("-"))
    a_fin, m_fin = map(int, fin.split("-"))
    if frecuencia == "trimestral":            # AAAA-T (número de trimestre)
        return f"{a_ini}-{(m_ini - 1) // 3 + 1}", f"{a_fin}-{(m_fin - 1) // 3 + 1}"
    return f"{a_ini}-{m_ini}", f"{a_fin}-{m_fin}"   # mensual: AAAA-M


def leer_json(contenido):
    """Convierte la respuesta en JSON. La API del BCRP agrega texto después del
    objeto JSON ("Extra data"); se lee solo el primer objeto y se registra lo ignorado."""
    try:
        texto = contenido.decode("utf-8")
    except UnicodeDecodeError:
        texto = contenido.decode("latin-1")
    texto = texto.lstrip("\ufeff \r\n\t")
    datos, fin = json.JSONDecoder().raw_decode(texto)
    resto = texto[fin:].strip()
    if resto:
        log.info(f"Se ignoraron {len(resto)} caracteres añadidos después del JSON")
    return datos


def consultar_api(codigos, inicio, fin):
    """Llama a la API con reintentos. Devuelve el JSON leído y la respuesta en bytes."""
    url = f"{URL_BASE}/{'-'.join(codigos)}/json/{inicio}/{fin}/esp"
    for intento in range(1, REINTENTOS + 1):
        try:
            r = SESION.get(url, timeout=TIMEOUT_SEG)
            log.info(f"GET {url} -> HTTP {r.status_code} (intento {intento})")
            if r.status_code == 200:
                return leer_json(r.content), r.content
        except (requests.RequestException, ValueError) as e:
            log.warning(f"Error en intento {intento}: {e}")
        time.sleep(PAUSA_SEG * 2 * intento)           # espera creciente antes de reintentar
    raise RuntimeError(f"No se pudo descargar {codigos} tras {REINTENTOS} intentos")


def aplanar(datos, codigos, frecuencia):
    """Pasa el JSON de la API a formato largo sin modificar los valores."""
    nombres = [s.get("name", "") for s in datos["config"]["series"]]
    filas = []
    for p in datos.get("periods", []):
        for codigo, nombre, valor in zip(codigos, nombres, p["values"]):
            filas.append({"frecuencia": frecuencia, "codigo_serie": codigo,
                          "nombre_serie": nombre, "periodo": p["name"], "valor": valor})
    return filas


def descargar(frecuencia, codigos, inicio, fin, etiqueta):
    datos, bruto = consultar_api(codigos, inicio, fin)
    nombre = f"api_{frecuencia}_{etiqueta}_{CODIGO}"
    (DIR_JSON / f"{nombre}_respuesta_original.txt").write_bytes(bruto)   # respuesta exacta del servidor
    with open(DIR_JSON / f"{nombre}.json", "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)               # JSON válido leído de esa respuesta
    filas = aplanar(datos, codigos, frecuencia)
    log.info(f"{frecuencia} {etiqueta}: {len(filas)} registros recibidos")
    time.sleep(PAUSA_SEG)
    return filas


# ----------------------------------------------------------------------------
# 6. EJECUCIÓN
# ----------------------------------------------------------------------------
def main():
    log.info("=" * 70)
    log.info(f"Inicio | Python {platform.python_version()} | requests {requests.__version__} "
             f"| pandas {pd.__version__}")
    log.info(f"Parámetros: FECHA_INICIO={FECHA_INICIO} FECHA_CORTE={FECHA_CORTE} | User-Agent: {USER_AGENT}")

    # Una solicitud POR SERIE: cuando se piden varias juntas, la API no garantiza
    # devolverlas en el orden pedido, y la asignación código -> valores podría cruzarse.
    registros = []
    for frecuencia, series in SERIES.items():
        ini, fin = rango_api(frecuencia, FECHA_INICIO, FECHA_CORTE)
        for codigo in series:
            registros += descargar(frecuencia, [codigo], ini, fin, codigo)

    crudo = pd.DataFrame(registros)
    crudo.to_csv(ARCHIVO_CSV, index=False, encoding="utf-8")
    log.info(f"Guardado {ARCHIVO_CSV.name}: {len(crudo)} filas x {crudo.shape[1]} columnas")

    # Resumen por serie: nombre oficial devuelto por el BCRP, datos válidos y rango efectivo
    validos = crudo[~crudo["valor"].astype(str).str.lower().isin(["n.d.", "nd", ""])]
    for (frec, cod), g in crudo.groupby(["frecuencia", "codigo_serie"], sort=False):
        v = validos[validos["codigo_serie"] == cod]
        variable = next(n for s in SERIES.values() for c, n in s.items() if c == cod)
        log.info(f"Resumen {cod} -> {variable} ({frec}) | BCRP: '{g['nombre_serie'].iloc[0]}' | "
                 f"{len(g)} periodos, {len(v)} con dato, desde "
                 f"{v['periodo'].iloc[0] if len(v) else '-'} hasta {v['periodo'].iloc[-1] if len(v) else '-'}")
    log.info("Fin de 01_extraccion_api.py: OK")


if __name__ == "__main__":
    main()
