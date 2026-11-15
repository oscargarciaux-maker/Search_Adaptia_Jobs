// Paso 9 (15 nov): textos visibles con contraste insuficiente (WCAG AA) frente a su fondo opaco más cercano.
export const revisarContraste = () => {
  const parse = (c: string) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1]
      .split(/[ ,/]+/)
      .filter(Boolean)
      .map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const lum = (c: { r: number; g: number; b: number }) => {
    const f = (v: number) => {
      v /= 255;
      return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
    };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const mezcla = (a: any, b: any) => ({
    r: a.r * a.a + b.r * (1 - a.a),
    g: a.g * a.a + b.g * (1 - a.a),
    b: a.b * a.a + b.b * (1 - a.a),
    a: 1,
  });
  const fondo = (el: Element | null): any => {
    const capas: any[] = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage.includes("gradient")) {
        const m = cs.backgroundImage.match(/rgba?\([^)]+\)/);
        if (m) {
          capas.push(parse(m[0]));
          break;
        }
      }
      const b = parse(cs.backgroundColor);
      if (b && b.a > 0) {
        capas.push(b);
        if (b.a >= 1) break;
      }
    }
    let base = parse(
      getComputedStyle(document.documentElement).backgroundColor,
    ) || { r: 255, g: 255, b: 255, a: 1 };
    if (base.a < 1) base = { r: 255, g: 255, b: 255, a: 1 };
    for (let i = capas.length - 1; i >= 0; i--) base = mezcla(capas[i], base);
    return base;
  };
  const fallos: string[] = [];
  const vistos = new Set<string>();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const t = (n.textContent || "").trim();
    const el = n.parentElement;
    if (!t || !el) continue;
    const r = el.getBoundingClientRect();
    const cs = getComputedStyle(el);
    if (
      !r.width ||
      !r.height ||
      cs.visibility === "hidden" ||
      Number(cs.opacity) === 0
    )
      continue;
    if (
      el.closest(
        "[aria-hidden='true'], .marca-agua, button:disabled, [role='tooltip']",
      )
    )
      continue;
    let oculto = false;
    for (let e: Element | null = el; e; e = e.parentElement)
      if (Number(getComputedStyle(e).opacity) < 0.5) oculto = true;
    if (oculto) continue;
    const c = parse(cs.color)!;
    const f = fondo(el);
    const col = c.a < 1 ? mezcla(c, f) : c;
    const L1 = lum(col),
      L2 = lum(f);
    const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const px = parseFloat(cs.fontSize);
    const peso = Number(cs.fontWeight);
    const minimo = px >= 18.66 || (px >= 14 && peso >= 700) ? 3 : 4.5;
    if (ratio < minimo) {
      const clave = `${el.tagName}.${el.className}|${cs.color}|${t.slice(0, 30)}`;
      if (vistos.has(clave)) continue;
      vistos.add(clave);
      fallos.push(
        `${ratio.toFixed(2)} ${el.tagName.toLowerCase()}.${String(el.className).split(" ").join(".")} «${t.slice(0, 40)}» ${cs.color} sobre rgb(${Math.round(f.r)},${Math.round(f.g)},${Math.round(f.b)})`,
      );
    }
  }
  return fallos;
};
