"""Estadística del tipo de cambio USD -> RUB. Funciones puras, sin red ni disco.

Importante: esto NO predice el futuro. Mide con qué frecuencia el cambio subió o
bajó en el pasado reciente y compara el nivel de hoy con los últimos meses.
Todo se calcula usando solo datos anteriores al día evaluado (sin mirar al futuro).
"""
import math
from bisect import bisect_right

HORIZONTES = {"dia": 1, "semana": 7, "mes": 30}   # días de calendario
LOOKBACK_DIAS = 1095          # orígenes considerados: últimos 3 años
VIDA_MEDIA = 270              # días; las épocas recientes pesan más
VENTANA_RANGO = 90            # para ver si hoy está alto o bajo vs el trimestre
BANDA_ESTADO = 20             # +-20 puntos de percentil = "situación parecida"
MIN_MUESTRAS_COND = 40
UMBRAL_EDGE = 0.10


class Historia:
    """Serie ordenada por fecha. `ords` son fechas como ordinales (enteros)."""

    def __init__(self, serie):
        serie = sorted(serie)
        self.fechas = [d for d, _ in serie]
        self.vals = [float(v) for _, v in serie]
        self.ords = [d.toordinal() for d in self.fechas]
        self.rangos = self._rangos()

    def __len__(self):
        return len(self.vals)

    def valor_en(self, ordinal, hasta):
        """Último valor con fecha <= ordinal, sin usar índices > hasta."""
        i = bisect_right(self.ords, ordinal, 0, hasta + 1) - 1
        return self.vals[i] if i >= 0 else None

    def _rangos(self):
        """Percentil (0-100) de cada valor dentro de los 90 días ANTERIORES (inclusive)."""
        out, lo = [], 0
        for i, o in enumerate(self.ords):
            while self.ords[lo] < o - VENTANA_RANGO:
                lo += 1
            ventana = self.vals[lo:i + 1]
            if len(ventana) < 20:
                out.append(None)
            else:
                v = self.vals[i]
                menores = sum(1 for x in ventana if x < v)
                iguales = sum(1 for x in ventana if x == v)
                out.append(100.0 * (menores + 0.5 * iguales) / len(ventana))
        return out


def _cuantil(pares, q):
    """Cuantil ponderado. pares = [(valor, peso)]."""
    pares = sorted(pares)
    total = sum(w for _, w in pares)
    acum = 0.0
    for v, w in pares:
        acum += w
        if acum >= q * total:
            return v
    return pares[-1][0]


def _resumen(muestras, h, condicional):
    """muestras = [(retorno, peso)]."""
    pesos = [w for _, w in muestras]
    sw = sum(pesos)
    sw2 = sum(w * w for w in pesos)
    n_kish = (sw * sw / sw2) if sw2 else 0.0
    n_indep = max(1.0, n_kish / max(1, h))     # las ventanas se solapan: pocas son independientes
    p_up = sum(w if r > 0 else (0.5 * w if r == 0 else 0.0) for r, w in muestras) / sw
    margen = 1.96 * math.sqrt(0.25 / n_indep)
    return {
        "h": h,
        "p_sube": p_up, "p_baja": 1 - p_up,
        "mediana": _cuantil(muestras, 0.5),
        "p10": _cuantil(muestras, 0.10), "p90": _cuantil(muestras, 0.90),
        "n": len(muestras), "n_indep": n_indep,
        "margen_azar": margen,
        "significativo": abs(p_up - 0.5) > margen,
        "condicional": condicional,
    }


def estadisticas_horizonte(hist, hasta, h, rango_hoy):
    """Estadísticas de cambio a h días usando solo datos con índice <= hasta."""
    fin = hist.ords[hasta]
    todas, cond = [], []
    for j in range(hasta + 1):
        o = hist.ords[j]
        if o < fin - LOOKBACK_DIAS:
            continue
        if o + h > fin:
            break
        despues = hist.valor_en(o + h, hasta)
        r = despues / hist.vals[j] - 1.0
        w = 0.5 ** ((fin - o) / VIDA_MEDIA)
        todas.append((r, w))
        rj = hist.rangos[j]
        if rango_hoy is not None and rj is not None and abs(rj - rango_hoy) <= BANDA_ESTADO:
            cond.append((r, w))
    if len(todas) < 20:
        return None
    if len(cond) >= MIN_MUESTRAS_COND:
        res = _resumen(cond, h, True)
        res["incondicional_p_sube"] = _resumen(todas, h, False)["p_sube"]
        return res
    res = _resumen(todas, h, False)
    res["incondicional_p_sube"] = res["p_sube"]
    return res


def _desv(logs):
    if len(logs) < 2:
        return None
    m = sum(logs) / len(logs)
    return math.sqrt(sum((x - m) ** 2 for x in logs) / (len(logs) - 1))


def estado(hist, hasta):
    v = hist.vals[hasta]
    o = hist.ords[hasta]
    prev = hist.vals[hasta - 1] if hasta > 0 else None
    def ventana(dias):
        return [hist.vals[i] for i in range(hasta + 1) if hist.ords[i] >= o - dias]
    w30, w90, w365 = ventana(30), ventana(90), ventana(365)
    logs = [math.log(hist.vals[i] / hist.vals[i - 1]) for i in range(1, hasta + 1)]
    n30 = sum(1 for i in range(hasta + 1) if hist.ords[i] >= o - 30)
    base20 = hist.vals[max(0, hasta - 20)]
    def rango(w):
        return 100.0 * (sum(1 for x in w if x < v) + 0.5 * sum(1 for x in w if x == v)) / len(w)
    return {
        "fecha": hist.fechas[hasta].isoformat(),
        "valor": v,
        "previo": prev,
        "cambio_dia_pct": (v / prev - 1) * 100 if prev else None,
        "rango90": hist.rangos[hasta] if hist.rangos[hasta] is not None else rango(w90),
        "rango365": rango(w365),
        "prom30": sum(w30) / len(w30), "prom90": sum(w90) / len(w90),
        "min30": min(w30), "max30": max(w30), "min90": min(w90), "max90": max(w90),
        "tendencia20_pct": (v / base20 - 1) * 100,
        "vol30": _desv(logs[-n30:]) if n30 > 2 else None,
        "vol365": _desv(logs[-250:]),
    }


def calcular(hist, hasta=None):
    """Estado + estadísticas para los tres horizontes, usando datos hasta `hasta`."""
    hasta = len(hist) - 1 if hasta is None else hasta
    est = estado(hist, hasta)
    stats = {k: estadisticas_horizonte(hist, hasta, h, est["rango90"]) for k, h in HORIZONTES.items()}
    return est, stats


def _fmt_pct(x):
    return f"{x:.0f} %"


def recomendar(est, stats, dias_limite=None):
    """Devuelve la recomendación. dias_limite = en cuántos días necesita el dinero (None = sin apuro)."""
    sem, mes = stats.get("semana"), stats.get("mes")
    edge = 0.0
    for s in (sem, mes):
        if s and s["significativo"]:
            edge += s["p_sube"] - 0.5
    rango = est["rango90"]
    alto = rango is not None and rango >= 75
    bajo = rango is not None and rango <= 25

    if dias_limite is not None and dias_limite <= 2:
        veredicto = "ENVIAR_YA"
        razon = "Lo necesita pronto: esperar no compensa el riesgo de que el cambio baje."
    elif edge >= UMBRAL_EDGE:
        if dias_limite is None or dias_limite >= 10:
            veredicto = "ESPERAR"
            razon = ("En situaciones parecidas, el cambio subió con más frecuencia de lo normal. "
                     "Puede valer la pena esperar unos días.")
        else:
            veredicto = "MITAD"
            razon = ("Hay una leve señal de subida, pero el plazo es corto. "
                     "Envíe la mitad hoy y la otra mitad antes del límite.")
    elif edge <= -UMBRAL_EDGE:
        veredicto = "ENVIAR_YA"
        razon = "En situaciones parecidas, el cambio bajó con más frecuencia de lo normal. Mejor aprovechar hoy."
    elif alto:
        veredicto = "ENVIAR_YA"
        razon = (f"Hoy cada dólar rinde más rublos que en el {_fmt_pct(rango)} de los últimos 3 meses. "
                 "No hay señal clara de que siga subiendo.")
    elif bajo:
        veredicto = "MITAD"
        razon = (f"Hoy el dólar rinde menos que en el {_fmt_pct(100 - rango)} de los últimos 3 meses, "
                 "y no hay señal clara de mejora. Repartir el envío reduce el riesgo.")
    else:
        veredicto = "MITAD"
        razon = ("El cambio está en un nivel normal y no hay una señal clara. "
                 "Repartir el envío en dos partes es lo más seguro.")
    return {"veredicto": veredicto, "razon": razon, "edge": edge, "dias_limite": dias_limite}


def _simular(hist, t, veredicto, hasta_fin):
    """Cuántos rublos por dólar se obtienen según el veredicto, para una necesidad que nace en t."""
    o = hist.ords[t]
    r0 = hist.vals[t]
    f = lambda dias: hist.valor_en(o + dias, hasta_fin)
    if veredicto == "ENVIAR_YA":
        return r0
    if veredicto == "MITAD":
        return 0.5 * r0 + 0.5 * f(14)
    return f(30)   # ESPERAR: se envía al final del plazo de 30 días


def backtest(hist, paso=7, historia_min=365, plazo=30):
    """Prueba la regla hacia atrás: en cada fecha usa solo el pasado y compara contra enviar todo ya."""
    ult = len(hist) - 1
    fin = hist.ords[ult]
    filas = []
    for t in range(len(hist)):
        if hist.ords[t] - hist.ords[0] < historia_min:
            continue
        if hist.ords[t] + plazo > fin:
            break
        if filas and hist.ords[t] - filas[-1]["o"] < paso:
            continue
        est, stats = calcular(hist, t)
        if any(s is None for s in stats.values()):
            continue
        rec = recomendar(est, stats, None)
        base = hist.vals[t]
        regla = _simular(hist, t, rec["veredicto"], ult)
        mitad = _simular(hist, t, "MITAD", ult)
        filas.append({"o": hist.ords[t], "v": rec["veredicto"], "regla": regla / base - 1,
                      "mitad": mitad / base - 1})
    if not filas:
        return None
    def media_se(xs):
        n = len(xs)
        m = sum(xs) / n
        sd = math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
        n_indep = max(1.0, n * paso / plazo)       # ventanas solapadas
        return m * 100, 100 * sd / math.sqrt(n_indep)
    reg, mit = [f["regla"] for f in filas], [f["mitad"] for f in filas]
    m_reg, se_reg = media_se(reg)
    m_mit, se_mit = media_se(mit)
    conteo = {}
    for f in filas:
        conteo[f["v"]] = conteo.get(f["v"], 0) + 1
    return {
        "n": len(filas), "paso_dias": paso, "plazo_dias": plazo,
        "regla_vs_enviar_ya_pct": m_reg, "regla_se": se_reg,
        "mitad_vs_enviar_ya_pct": m_mit, "mitad_se": se_mit,
        "gana_regla_pct": 100 * sum(1 for x in reg if x > 0) / len(reg),
        "veredictos": conteo,
        "desde": hist.fechas[0].isoformat(),
        "hasta": hist.fechas[ult].isoformat(),
    }
