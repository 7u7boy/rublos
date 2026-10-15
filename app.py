import datetime as dt
import logging
import os
import threading

from flask import Flask, jsonify, render_template, request

import forecast as F
import fx_data

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

_cache = {"clave": None, "calculo": None}
_lock = threading.Lock()
LIMITES_VALIDOS = {2, 7, 14, 30}


def _calculo():
    """Estadísticas + prueba histórica; se recalculan solo cuando llegan datos nuevos."""
    datos = fx_data.cargar()
    clave = (datos["actualizado"], len(datos["serie"]), datos["serie"][-1])
    with _lock:
        if _cache["clave"] == clave:
            return datos, _cache["calculo"]
        hist = F.Historia(datos["serie"])
        est, stats = F.calcular(hist)
        bt = F.backtest(hist)
        _cache.update(clave=clave, calculo={"hist": hist, "est": est, "stats": stats, "bt": bt})
        return datos, _cache["calculo"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return "ok"


@app.route("/api/data")
def api_data():
    try:
        datos, c = _calculo()
    except Exception as e:
        logging.exception("sin datos")
        return jsonify({"error": "No pudimos obtener el tipo de cambio ahora. Intenta de nuevo en unos minutos."}), 503
    try:
        limite = int(request.args.get("necesito_en", "14"))
    except ValueError:
        limite = 14
    limite = limite if limite in LIMITES_VALIDOS else 14
    rec = F.recomendar(c["est"], c["stats"], limite if limite <= 14 else None)
    hist = c["hist"]
    ultimo = dt.date.fromisoformat(c["est"]["fecha"])
    return jsonify({
        "estado": c["est"],
        "horizontes": c["stats"],
        "recomendacion": rec,
        "backtest": c["bt"],
        "serie": [[d.isoformat(), round(v, 4)] for d, v in zip(hist.fechas, hist.vals)
                  if d >= ultimo - dt.timedelta(days=370)],
        "fuente": datos["fuente"],
        "desactualizado": datos["desactualizado"],
        "actualizado": dt.datetime.fromtimestamp(datos["actualizado"], dt.timezone.utc).isoformat(),
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
