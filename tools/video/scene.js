// Детерминированная отрисовка кадра по времени: window.drawAt(t). Данные: window.TL (таймлайн), window.MODEL (модель состояния).
// Никакой генерации видео: каждый кадр — чистая функция (t, данные). Тексты, цифры и стрелки — слой монтажа поверх кадров классов A/B.
const FONT = '"Segoe UI","Liberation Sans","DejaVu Sans",sans-serif';
const cv = document.getElementById('c'), ctx = cv.getContext('2d');
let W = 0, H = 0, L = null;
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = x => { x = clamp(x, 0, 1); return x * x * (3 - 2 * x); };
const fmt = (x, d = 2) => x.toFixed(d).replace('.', ',');

function layout() {
  const sz = TL.canvas, p = sz.height > sz.width;
  W = sz.width; H = sz.height; cv.width = W; cv.height = H;
  const sf = TL.safe_zone_px || {};
  if (p) {
    const top = sf.top || 220, bot = sf.bottom || 380, side = sf.side || 70;
    L = { portrait: true, side, x0: side, x1: W - side, chip: { y: top, h: 64 }, cap: { y: top + 90, h: 180 },
      stage: { x: side, y: top + 300, w: W - 2 * side, h: 690 }, plates: { y: top + 1010, h: 150 },
      subs: { y: H - bot - 170, h: 170 }, fCap: 60, fSub: 56, fPlate: 34, fChip: 38 };
  } else {
    const m = sf.side || 80;
    L = { portrait: false, side: m, x0: m, x1: W - m, chip: { y: 40, h: 56 }, cap: { y: 110, h: 100 },
      stage: { x: m, y: 230, w: W - 2 * m, h: 500 }, plates: { y: 745, h: 90 },
      subs: { y: H - 215, h: 170 }, fCap: 54, fSub: 52, fPlate: 36, fChip: 34 };
  }
}

function wrap(text, maxW, font) {
  ctx.font = font; const words = String(text).split(/\s+/), lines = []; let cur = '';
  for (const w of words) { const t = cur ? cur + ' ' + w : w; if (ctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
  if (cur) lines.push(cur); return lines;
}
function textBlock(text, x, y, maxW, px, color, opts = {}) {
  const font = `${opts.weight || 'bold'} ${px}px ${FONT}`, lines = wrap(text, maxW, font), lh = px * 1.18;
  ctx.font = font; ctx.fillStyle = color; ctx.textAlign = opts.align || 'left'; ctx.textBaseline = 'top';
  const ax = opts.align === 'center' ? x + maxW / 2 : opts.align === 'right' ? x + maxW : x;
  lines.forEach((ln, i) => ctx.fillText(ln, ax, y + i * lh)); return lines.length * lh;
}
function rrect(x, y, w, h, r, fill, stroke, lw = 3) {
  ctx.beginPath(); ctx.roundRect(x, y, w, h, r);
  if (fill) { ctx.fillStyle = fill; ctx.fill(); } if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke(); }
}
function arrow(x1, y1, x2, y2, color, lw = 8, head = 30) {
  const a = Math.atan2(y2 - y1, x2 - x1); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = lw; ctx.lineCap = 'round';
  ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2 - Math.cos(a) * head * 0.6, y2 - Math.sin(a) * head * 0.6); ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x2, y2); ctx.lineTo(x2 - head * Math.cos(a - 0.45), y2 - head * Math.sin(a - 0.45));
  ctx.lineTo(x2 - head * Math.cos(a + 0.45), y2 - head * Math.sin(a + 0.45)); ctx.closePath(); ctx.fill();
}
function hexRgb(h) { h = h.replace('#', ''); return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)]; }
function mix(a, b, t) { const A = hexRgb(a), B = hexRgb(b); return `rgb(${A.map((v, i) => Math.round(v + (B[i] - v) * t)).join(',')})`; }
const C = () => TL.colors;

// ---------- вид rock_grid (требует MODEL = resistor_grid_2d) ----------
function drawGrid(stage, p, u, dur) {
  const M = MODEL, n = M.n, s = Math.min(stage.w, stage.h - 200, 640), x0 = stage.x + (stage.w - s) / 2, y0 = stage.y + 40, cs = s / n;
  const col = C(); const mode = p.mode || 'idle';
  const kinds = [col.grain_quartz, '#D98C5F', '#B39DDB', col.grain_calcite]; // кварц, полевой шпат, слюда, кальцит (условные цвета)
  const kindOf = g => (g * 7 + 3) % 4;
  const swapT = mode === 'swap' ? smooth((u - 0.4) / 1.0) : (p.after_swap ? 1 : 0);
  rrect(x0 - 10, y0 - 10, s + 20, s + 20, 10, col.panel);
  const rhoIdx = p.rho_index || 0; let rhoNow = M.rho_w[rhoIdx];
  if (p.rho_from !== undefined) { const t = smooth((u - (p.rho_at || 1.4)) / 0.5); rhoNow = M.rho_w[p.rho_from] * (1 - t) + M.rho_w[p.rho_index] * t; }
  const ramp = p.ramp ? smooth(u / p.ramp) : 1;
  const hatch = p.exception;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const g = M.grain[y][x], px = x0 + x * cs, py = y0 + y * cs;
    if (g > 0) {
      const k = kindOf(g); const base = p.only_quartz ? 0 : k;
      ctx.fillStyle = p.mixed ? kinds[k] : mix(kinds[0], kinds[3], swapT); ctx.fillRect(px, py, cs + 0.6, cs + 0.6);
    } else {
      let fill = '#16222d';
      if (mode === 'saturated') fill = '#2b79b5';
      else if (mode === 'exception') { const dry = ((x * 31 + y * 17) % 97 < 0) || (Math.hypot(x - 22, y - 18) < 13) || (Math.hypot(x - 46, y - 46) < 9); fill = dry ? '#95A5A6' : '#2b79b5'; }
      else if (mode === 'current' || mode === 'swap') {
        if (!M.connected[y][x]) fill = '#16222d';
        else {
          const jj = M.j[y][x] * (M.rho_w[0] / rhoNow);
          const wave = 0.65 + 0.35 * Math.sin(2 * Math.PI * (M.phi[y][x] * 3 - u * 0.9));
          const a = clamp(Math.pow(jj * 1.8, 0.7), 0, 1) * wave * ramp;
          fill = mix('#16345a', '#7fd0ff', clamp(0.12 + a * 0.95, 0, 1));
        }
      } else fill = '#1d3b57';
      ctx.fillStyle = fill; ctx.fillRect(px, py, cs + 0.6, cs + 0.6);
      if (mode === 'exception' && fill === '#95A5A6') { ctx.strokeStyle = '#6c7a7b'; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(px, py + cs); ctx.lineTo(px + cs, py); ctx.stroke(); }
    }
  }
  // электроды
  ctx.fillStyle = '#E74C3C'; ctx.fillRect(x0 - 26, y0, 16, s); ctx.fillStyle = '#3498DB'; ctx.fillRect(x0 + s + 10, y0, 16, s);
  ctx.font = `bold 40px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
  ctx.fillStyle = '#E74C3C'; ctx.fillText('+', x0 - 18, y0 - 18); ctx.fillStyle = '#3498DB'; ctx.fillText('−', x0 + s + 18, y0 - 18);
  // счётчик R
  if (p.show_R) {
    const k = M.rho_w.findIndex(r => Math.abs(r - rhoNow) < 1e-9); const Rrel = k >= 0 ? M.R_rel[k] : rhoNow * (M.R_rel[0] / M.rho_w[0]);
    const bx = stage.x + stage.w - 330, by = y0 + s + 28;
    rrect(bx - 10, by - 6, 340, 118, 14, '#1A2129', col.measurement, 3);
    ctx.textAlign = 'left'; ctx.fillStyle = col.text; ctx.font = `bold 40px ${FONT}`; ctx.fillText(`ρв = ${fmt(rhoNow, 1)} усл.`, bx + 10, by + 44);
    ctx.fillStyle = col.measurement; ctx.fillText(`R = ${fmt(Rrel, 2)} отн.`, bx + 10, by + 98);
  }
  if (mode === 'swap') {
    const bx = stage.x + 10, by = y0 + s + 28;
    ctx.textAlign = 'left'; ctx.font = `bold 40px ${FONT}`; ctx.fillStyle = mix(kinds[0], kinds[3], swapT);
    ctx.fillText(swapT < 0.5 ? '■ кварц' : '■ кальцит', bx, by + 44);
  }
  if (p.options) { // вопрос-предсказание: варианты без подсветки
    const oy = y0 + s + 30, ow = (stage.w - 40) / 3;
    p.options.forEach((t, i) => { rrect(stage.x + i * (ow + 20), oy, ow, 118, 14, '#1A2129', '#4a5560', 3); textBlock(t, stage.x + i * (ow + 20) + 12, oy + 16, ow - 24, 38, col.text, { align: 'center' }); });
  }
  if (p.timer) { // обратный отсчёт паузы (только таймер, ответа нет)
    const r = 70, cx = stage.x + stage.w - 100, cy = y0 + 70, f = clamp(1 - u / dur, 0, 1);
    ctx.lineWidth = 12; ctx.strokeStyle = '#2d3844'; ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.stroke();
    ctx.strokeStyle = col.measurement; ctx.beginPath(); ctx.arc(cx, cy, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * f); ctx.stroke();
    rrect(x0 + s / 2 - 220, y0 + s / 2 - 50, 440, 100, 18, 'rgba(15,20,25,0.88)', col.measurement, 4);
    ctx.fillStyle = col.measurement; ctx.font = `bold 56px ${FONT}`; ctx.textAlign = 'center'; ctx.fillText('Ваш ответ?', x0 + s / 2, y0 + s / 2 + 20);
  }
}

// ---------- прочие виды ----------
const VIEWS = {
  rock_grid: (st, p, u, d) => drawGrid(st, p, u, d),
  chips(st, p, u) {
    const items = p.items || [], cols = items.length > 3 ? 2 : 1, rows = Math.ceil(items.length / cols), cw = (st.w - (cols - 1) * 24) / cols, chh = Math.min(150, (st.h - 20) / rows - 20);
    items.forEach((it, i) => { const a = smooth((u - i * 0.25) / 0.4), cx = st.x + (i % cols) * (cw + 24), cy = st.y + Math.floor(i / cols) * (chh + 20);
      ctx.globalAlpha = a; rrect(cx, cy, cw, chh, 16, C().panel, it.color || '#4a5560', 4);
      ctx.fillStyle = it.color || '#888'; ctx.fillRect(cx + 20, cy + chh / 2 - 28, 56, 56);
      ctx.font = `bold 42px ${FONT}`; ctx.fillStyle = C().text; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(it.label, cx + 92, cy + chh / 2); ctx.globalAlpha = 1; });
    if (p.note) textBlock(p.note, st.x, st.y + rows * (chh + 20) + 10, st.w, 40, C().muted, { weight: 'normal' });
  },
  log_bar(st, p, u) {
    const col = C(), x0 = st.x + 30, x1 = st.x + st.w - 30, yb = st.y + st.h * 0.52, e0 = p.axis_min ?? 0, e1 = p.axis_max ?? 16, X = e => x0 + (e - e0) / (e1 - e0) * (x1 - x0);
    ctx.strokeStyle = col.muted; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(x0, yb); ctx.lineTo(x1, yb); ctx.stroke();
    ctx.fillStyle = col.muted; ctx.font = `34px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'top';
    for (let e = e0; e <= e1; e += (p.tick || 4)) { ctx.beginPath(); ctx.moveTo(X(e), yb - 10); ctx.lineTo(X(e), yb + 10); ctx.stroke(); ctx.fillText('10' + sup(e), X(e), yb + 18); }
    ctx.textAlign = 'right'; ctx.fillText(p.unit || 'Ом·м', x1, yb + 62);
    const g = p.reveal === false ? 1 : smooth(u / 1.2), a = X(p.min_exp), b = a + (X(p.max_exp) - a) * g;
    rrect(a, yb - 70, Math.max(0, b - a), 60, 10, p.color || col.grain_quartz);
    if (g > 0.95) { textBlock(p.label || '', st.x, yb - 170, st.w, 44, col.text, { weight: 'bold', align: 'center' }); }
    if (p.tag && u > (p.tag_at || 0)) { rrect(a, yb + 110, X(p.max_exp) - a, 80, 14, '#1A2129', col.measurement); textBlock(p.tag, a + 12, yb + 124, X(p.max_exp) - a - 24, 44, col.measurement, { align: 'center' }); }
    if (p.gloss) { const a2 = smooth(u / 0.4); ctx.globalAlpha = a2; textBlock(p.gloss, st.x, st.y + st.h * 0.02, st.w, 40, col.muted, { weight: 'normal' }); ctx.globalAlpha = 1; }
  },
  compare(st, p, u) {
    const col = C(), bw = (st.w - 150) / 2, by = st.y + 40, bh = 330;
    const a = smooth(u / 0.5), b = smooth((u - 0.5) / 0.5);
    ctx.globalAlpha = a; rrect(st.x, by, bw, bh, 18, col.panel, p.left_color || col.measurement, 4);
    textBlock(p.left_title, st.x + 20, by + 20, bw - 40, 38, col.muted, { weight: 'normal' }); textBlock(p.left, st.x + 20, by + 90, bw - 40, 54, col.text); ctx.globalAlpha = 1;
    ctx.globalAlpha = b; arrow(st.x + bw + 20, by + bh / 2, st.x + bw + 130, by + bh / 2, col.text, 10, 36);
    rrect(st.x + bw + 150, by, bw, bh, 18, col.panel, p.right_color || col.provenance['схема'], 4);
    textBlock(p.right_title, st.x + bw + 170, by + 20, bw - 40, 38, col.muted, { weight: 'normal' }); textBlock(p.right, st.x + bw + 170, by + 90, bw - 40, 54, col.text); ctx.globalAlpha = 1;
  },
  xy_plot(st, p, u) {
    const col = C(), ax = st.x + 110, ay = st.y + st.h - 90, aw = st.w - 160, ah = st.h - 160, xs = p.xmax ?? 3.5, ys = p.ymax ?? 3.5;
    ctx.strokeStyle = col.muted; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(ax, ay - ah); ctx.lineTo(ax, ay); ctx.lineTo(ax + aw, ay); ctx.stroke();
    ctx.fillStyle = col.muted; ctx.font = `38px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'top'; ctx.fillText(p.xlabel || '', ax + aw / 2, ay + 24);
    ctx.save(); ctx.translate(ax - 70, ay - ah / 2); ctx.rotate(-Math.PI / 2); ctx.fillText(p.ylabel || '', 0, 0); ctx.restore();
    const pts = (p.points === 'model_R' ? MODEL.rho_w.map((r, i) => [r, MODEL.R_rel[i]]) : p.points) || [];
    const X = x => ax + x / xs * aw, Y = y => ay - y / ys * ah;
    const k = Math.floor(u / 0.5);
    ctx.strokeStyle = col.measurement; ctx.lineWidth = 6; ctx.beginPath(); pts.forEach((q, i) => { if (i <= k) { i ? ctx.lineTo(X(q[0]), Y(q[1])) : ctx.moveTo(X(q[0]), Y(q[1])); } }); ctx.stroke();
    pts.forEach((q, i) => { if (i <= k) { ctx.fillStyle = col.measurement; ctx.beginPath(); ctx.arc(X(q[0]), Y(q[1]), 16, 0, 7); ctx.fill(); ctx.fillStyle = col.text; ctx.font = `bold 38px ${FONT}`; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.fillText(`${fmt(q[0], 0)}; ${fmt(q[1], 2)}`, X(q[0]) + 24, Y(q[1]) - 18); } });
    if (p.note) textBlock(p.note, st.x, st.y - 10, st.w, 40, col.muted, { weight: 'normal' });
  },
  ion_surface(st, p, u) {
    const col = C(), wy = st.y + st.h * 0.58, wh = st.h * 0.26;
    ctx.fillStyle = '#3b4650'; ctx.fillRect(st.x, wy, st.w, wh); ctx.strokeStyle = '#59656f'; ctx.lineWidth = 2;
    for (let x = st.x - wh; x < st.x + st.w; x += 36) { ctx.beginPath(); ctx.moveTo(x, wy + wh); ctx.lineTo(x + wh, wy); ctx.stroke(); }
    textBlock(p.solid_label || 'твёрдая фаза', st.x + 20, wy + wh / 2 - 26, st.w - 40, 48, col.text, { align: 'center' });
    ctx.fillStyle = '#1d3b57'; ctx.fillRect(st.x, st.y, st.w, wy - st.y);
    textBlock(p.water_label || 'поровая вода', st.x + 20, st.y + 14, st.w - 40, 44, '#9fd4ff', { align: 'center', weight: 'normal' });
    const N = 46; for (let i = 0; i < N; i++) { const rnd = k => { const s = Math.sin(i * 12.9898 + k * 78.233) * 43758.5453; return s - Math.floor(s); }, rx = rnd(1), ry = rnd(2), dens = Math.pow(ry, 3.2), y = wy - 28 - dens * (wy - st.y - 130), x = st.x + 30 + rx * (st.w - 60), a = smooth((u - i * 0.03) / 0.5);
      ctx.globalAlpha = a; ctx.fillStyle = i % 3 === 0 ? '#E8C872' : '#7FB3D5'; ctx.beginPath(); ctx.arc(x, y, 14, 0, 7); ctx.fill(); ctx.fillStyle = '#0F1419'; ctx.font = `bold 22px ${FONT}`; ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(i % 3 === 0 ? '−' : '+', x, y + 1); ctx.globalAlpha = 1; }
    if (p.note) textBlock(p.note, st.x, wy + wh + 14, st.w, 38, col.muted, { weight: 'normal' });
  },
  conclusion(st, p, u) {
    const col = C(), a = smooth(u / 0.5), b = smooth((u - 0.4) / 0.5), cy = st.y + 20;
    ctx.globalAlpha = a; rrect(st.x, cy, st.w, 110, 18, col.panel, col.measurement, 4); textBlock(p.from, st.x + 20, cy + 26, st.w - 40, 52, col.text, { align: 'center' }); ctx.globalAlpha = 1;
    ctx.globalAlpha = b; arrow(st.x + st.w / 2, cy + 120, st.x + st.w / 2, cy + 190, col.text, 10, 36);
    rrect(st.x, cy + 200, st.w, 110, 18, col.panel, col.provenance['схема'], 4); textBlock(p.to, st.x + 20, cy + 226, st.w - 40, 52, col.text, { align: 'center' });
    if (p.not) textBlock('не ' + p.not, st.x, cy + 330, st.w, 52, '#e57373', { align: 'center' });
    ctx.globalAlpha = 1;
    if (p.condition) { const c = smooth((u - 0.2) / 0.4); ctx.globalAlpha = c; rrect(st.x, cy + 410, st.w, 190, 18, '#1A2129', col.measurement, 4); const h = textBlock(p.condition, st.x + 20, cy + 428, st.w - 40, 46, col.measurement, { align: 'center' }); if (p.condition_note) textBlock(p.condition_note, st.x + 20, cy + 428 + h + 10, st.w - 40, 36, col.muted, { align: 'center', weight: 'normal' }); ctx.globalAlpha = 1; }
  },
  title_card(st, p, u) {
    const a = smooth(u / 0.5); ctx.globalAlpha = a; const h = textBlock(p.text, st.x + 20, st.y + st.h * 0.3, st.w - 40, p.px || 72, C().text, { align: 'center' });
    if (p.sub) textBlock(p.sub, st.x + 20, st.y + st.h * 0.3 + h + 30, st.w - 40, 44, C().muted, { align: 'center', weight: 'normal' }); ctx.globalAlpha = 1;
  }
};
function sup(e) { const m = { '0': '⁰', '1': '¹', '2': '²', '3': '³', '4': '⁴', '5': '⁵', '6': '⁶', '7': '⁷', '8': '⁸', '9': '⁹' }; return String(e).split('').map(c => m[c] || c).join(''); }

// ---------- кадр ----------
function drawAt(t) {
  if (!L) layout();
  const col = C(); ctx.fillStyle = col.background; ctx.fillRect(0, 0, W, H);
  const f = TL.frames.find(f => t >= f.t0 && t < f.t1) || TL.frames[TL.frames.length - 1], u = t - f.t0, dur = f.t1 - f.t0;
  // метка происхождения
  const pc = col.provenance[f.label] || '#888'; ctx.font = `bold ${L.fChip}px ${FONT}`; const lw = ctx.measureText(f.label.toUpperCase()).width + 40;
  rrect(L.x0, L.chip.y, lw, L.chip.h, 12, pc); ctx.fillStyle = '#fff'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(f.label.toUpperCase(), L.x0 + 20, L.chip.y + L.chip.h / 2 + 2);
  ctx.font = `${L.fChip}px ${FONT}`; ctx.fillStyle = col.muted; ctx.fillText('кадр ' + f.class, L.x0 + lw + 20, L.chip.y + L.chip.h / 2 + 2);
  // подпись кадра (≤8 слов)
  const fade = smooth(u / 0.25); ctx.globalAlpha = fade;
  textBlock(f.caption, L.x0, L.cap.y, L.x1 - L.x0, L.fCap, col.text);
  if (f.caption_note) textBlock(f.caption_note, L.x0, L.cap.y + L.cap.h - 10, L.x1 - L.x0, 36, col.muted, { weight: 'normal' });
  // сцена
  const v = VIEWS[f.view_type || f.view]; if (v) v(L ? { x: L.stage.x, y: L.stage.y, w: L.stage.w, h: L.stage.h } : null, f.params || {}, u, dur); else { textBlock('нет шаблона: ' + f.view, L.stage.x, L.stage.y, L.stage.w, 48, '#e57373'); }
  ctx.globalAlpha = 1;
  // плашки честности
  let py = L.plates.y; (f.plates || []).forEach(p => { const h = textBlock(p, L.x0, py, L.x1 - L.x0, L.fPlate, col.muted, { weight: 'normal' }); py += h + 6; });
  // субтитры (слова с подсветкой текущего)
  const ch = TL.subs.find(c => t >= c.t0 - 0.05 && t < c.t1 + 0.12);
  if (ch) { ctx.font = `bold ${L.fSub}px ${FONT}`; const maxW = L.x1 - L.x0; const lines = []; let cur = []; let curW = 0; const sp = ctx.measureText(' ').width;
    ch.words.forEach(w => { const ww = ctx.measureText(w.t).width; if (curW + ww > maxW && cur.length) { lines.push(cur); cur = []; curW = 0; } cur.push({ ...w, ww }); curW += ww + sp; }); lines.push(cur);
    const lh = L.fSub * 1.22, total = lines.length * lh, top = L.subs.y + L.subs.h - total; rrect(L.x0 - 14, top - 12, maxW + 28, total + 20, 14, 'rgba(15,20,25,0.82)');
    lines.forEach((ln, i) => { const lwid = ln.reduce((s, w) => s + w.ww + sp, -sp); let x = L.x0 + (maxW - lwid) / 2; ln.forEach(w => { ctx.fillStyle = (t >= w.t0 && t < w.t1 + 0.05) ? col.measurement : col.text; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(w.t, x, top + i * lh); x += w.ww + sp; }); }); }
}
window.drawAt = drawAt; window.initScene = () => { layout(); };
