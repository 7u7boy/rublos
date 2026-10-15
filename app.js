(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const fmt = (n, d = 2) => n.toLocaleString("es-EC", { minimumFractionDigits: d, maximumFractionDigits: d });
  const fmt0 = (n) => Math.round(n).toLocaleString("es-EC");
  const pct0 = (p) => Math.round(p * 100);

  const store = {
    get(k, def) { try { const v = localStorage.getItem(k); return v === null ? def : JSON.parse(v); } catch { return def; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
  };
  const S = {
    plazo: store.get("plazo", 14),
    monto: store.get("monto", 200),
    rango: store.get("rango", 90),
    canales: store.get("canales", [{ n: "", tc: "", fijo: "", pct: "" }]),
    data: null,
  };

  const fechaLarga = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("es-EC", { day: "numeric", month: "long" });
  const fechaCorta = (iso) => new Date(iso + "T12:00:00").toLocaleDateString("es-EC", { day: "numeric", month: "short" });
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };

  // Semáforo: rojo arriba, amarillo en medio, verde abajo. Se enciende la luz que toca.
  const LUZ = { ESPERAR: 0, MITAD: 1, ENVIAR_YA: 2 };
  const CLASE = ["r", "a", "v"];
  function semaforo(ver) {
    const on = LUZ[ver];
    let g = '<svg viewBox="0 0 58 118"><rect class="caja" x="1" y="1" width="56" height="116" rx="18"/>';
    for (let i = 0; i < 3; i++) {
      const cy = 21 + i * 38;
      g += `<circle class="foco ${i === on ? "on " + CLASE[i] : ""}" cx="29" cy="${cy}" r="14"/>`;
    }
    return g + "</svg>";
  }

  async function cargar() {
    try {
      const r = await fetch(`/api/data?necesito_en=${S.plazo}`, { cache: "no-store" });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || "error");
      S.data = d;
      pintar();
    } catch (e) {
      $("ver-titulo").textContent = "No pudimos cargar el cambio";
      $("ver-razon").textContent = "Revise su conexión e intente de nuevo en unos minutos.";
      $("actualizado").textContent = "Sin conexión";
    }
  }

  function marcar(grupo, valor) {
    grupo.querySelectorAll("button").forEach((b) => b.setAttribute("aria-checked", String(Number(b.dataset.dias) === valor)));
  }

  function pintar() {
    const d = S.data, e = d.estado;
    marcar($("chips-plazo"), S.plazo);
    marcar($("chips-rango"), S.rango);
    $("monto").value = S.monto;

    // Encabezado y cambio
    const min = Math.max(0, Math.round((Date.now() - new Date(d.actualizado).getTime()) / 60000));
    $("actualizado").textContent = d.desactualizado
      ? "No pudimos actualizar. Mostrando el último dato guardado."
      : `Cambio oficial del ${fechaLarga(e.fecha)}`;
    animarValor(e.valor);
    $("serie").textContent = "№ " + e.fecha.split("-").reverse().join(".");
    pintarMini();
    const dif = $("dif"); dif.textContent = "";
    if (e.previo) {
      const c = e.cambio_dia_pct, sube = c >= 0;
      const s = el("span", sube ? "sube" : "baja", `${sube ? "▲ Subió" : "▼ Bajó"} ${fmt(Math.abs(c))} %`);
      dif.append(s, document.createTextNode(` desde la vez anterior (${fmt(e.previo)} ₽). ${sube ? "Cada dólar rinde un poco más." : "Cada dólar rinde un poco menos."}`));
    }

    // Veredicto
    const rec = d.recomendacion, v = $("veredicto");
    v.dataset.v = rec.veredicto;
    $("ver-icono").innerHTML = semaforo(rec.veredicto);   // SVG fijo del programa, sin datos externos
    const sem = S.plazo === 7 ? "una semana" : "2 semanas";
    $("ver-titulo").textContent = {
      ENVIAR_YA: "Conviene enviar hoy",
      MITAD: `Envíe la mitad hoy y la otra mitad en ${sem}`,
      ESPERAR: "Conviene esperar unos días",
    }[rec.veredicto];
    $("ver-razon").textContent = rec.razon + (rec.veredicto === "ESPERAR" ? " Vuelva a revisar mañana." : "");

    pintarCalculo();
    pintarHorizontes();
    pintarGrafico();
    pintarTabla();
    pintarCanales();
    pintarComo();
  }

  let primera = true;
  function animarValor(v) {
    const nodo = $("valor");
    const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!primera || quieto) { nodo.textContent = fmt(v); primera = false; return; }
    primera = false;
    const t0 = performance.now(), dur = 900, ini = v * 0.88;
    const paso = (t) => {
      const k = Math.min(1, (t - t0) / dur), ease = 1 - Math.pow(1 - k, 3);
      nodo.textContent = fmt(ini + (v - ini) * ease);
      if (k < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  }

  function pintarMini() {
    const svg = $("mini"); svg.textContent = "";
    const pts = S.data.serie.slice(-30).map(([, v]) => v);
    if (pts.length < 2) return;
    const lo = Math.min(...pts), hi = Math.max(...pts), pad = (hi - lo) * 0.15 || 1;
    const x = (i) => (i / (pts.length - 1)) * 300, y = (v) => 50 - ((v - (lo - pad)) / (hi - lo + 2 * pad)) * 46;
    const d = pts.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join("");
    const mk = (tag, at) => { const n = document.createElementNS(NS, tag); for (const k in at) n.setAttribute(k, at[k]); svg.appendChild(n); return n; };
    const defs = mk("defs", {}), g = document.createElementNS(NS, "linearGradient");
    g.setAttribute("id", "mg"); g.setAttribute("x1", "0"); g.setAttribute("y1", "0"); g.setAttribute("x2", "0"); g.setAttribute("y2", "1");
    [["0", ".35"], ["1", "0"]].forEach(([o, op]) => { const st = document.createElementNS(NS, "stop"); st.setAttribute("offset", o); st.setAttribute("stop-color", "#F2C14E"); st.setAttribute("stop-opacity", op); g.appendChild(st); });
    defs.appendChild(g);
    mk("path", { class: "a", d: `${d}L300,54L0,54Z` });
    mk("path", { class: "l", d });
  }

  function pintarCalculo() {
    const d = S.data, v = d.estado.valor, monto = Number(S.monto) || 0;
    $("recibe").textContent = fmt0(monto * v);
    const m = d.horizontes.mes;
    $("rango-mes").textContent = m
      ? `Dentro de un mes podría ser entre ${fmt0(monto * v * (1 + m.p10))} y ${fmt0(monto * v * (1 + m.p90))} ₽ (8 de cada 10 veces).`
      : "";
  }

  function pintarHorizontes() {
    const cont = $("horizontes"); cont.textContent = "";
    const v = S.data.estado.valor;
    [["dia", "Mañana"], ["semana", "En una semana"], ["mes", "En un mes"]].forEach(([k, titulo]) => {
      const h = S.data.horizontes[k]; if (!h) return;
      const fila = el("div", "hor");
      fila.append(el("h3", "", titulo));
      const barra = el("div", "barra");
      const s = el("span", "s"), b = el("span", "b");
      s.style.width = pct0(h.p_sube) + "%"; b.style.width = pct0(h.p_baja) + "%";
      barra.append(s, b);
      const etq = el("div", "etq");
      etq.append(el("span", "s", `Sube ${pct0(h.p_sube)} %`), el("span", "b", `Baja ${pct0(h.p_baja)} %`));
      const msg = h.significativo
        ? (h.p_sube > 0.5 ? "En situaciones parecidas, tendió a subir." : "En situaciones parecidas, tendió a bajar.")
        : "Casi un volado: no hay una tendencia clara.";
      const rango = `Lo más probable: entre ${fmt(v * (1 + h.p10))} y ${fmt(v * (1 + h.p90))} ₽ por dólar (8 de cada 10 veces).`;
      fila.append(barra, etq, el("p", "claro", msg), el("p", "", rango));
      cont.append(fila);
    });
  }

  // ---------- Gráfico ----------
  let cursor = null;
  function pintarGrafico() {
    const cont = $("grafico"); cont.textContent = "";
    const serie = S.data.serie;
    const ultimo = new Date(serie[serie.length - 1][0] + "T12:00:00");
    const desde = new Date(ultimo.getTime() - S.rango * 86400000);
    const pts = serie.filter(([f]) => new Date(f + "T12:00:00") >= desde).map(([f, v]) => ({ f, v, t: new Date(f + "T12:00:00").getTime() }));
    if (pts.length < 2) return;
    const W = Math.max(280, cont.clientWidth || 600), H = W < 420 ? 230 : 280;
    const M = { l: 46, r: 62, t: 14, b: 28 };
    const vals = pts.map((p) => p.v), lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.12 || 1;
    const y0 = lo - pad, y1 = hi + pad;
    const x = (t) => M.l + ((t - pts[0].t) / (pts[pts.length - 1].t - pts[0].t)) * (W - M.l - M.r);
    const y = (v) => H - M.b - ((v - y0) / (y1 - y0)) * (H - M.t - M.b);

    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("tabindex", "0");
    svg.setAttribute("aria-label", "Gráfico de líneas. Use las flechas izquierda y derecha para ver cada día.");
    const add = (tag, attrs, parent = svg) => { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); parent.appendChild(n); return n; };

    // cuadrícula y ejes (4 marcas redondas)
    const paso = [0.5, 1, 2, 5, 10].find((p) => (y1 - y0) / p <= 5) || 10;
    for (let tv = Math.ceil(y0 / paso) * paso; tv <= y1; tv += paso) {
      add("line", { class: "grid", x1: M.l, x2: W - M.r, y1: y(tv), y2: y(tv) });
      const t = add("text", { x: M.l - 8, y: y(tv) + 4, "text-anchor": "end" }); t.textContent = fmt(tv, paso < 1 ? 1 : 0);
    }
    const nx = W < 420 ? 3 : 5;
    for (let i = 0; i < nx; i++) {
      const p = pts[Math.round((i * (pts.length - 1)) / (nx - 1))];
      const t = add("text", { x: x(p.t), y: H - 6, "text-anchor": i === 0 ? "start" : i === nx - 1 ? "end" : "middle" });
      t.textContent = fechaCorta(p.f);
    }
    const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join("");
    add("path", { class: "area", d: `${d}L${x(pts[pts.length - 1].t)},${H - M.b}L${x(pts[0].t)},${H - M.b}Z` });
    add("path", { class: "linea", d });
    const fin = pts[pts.length - 1];
    add("circle", { class: "punto", cx: x(fin.t), cy: y(fin.v), r: 5 });
    const lab = add("text", { class: "fin", x: x(fin.t) + 10, y: y(fin.v) + 5 }); lab.textContent = fmt(fin.v);

    const cruz = add("line", { class: "cruz", y1: M.t, y2: H - M.b, visibility: "hidden" });
    const marca = add("circle", { class: "punto", r: 5, visibility: "hidden" });
    const tip = el("div", "tip"); tip.hidden = true;
    const tipV = el("b"), tipF = el("span"); tip.append(tipV, tipF);
    cont.append(svg, tip);

    function mostrar(i) {
      cursor = i; const p = pts[i];
      cruz.setAttribute("x1", x(p.t)); cruz.setAttribute("x2", x(p.t)); cruz.setAttribute("visibility", "visible");
      marca.setAttribute("cx", x(p.t)); marca.setAttribute("cy", y(p.v)); marca.setAttribute("visibility", "visible");
      tipV.textContent = `${fmt(p.v)} ₽`; tipF.textContent = fechaLarga(p.f);
      tip.hidden = false;
      const escala = cont.clientWidth / W, px = x(p.t) * escala;
      tip.style.left = Math.min(Math.max(px - tip.offsetWidth / 2, 0), cont.clientWidth - tip.offsetWidth) + "px";
      tip.style.top = Math.max(y(p.v) * escala - tip.offsetHeight - 14, 0) + "px";
    }
    function ocultar() { cruz.setAttribute("visibility", "hidden"); marca.setAttribute("visibility", "hidden"); tip.hidden = true; cursor = null; }
    function indiceCercano(ev) {
      const r = svg.getBoundingClientRect();
      const px = ((ev.clientX - r.left) / r.width) * W;
      let mejor = 0, dmin = Infinity;
      pts.forEach((p, i) => { const dd = Math.abs(x(p.t) - px); if (dd < dmin) { dmin = dd; mejor = i; } });
      return mejor;
    }
    svg.addEventListener("pointermove", (ev) => mostrar(indiceCercano(ev)));
    svg.addEventListener("pointerdown", (ev) => mostrar(indiceCercano(ev)));
    svg.addEventListener("pointerleave", ocultar);
    svg.addEventListener("blur", ocultar);
    svg.addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight") return;
      ev.preventDefault();
      const i = cursor === null ? pts.length - 1 : cursor + (ev.key === "ArrowLeft" ? -1 : 1);
      mostrar(Math.min(pts.length - 1, Math.max(0, i)));
    });
  }

  function pintarTabla() {
    const tb = $("tabla").querySelector("tbody"); tb.textContent = "";
    S.data.serie.slice(-30).reverse().forEach(([f, v]) => {
      const tr = el("tr"); tr.append(el("td", "", fechaLarga(f)), el("td", "", fmt(v, 4))); tb.append(tr);
    });
  }

  // ---------- Comparador de envíos ----------
  function pintarCanales() {
    const cont = $("canales"); cont.textContent = "";
    S.canales.forEach((c, i) => {
      const f = el("div", "canal"); f.dataset.i = i;
      const campo = (cls, etiqueta, clave, ph, modo) => {
        const l = el("label", cls); l.append(el("span", "", etiqueta));
        const inp = el("input"); inp.type = modo === "texto" ? "text" : "number";
        if (modo !== "texto") { inp.inputMode = "decimal"; inp.step = "any"; inp.min = "0"; }
        inp.placeholder = ph; inp.value = c[clave];
        inp.addEventListener("input", () => { S.canales[i][clave] = inp.value; store.set("canales", S.canales); calcularCanales(); });
        l.append(inp); return l;
      };
      f.append(
        campo("nombre", "Nombre del servicio", "n", "Por ejemplo: Banco o transferencia", "texto"),
        campo("", "Cambio que le dan (₽ por US$)", "tc", "Opcional"),
        campo("", "Cargo fijo (US$)", "fijo", "0"),
        campo("", "Comisión (%)", "pct", "0"),
      );
      const res = el("div", "res"); res.append(el("span", "", "Recibiría"), el("strong", "", "—")); f.append(res);
      if (S.canales.length > 1) {
        const q = el("button", "boton-sec chico quitar", "Quitar"); q.type = "button";
        q.addEventListener("click", () => { S.canales.splice(i, 1); store.set("canales", S.canales); pintarCanales(); });
        f.append(q);
      }
      cont.append(f);
    });
    calcularCanales();
  }

  function calcularCanales() {
    const oficial = S.data.estado.valor, monto = Number(S.monto) || 0;
    const filas = [...$("canales").querySelectorAll(".canal")];
    const totales = S.canales.map((c) => {
      const tc = Number(c.tc) > 0 ? Number(c.tc) : oficial;
      return Math.max(0, (monto - (Number(c.fijo) || 0)) * (1 - (Number(c.pct) || 0) / 100)) * tc;
    });
    const mejor = Math.max(...totales);
    filas.forEach((f, i) => {
      f.querySelector(".res strong").textContent = `${fmt0(totales[i])} ₽`;
      f.classList.toggle("mejor", totales.length > 1 && totales[i] === mejor && mejor > 0);
    });
  }

  // ---------- Explicación y prueba con el pasado ----------
  function pintarComo() {
    const c = $("como"); c.textContent = "";
    const d = S.data, bt = d.backtest;
    const sec = (titulo, ...parrafos) => { c.append(el("h3", "", titulo)); parrafos.forEach((t) => c.append(el("p", "", t))); };
    sec("¿De dónde salen los datos?",
      "Del tipo de cambio oficial que publica el Banco Central de Rusia para el dólar, con los últimos tres años de historia. Se actualiza solo cada media hora.");
    sec("¿Cómo salen los porcentajes?",
      "Se buscan los días del pasado en que el cambio estaba en una situación parecida a la de hoy (por ejemplo, en la parte alta o baja de los últimos 3 meses) y se cuenta cuántas veces subió o bajó después. Los años más recientes pesan más.");
    sec("¿Qué significa «casi un volado»?",
      "Que la diferencia entre subir y bajar es tan pequeña que podría ser pura casualidad. En ese caso la aplicación no promete nada y recomienda repartir el envío en dos partes, que es lo más seguro.");
    if (bt) {
      const a = bt.regla_vs_enviar_ya_pct, se = bt.regla_se, m = bt.mitad_vs_enviar_ya_pct;
      const signo = (x) => (x >= 0 ? "+" : "−") + fmt(Math.abs(x)) + " %";
      const distinto = Math.abs(a) > 2 * se;
      const conclusion = distinto
        ? (a > 0 ? "La regla le dio una ventaja que no parece casualidad." : "La regla salió peor que enviar todo el mismo día. No hay que fiarse ciegamente de ella.")
        : "La diferencia es tan pequeña que no se puede distinguir de la casualidad. La utilidad real de la aplicación es ver el panorama y evitar decidir a ciegas.";
      sec("Prueba con el pasado",
        `Entre el ${fechaLarga(bt.desde)} y el ${fechaLarga(bt.hasta)} se probó la regla ${bt.n} veces, una por semana, usando solo lo que se sabía en cada fecha. Se comparó con enviar todo el mismo día.`);
      const t = el("table");
      const fila = (a1, b1, c1) => { const tr = el("tr"); tr.append(el("td", "", a1), el("td", "", b1), el("td", "", c1)); t.append(tr); };
      fila("Regla de la aplicación", signo(a), `± ${fmt(2 * se)} %`);
      fila("Siempre en dos mitades", signo(m), `± ${fmt(2 * bt.mitad_se)} %`);
      c.append(t);
      c.append(el("p", "", "La primera columna es la diferencia promedio de rublos recibidos frente a enviar todo el mismo día. La última es el margen de error."));
      c.append(el("p", "claro", conclusion));
    }
    sec("Una advertencia honesta",
      "Los mercados cambian por noticias que nadie conoce de antemano. Esta aplicación no adivina: ayuda a ordenar la decisión. Si necesita el dinero pronto, enviarlo pronto suele ser mejor que esperar una mejora que quizá no llegue.");
  }

  // ---------- Eventos ----------
  $("chips-plazo").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    S.plazo = Number(b.dataset.dias); store.set("plazo", S.plazo); cargar();
  });
  $("chips-rango").addEventListener("click", (e) => {
    const b = e.target.closest("button"); if (!b) return;
    S.rango = Number(b.dataset.dias); store.set("rango", S.rango); marcar($("chips-rango"), S.rango); pintarGrafico();
  });
  $("monto").addEventListener("input", (e) => {
    S.monto = e.target.value; store.set("monto", S.monto);
    if (S.data) { pintarCalculo(); calcularCanales(); }
  });
  $("canal-nuevo").addEventListener("click", () => {
    S.canales.push({ n: "", tc: "", fijo: "", pct: "" }); store.set("canales", S.canales); pintarCanales();
  });
  let rz; window.addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => S.data && pintarGrafico(), 150); });

  cargar();
  setInterval(cargar, 15 * 60 * 1000);
})();
