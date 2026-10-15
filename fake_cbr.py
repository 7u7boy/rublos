"""Servidor de PRUEBA que imita al Banco Central (datos sintéticos, solo para ver la app funcionando)."""
import datetime as dt, json, math, random, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

def serie(fin=dt.date(2026, 10, 13)):
    rnd = random.Random(7)
    d, v, out = fin - dt.timedelta(days=1100), 78.0, []
    media = 82.0
    while d <= fin:
        if d.weekday() < 5:
            v *= math.exp(0.02 * math.log(media / v) + rnd.gauss(0, 0.009))
            out.append([d, v])
        d += dt.timedelta(days=1)
    out[-1][1] = 83.9153            # valores reales de hoy según el Banco Central
    out[-2][1] = 84.9048
    return out

DATOS = serie()

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        p = urlparse(self.path).path
        if p.endswith("XML_dynamic.asp"):
            filas = "".join(f'<Record Date="{d:%d.%m.%Y}" Id="R01235"><Nominal>1</Nominal><Value>{v:.4f}</Value><VunitRate>{v:.4f}</VunitRate></Record>'.replace(".", ",", 0) for d, v in DATOS)
            filas = filas.replace("<Value>", "<Value>").replace(".", ".")
            # decimales con coma, como el BCR
            import re
            filas = re.sub(r"<(Value|VunitRate)>(\d+)\.(\d+)<", r"<\1>\2,\3<", filas)
            xml = f'<?xml version="1.0" encoding="windows-1251"?><ValCurs ID="R01235" DateRange1="x" DateRange2="y" name="x">{filas}</ValCurs>'
            body = xml.encode("cp1251")
            self.send_response(200); self.send_header("Content-Type", "text/xml; charset=windows-1251")
        elif p.endswith("daily_json.js") and "/archive/" not in p:
            d, v = DATOS[-1]
            body = json.dumps({"Date": f"{d}T11:30:00+03:00", "Valute": {"USD": {"Nominal": 1, "Value": v}}}).encode()
            self.send_response(200); self.send_header("Content-Type", "application/javascript")
        else:
            body = b"no"; self.send_response(404)
        self.end_headers(); self.wfile.write(body)

if __name__ == "__main__":
    HTTPServer(("127.0.0.1", int(sys.argv[1]) if len(sys.argv) > 1 else 8799), H).serve_forever()
