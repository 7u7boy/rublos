import datetime as dt, math, random, sys, os, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import forecast as F


def sintetica(n_dias=1100, vol=0.01, seed=1, deriva=0.0, reversion=0.0, inicio=80.0):
    """Serie de días hábiles: paseo aleatorio (con deriva / reversión a la media opcionales)."""
    rnd = random.Random(seed)
    d = dt.date(2023, 1, 2)
    v, media, out = inicio, inicio, []
    while len(out) < n_dias:
        if d.weekday() < 5:
            v *= math.exp(deriva + reversion * (math.log(media / v)) + rnd.gauss(0, vol))
            out.append((d, v))
        d += dt.timedelta(days=1)
    return out


class Pruebas(unittest.TestCase):
    def test_sin_mirar_al_futuro(self):
        a = sintetica(seed=3)
        t = 700
        b = list(a)
        for i in range(t + 1, len(b)):          # alteramos TODO el futuro
            b[i] = (b[i][0], b[i][1] * 3.0)
        ha, hb = F.Historia(a), F.Historia(b)
        ea, sa = F.calcular(ha, t)
        eb, sb = F.calcular(hb, t)
        self.assertEqual(ea, eb)
        self.assertEqual(sa, sb)
        ra, rb = F.backtest(F.Historia(a[: t + 1]), paso=14), F.backtest(F.Historia(b[: t + 1]), paso=14)
        self.assertEqual(ra, rb)

    def test_probabilidades_validas(self):
        h = F.Historia(sintetica())
        est, stats = F.calcular(h)
        for k, s in stats.items():
            self.assertIsNotNone(s)
            self.assertAlmostEqual(s["p_sube"] + s["p_baja"], 1.0)
            self.assertLessEqual(s["p10"], s["mediana"])
            self.assertLessEqual(s["mediana"], s["p90"])
        self.assertTrue(0 <= est["rango90"] <= 100)

    def test_deriva_clara_se_detecta(self):
        h = F.Historia(sintetica(deriva=0.004, vol=0.004, seed=5))   # sube casi siempre
        _, stats = F.calcular(h)
        self.assertGreater(stats["mes"]["p_sube"], 0.8)
        self.assertTrue(stats["mes"]["significativo"])

    def test_paseo_aleatorio_no_da_ventaja(self):
        """En un paseo aleatorio puro la regla no debe ganar de forma sistemática."""
        difs = []
        for seed in range(6):
            bt = F.backtest(F.Historia(sintetica(seed=seed, vol=0.012)), paso=7)
            difs.append(bt["regla_vs_enviar_ya_pct"])
        media = sum(difs) / len(difs)
        print("paseo aleatorio: diferencia media regla vs enviar ya =", round(media, 3), "%", [round(x, 2) for x in difs])
        self.assertLess(abs(media), 1.0)

    def test_recomendar_casos(self):
        est = {"rango90": 90.0}
        sig = lambda p: {"p_sube": p, "significativo": True}
        no = {"p_sube": 0.5, "significativo": False}
        self.assertEqual(F.recomendar(est, {"semana": no, "mes": no}, 1)["veredicto"], "ENVIAR_YA")
        self.assertEqual(F.recomendar(est, {"semana": no, "mes": no}, None)["veredicto"], "ENVIAR_YA")   # alto
        self.assertEqual(F.recomendar({"rango90": 50.0}, {"semana": no, "mes": no}, None)["veredicto"], "MITAD")
        self.assertEqual(F.recomendar({"rango90": 50.0}, {"semana": sig(0.62), "mes": sig(0.62)}, None)["veredicto"], "ESPERAR")
        self.assertEqual(F.recomendar({"rango90": 50.0}, {"semana": sig(0.62), "mes": sig(0.62)}, 5)["veredicto"], "MITAD")
        self.assertEqual(F.recomendar({"rango90": 50.0}, {"semana": sig(0.38), "mes": sig(0.38)}, None)["veredicto"], "ENVIAR_YA")


if __name__ == "__main__":
    unittest.main(verbosity=2)
