"""Descarga y guarda el tipo de cambio oficial USD/RUB del Banco Central de Rusia.

Orden de intentos:
 1. cbr.ru  (serie completa en una sola petición)
 2. cbr-xml-daily.ru  (archivo día por día; más lento, solo si falla el 1)
 3. copia en disco de la última descarga buena (se marca como "desactualizado")
Las URLs se pueden cambiar con variables de entorno (útil para pruebas).
"""
import datetime as dt
import json
import logging
import os
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

import requests

log = logging.getLogger("fx")

URL_DINAMICA = os.getenv("FX_URL_DINAMICA", "https://www.cbr.ru/scripts/XML_dynamic.asp")
URL_ARCHIVO = os.getenv("FX_URL_ARCHIVO", "https://www.cbr-xml-daily.ru/archive/{y:04d}/{m:02d}/{d:02d}/daily_json.js")
URL_DIARIO = os.getenv("FX_URL_DIARIO", "https://www.cbr-xml-daily.ru/daily_json.js")
ID_USD = "R01235"
ARCHIVO_CACHE = os.getenv("FX_CACHE_FILE", os.path.join(os.path.dirname(__file__), "data", "usd_rub.json"))
TTL = int(os.getenv("FX_TTL_SEGUNDOS", str(30 * 60)))
DIAS_HISTORIA = int(os.getenv("FX_DIAS_HISTORIA", "1095"))
UA = {"User-Agent": "Mozilla/5.0 (compatible; dolar-rublo/1.0)"}

_lock = threading.Lock()
_memoria = {"datos": None, "t": 0.0}


def parsear_xml_dinamico(contenido: bytes):
    raiz = ET.fromstring(contenido)
    out = []
    for rec in raiz.iter("Record"):
        fecha = dt.datetime.strptime(rec.get("Date"), "%d.%m.%Y").date()
        unit = rec.findtext("VunitRate")
        if unit:
            valor = float(unit.replace(",", "."))
        else:
            valor = float(rec.findtext("Value").replace(",", ".")) / int(rec.findtext("Nominal", "1"))
        out.append((fecha, valor))
    return out


def _desde_dinamica(hoy):
    r = requests.get(URL_DINAMICA, params={
        "date_req1": (hoy - dt.timedelta(days=DIAS_HISTORIA)).strftime("%d/%m/%Y"),
        "date_req2": (hoy + dt.timedelta(days=2)).strftime("%d/%m/%Y"),
        "VAL_NM_RQ": ID_USD}, headers=UA, timeout=25)
    r.raise_for_status()
    serie = parsear_xml_dinamico(r.content)
    if len(serie) < 100:
        raise ValueError(f"serie demasiado corta ({len(serie)} filas)")
    return serie


def _json_usd(texto):
    d = json.loads(texto)
    fecha = dt.datetime.fromisoformat(d["Date"]).date()
    usd = d["Valute"]["USD"]
    return fecha, usd["Value"] / usd.get("Nominal", 1)


def _desde_archivo(hoy, dias=400):
    def uno(d):
        try:
            r = requests.get(URL_ARCHIVO.format(y=d.year, m=d.month, d=d.day), headers=UA, timeout=15)
            if r.status_code != 200:
                return None
            return _json_usd(r.text)
        except Exception:
            return None
    fechas = [hoy - dt.timedelta(days=i) for i in range(dias)]
    with ThreadPoolExecutor(max_workers=16) as ex:
        res = [x for x in ex.map(uno, fechas) if x]
    serie = sorted(set(res))
    if len(serie) < 100:
        raise ValueError(f"archivo incompleto ({len(serie)} filas)")
    return serie


def _ultimo_diario():
    r = requests.get(URL_DIARIO, headers=UA, timeout=15)
    r.raise_for_status()
    return _json_usd(r.text)


def _leer_cache():
    try:
        with open(ARCHIVO_CACHE, encoding="utf-8") as f:
            d = json.load(f)
        return [(dt.date.fromisoformat(a), float(b)) for a, b in d["serie"]], d.get("fuente", "copia local")
    except Exception:
        return None, None


def _guardar_cache(serie, fuente):
    try:
        os.makedirs(os.path.dirname(ARCHIVO_CACHE), exist_ok=True)
        tmp = ARCHIVO_CACHE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"fuente": fuente, "serie": [(d.isoformat(), v) for d, v in serie]}, f)
        os.replace(tmp, ARCHIVO_CACHE)
    except Exception as e:
        log.warning("No pude guardar la copia local: %s", e)


def cargar(forzar=False):
    """Devuelve {"serie": [(fecha, valor)], "fuente": str, "actualizado": epoch, "desactualizado": bool}."""
    with _lock:
        ahora = time.time()
        if not forzar and _memoria["datos"] and ahora - _memoria["t"] < TTL:
            return _memoria["datos"]
        hoy = dt.date.today()
        serie, fuente, desact = None, None, False
        for nombre, fn in (("cbr.ru", _desde_dinamica), ("cbr-xml-daily.ru", _desde_archivo)):
            try:
                serie = fn(hoy)
                fuente = nombre
                break
            except Exception as e:
                log.warning("Fuente %s falló: %s", nombre, e)
        if serie is not None:
            try:                                  # asegura incluir el último valor publicado
                serie = sorted(set(serie) | {_ultimo_diario()})
            except Exception as e:
                log.info("daily_json no disponible: %s", e)
            previa, _ = _leer_cache()
            if previa:                            # la copia acumula días que la fuente ya no devuelva
                mezcla = dict(previa)
                mezcla.update(dict(serie))
                serie = sorted(mezcla.items())
            _guardar_cache(serie, fuente)
        else:
            serie, fuente = _leer_cache()
            desact = True
            if serie is None:
                if _memoria["datos"]:             # mejor datos viejos en memoria que nada
                    return _memoria["datos"]
                raise RuntimeError("No se pudo obtener el tipo de cambio y no hay copia local.")
        if desact:
            try:
                actualizado = os.path.getmtime(ARCHIVO_CACHE)
            except OSError:
                actualizado = ahora
            _memoria["t"] = ahora - TTL + 120          # reintenta en ~2 minutos
        else:
            actualizado = ahora
            _memoria["t"] = ahora
        datos = {"serie": serie, "fuente": fuente, "actualizado": actualizado, "desactualizado": desact}
        _memoria["datos"] = datos
        return datos
