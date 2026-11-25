#!/usr/bin/env python3
"""Курс из учебного слоя: python3 -I tools/build_course.py <chapter> --prefix lat.s12. --out out/<dir>
Читает build/<chapter>/{nodes,units}.json и tools/course_config/<chapter>.json, пишет один index.html
(данные, стили и скрипт вшиты; без fetch и внешних запросов). Правила «проверено» те же, что в tools/check_nodes.py."""
import argparse, html, json, math, re, sys, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "tools/course_template"
esc = lambda s: html.escape(str(s), quote=True)
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[«»\"'`]", "", s)).strip().lower()  # как в check_nodes.py
nrm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
NUM = re.compile(r"\d+(?:,\d+)?")
ABBR = ("рис", "табл", "стр", "см", "т", "п")


def sentences(t):
    """Делит на предложения, не режет «рис. 51», «табл. 12»."""
    out, cur = [], ""
    for part in re.split(r"(?<=[.!?])\s+(?=[А-ЯA-Z\[«])", t.strip()):
        if cur and re.search(r"(?:^|\W)(?:%s)\.$" % "|".join(ABBR), cur):
            cur += " " + part
        else:
            if cur: out.append(cur)
            cur = part
    if cur: out.append(cur)
    return out


def verify(c, units):
    """Статус claim: ok / noquote / notfound / model. Те же проверки, что check_nodes.py (цитата и числа на странице, не figure_desc)."""
    if c["author"] != "автор":
        return "model", None
    pool = [u for u in units if u["page"] == c["page"] and u["type"] != "figure_desc"]
    q = norm(c.get("quote", ""))
    if not q: return "noquote", None
    hit = next((u for u in pool if q in norm(u["text"])), None)
    if not hit: return "notfound", None
    page_txt = re.sub(r"(?<=\d) (?=\d)", "", norm(" ".join(u["text"] for u in pool)))
    for x in NUM.findall(c["text"]):
        if x not in page_txt and x not in (c.get("ocr_note") or ""): return "numbers", hit
    return "ok", hit


def ctx_parts(hit, quote):
    t = hit["text"]
    words = [re.escape(w) for w in re.sub(r"[«»\"'`]", "", quote).split()]
    m = re.search(r"[«»\"'`]?\s*".join(words), t, re.I) if words else None
    if len(t) > 900 and m:
        a = max(0, m.start() - 350); t2 = t[a:m.end() + 350]; off = a
        m = re.search(r"[«»\"'`]?\s*".join(words), t2, re.I); t = ("…" if a else "") + t2; shift = 1 if a else 0
    else: shift = 0
    if m: return [t[:m.start() + shift], t[m.start() + shift:m.end() + shift], t[m.end() + shift:]]
    return [t[:900], "", ""]

GREEK = {"rho": "ρ", "Delta": "Δ", "delta": "δ", "phi": "φ", "varphi": "φ", "Lambda": "Λ", "lambda": "λ", "Sigma": "Σ", "sigma": "σ", "Pi": "Π", "pi": "π",
         "mu": "μ", "alpha": "α", "beta": "β", "gamma": "γ", "eta": "η", "tau": "τ", "nu": "ν", "epsilon": "ε", "varepsilon": "ε", "theta": "θ", "kappa": "κ",
         "xi": "ξ", "omega": "ω", "Omega": "Ω", "psi": "ψ", "chi": "χ", "zeta": "ζ", "cdot": "·", "times": "×", "div": "÷", "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥",
         "approx": "≈", "sim": "∼", "ne": "≠", "pm": "±", "infty": "∞", "to": "→", "rightarrow": "→", "Rightarrow": "⇒", "partial": "∂", "circ": "°", "prime": "′",
         "ldots": "…", "quad": " ", "qquad": " ", "left": "", "right": ""}
SUP = {"0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻", "+": "⁺"}


def tex2txt(t):
    """Читаемая запись формулы из TeX слоя (индексы как в тексте слоя: ρ_вп). Если остаются неизвестные команды, вернёт None."""
    t = t.strip()
    t = re.sub(r"^\$\$|\$\$$|^\\\(|\\\)$|^\\\[|\\\]$", "", t).strip()
    t = re.sub(r"\$\$|\\\(|\\\)", " ", t)
    tag = re.search(r"\\tag\{([^}]*)\}", t); t = re.sub(r"\\tag\{[^}]*\}", "", t)
    t = re.sub(r"\\begin\{[^}]*\}(\{[^}]*\})?|\\end\{[^}]*\}", "", t).replace("\\\\", "; ").replace("&", " ")
    for _ in range(6):
        t = re.sub(r"\\(?:text|mathrm|mathbf|mathit|operatorname)\{([^{}]*)\}", r"\1", t)
        t = re.sub(r"\\frac\{([^{}]*)\}\{([^{}]*)\}", r"(\1)/(\2)", t)
    t = re.sub(r"\\([A-Za-z]+)", lambda m: GREEK.get(m.group(1), m.group(0)), t)
    t = re.sub(r"\\[,;:!]", " ", t)
    t = re.sub(r"\^\{([0-9+\-]+)\}", lambda m: "".join(SUP[c] for c in m.group(1)), t)
    t = re.sub(r"\^([0-9])", lambda m: SUP[m.group(1)], t)
    t = re.sub(r"\^\{([^{}]*)\}", r"^(\1)", t)
    t = re.sub(r"_\{([^{}]*)\}", r"_\1", t)
    t = t.replace("{}", "")
    t = re.sub(r"\^\{′\}", "′", t)
    t = re.sub(r"\s+", " ", t).strip()
    if tag: t += f"  ({tag.group(1)})"
    return None if re.search(r"\\[A-Za-z]|[{}]", t) else t


def tex_inline(t):
    r"""Формулы внутри текста/ячеек: \( ... \) и $...$ -> читаемая запись; если не получилось, оставляет как есть."""
    return re.sub(r"\\\((.+?)\\\)|\$(.+?)\$", lambda m: tex2txt(m.group(1) or m.group(2)) or m.group(0), t)


SERVICE_SENT = re.compile(r"FORMAT|figure_desc|ocr_note|\bв ролик|\bв ключе|не использовать в (?:роликах|заданиях)|ответы не придум|для ментора|вопрос ментору|узел lat\.", re.I)


STEPNUM = {}  # id узла -> номер шага (заполняется в Build.render)
SHORTNUM = {}  # две цифры номера узла -> номер шага


def vis(text):
    """Текст для читателя: без предложений-служебных пометок слоя (в панели источника остаётся оригинал); ссылки «узел lat.…» -> «шаг N»."""
    text = re.sub(r"\s*\((?:figure_desc|FORMAT[^)]*)\)", "", text)
    text = re.sub(r"\bузл(?:ы|а|ов|е|у)?\s+(\d{2}(?:(?:,\s*|\s+и\s+)\d{2})*)", lambda m: ("шаги " if len(re.findall(r"\d{2}", m.group(1))) > 1 else "шаг ") + ", ".join(str(SHORTNUM.get(k, "?")) for k in re.findall(r"\d{2}", m.group(1))), text)
    text = re.sub(r"узел (lat\.[\w.\-]+)", lambda m: f"шаг {STEPNUM[m.group(1)]}" if m.group(1) in STEPNUM else "соответствующий шаг", text)
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    keep = [x for x in parts if not SERVICE_SENT.search(x)]
    return " ".join(keep) if keep and len(keep) < len(parts) else text


SERVICE = [(re.compile(r"\s*Не подтверждено книгой,? не использовать в заданиях и роликах\.?", re.I), " (в книге не подтверждено)")]


def clean_note(t):
    """Служебные формулировки слоя для аудитории: без «не использовать в заданиях и роликах»."""
    for rx, rep in SERVICE: t = rx.sub(rep, t)
    return vis(t)


GLOSS_NOISE = re.compile(r"clean\.md|draft|куратор|\bOCR\b|\bocr|вопрос ментору|ментор|черновик", re.I)


def gloss_clean(t):
    parts = re.split(r"(?<=[.;!?])\s+", t.strip())
    keep = [x for x in parts if not GLOSS_NOISE.search(x)]
    return " ".join(keep) if keep else t


def glossary_rows(path, maxpage, book="Лат"):
    """Строки глоссария доменного пакета: термины данной книги, определённые на страницах не позже maxpage (PDF)."""
    rows = []
    if not Path(path).exists(): return rows
    for line in Path(path).read_text().splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(c) < 5 or c[0].startswith(("термин", "---", ":--")) or set(c[0]) <= set("-: "): continue
        pg = [int(x) for m in re.finditer(book + r"\s*([0-9][0-9,\s;–\-]*)", c[3]) for x in re.findall(r"\d+", m.group(1))]
        if pg and min(pg) <= maxpage: rows.append((c[0], gloss_clean(c[2]), c[3], min(pg)))
    return sorted(rows, key=lambda r: (r[3], r[0].lower()))


class Build:
    def __init__(s, nodes, units, cfg, chapter):
        s.nodes, s.units, s.cfg, s.chapter = nodes, units, cfg, chapter
        s.U = {u["id"]: u for u in units}
        s.EV, s.warn, s.dcalc = {}, [], None
        s.nid = {n["id"].split(".")[-1][:2]: n["id"] for n in nodes}  # короткий ключ «01» -> полный id; суффикс-число из слоя
        s.byid = {n["id"]: n for n in nodes}

    # ---- ключи утверждений
    def key(s, ref, node=None):
        if "#" in ref:
            a, b = ref.split("#"); return f"{s.nid.get(a, a)}#{b}"
        return f"{node}#{ref}"

    def claim(s, key):
        n, c = key.split("#"); return next(x for x in s.byid[n]["claims"] if x["id"] == c)

    def register(s):
        for n in s.nodes:
            pages = sorted({c["page"] for c in n["claims"]})
            for c in n["claims"]:
                st, hit = verify(c, s.units)
                e = {"a": c["author"], "k": c["kind"], "p": c["page"], "q": c.get("quote", ""), "st": st, "t": c["text"],
                     "o": c.get("ocr_note", ""), "n": n["id"], "c": c["id"]}
                if hit: e["x"] = ctx_parts(hit, c["quote"])
                s.EV[f"{n['id']}#{c['id']}"] = e
            if not s.nodes: continue
            s.pages = getattr(s, "pages", {}); s.pages[n["id"]] = pages

    def model_ev(s, n, field, author="модель", note=""):
        k = f"{n['id']}@{field}"
        s.EV[k] = {"a": author, "k": "поле модели", "p": 0, "st": "model", "n": n["id"], "pp": s.pages[n["id"]], "o": note,
                   "basis": [f"{n['id']}#{c['id']}" for c in n["claims"]]}
        return k

    def cl(s, key, text):
        e = s.EV[key]; cls = {"автор": "ca", "модель": "cm", "гипотеза": "ch"}[e["a"]]
        ok = '<sup class="vk" title="проверено: цитата найдена на странице">✓</sup>' if e["st"] == "ok" else ""
        return f'<span class="cl {cls}" tabindex="0" role="button" data-k="{esc(key)}" aria-label="{esc(e["a"])}: показать источник">{esc(vis(text))}{ok}</span>'

    def model_sents(s, n, field, text, author="модель", note=""):
        out = []
        ss = sentences(text); ks = [x for x in ss if not SERVICE_SENT.search(x)]
        for i, sent in enumerate(ks if ks and len(ks) < len(ss) else ss):
            au = "гипотеза" if re.search(r"гипотез", sent, re.I) else author
            k = f"{n['id']}@{field}.{i}"
            s.EV[k] = {"a": au, "k": "поле модели", "p": 0, "st": "model", "n": n["id"], "pp": s.pages[n["id"]], "o": note,
                       "basis": [f"{n['id']}#{c['id']}" for c in n["claims"]], "field": field}
            out.append(s.cl(k, sent))
        return " ".join(out)

    # ---- иллюстрации
    def fig(s, n, short):
        sp = s.cfg["illustrations"].get(n["id"].split(".")[-1][:2], {"kind": "flow"})
        kind = sp["kind"]; cap = ""; body = ""; alt = ""
        if kind == "table_bars":
            tb = next(s.U[u] for u in n["unit_ids"] if s.U[u]["type"] == "table")
            rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in tb["text"].splitlines()[2:]]
            data = []
            for r in rows:
                v = [float(x.replace(",", ".")) for x in NUM.findall(r[1])] if len(r) > 1 else []
                if v: data.append((r[0], min(v), max(v)))
            lo, hi = math.log(0.4), math.log(60); W, H = 360, 22 * len(data) + 40
            X = lambda v: 150 + (math.log(v) - lo) / (hi - lo) * 200
            g = "".join(f'<text x="146" y="{22+i*22}" text-anchor="end" class="t">{esc(textwrap.shorten(nm, 24, placeholder="…"))}</text>'
                        f'<rect x="{X(a):.1f}" y="{12+i*22}" width="{max(X(b)-X(a),3):.1f}" height="12" class="bar"/>' for i, (nm, a, b) in enumerate(data))
            ticks = "".join(f'<line x1="{X(v):.1f}" x2="{X(v):.1f}" y1="6" y2="{H-24}" class="grid"/><text x="{X(v):.1f}" y="{H-10}" text-anchor="middle" class="t">{v}</text>' for v in (0.5, 1, 5, 10, 50))
            body = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Диапазоны q по породам из таблицы 12">{ticks}{g}</svg>'
            cap = f"Из данных: диапазоны q (пг-экв Ra/г) по таблице 12, стр. {tb['page']} PDF; шкала логарифмическая."
            alt = "Горизонтальные столбики диапазонов q для пород таблицы 12"
        elif kind == "linmodel":
            body = f'<div class="wid" data-widget="linmodel" data-dj="{1 if sp.get("show_dj") else 0}"></div>'
            cap = "Модель состояния: I = C·q + I_ф с условными числами (не из книги); двигайте ползунки." + (" ΔJ по формуле (40) не меняется от C и I_ф." if sp.get("show_dj") else "")
        elif kind in ("redraw_eta", "redraw_dj"):
            body = s.redraw(kind, n, sp); cap = f"перерисовано по рис. {sp['fig']}, стр. {sp['page']} PDF; схематично, значения кривых не воспроизведены."
        elif kind == "redraw_axes":
            c = s.claim(sp["claim"].replace("#", "#") if "#" in sp["claim"] else f"{n['id']}#{sp['claim']}"); g = ""; k = len(sp["panels"]); W = 360
            for i, pn in enumerate(sp["panels"]):
                for need in (pn["lo"], pn["hi"]):
                    if need not in c["text"]: s.warn.append(f"{n['id']}: {need} нет в {sp['claim']}")
                x = 40 + i * (W - 60) / k + (W - 60) / k / 2; down = pn["dir"] == "down"; ya, yb = 40, 170
                top, bot = (pn["lo"], pn["hi"]) if down else (pn["hi"], pn["lo"])
                ah = f'M{x} {ya} V{yb} m-5 -8 l5 8 l5 -8' if down else f'M{x} {yb} V{ya} m-5 8 l5 -8 l5 8'
                g += (f'<path d="{ah}" class="ax" fill="none"/><text x="{x}" y="{ya-10}" text-anchor="middle" class="t">{esc(top)}</text>'
                      f'<text x="{x}" y="{yb+22}" text-anchor="middle" class="t">{esc(bot)}</text><text x="{x}" y="{yb+40}" text-anchor="middle" class="t sm">{esc(pn["label"])}</text>'
                      f'<text x="{x+8}" y="105" class="t sm">{"растёт вниз" if down else "растёт вверх"}</text>')
            body = f'<svg viewBox="0 0 {W} 230" role="img" aria-label="Шкалы рисунка {esc(sp["fig"])}: {esc("; ".join(p["label"] + " от " + p["lo"] + " до " + p["hi"] + ", растёт " + ("вниз" if p["dir"] == "down" else "вверх") for p in sp["panels"]))}">{g}</svg>'
            cap = f"перерисовано по рис. {sp['fig']}, стр. {sp['page']} PDF: только оси, диапазоны и направление шкал из утверждения {sp['claim'].split('.')[-1]}; кривые не воспроизведены."
        elif kind == "numbers":
            c = s.claim(f"{n['id']}#{sp['claim']}"); bars = []
            for lab, v in sp["bars"]:
                if v not in c["text"]: s.warn.append(f"{n['id']}: число {v} нет в {sp['claim']}")
                bars.append((lab, float(v.replace(",", "."))))
            mx = max(b[1] for b in bars)
            g = "".join(f'<text x="100" y="{24+i*30}" text-anchor="end" class="t">{esc(l)}</text><rect x="106" y="{10+i*30}" width="{v/mx*200:.1f}" height="18" class="bar"/>'
                        f'<text x="{110+v/mx*200:.1f}" y="{24+i*30}" class="t">{v:g}</text>' for i, (l, v) in enumerate(bars))
            body = f'<svg viewBox="0 0 360 {30*len(bars)+10}" role="img" aria-label="Числа расчёта: {esc(", ".join(f"{l} {v:g}" for l, v in bars))} {esc(sp["unit"])}">{g}</svg>'
            cap = f"Из данных: числа утверждения {sp['claim']}, стр. {c['page']} PDF ({sp['unit']})."
        elif kind == "scale":
            c = s.claim(f"{n['id']}#{sp['claim']}")
            t = "".join(f'<line x1="{30+i*30}" x2="{30+i*30}" y1="40" y2="{58 if i in (0,10) else 50}" class="ax"/><text x="{30+i*30}" y="74" text-anchor="middle" class="t">{i/10:.1f}'.replace(".", ",") + "</text>" for i in range(11))
            body = (f'<svg viewBox="0 0 360 120" role="img" aria-label="Шкала ΔJ от 0 до 1 из десяти равных частей между линиями I_min и I_гл">'
                    f'<line x1="30" x2="330" y1="40" y2="40" class="ax"/>{t}<text x="30" y="26" text-anchor="middle" class="t">I_min</text><text x="330" y="26" text-anchor="middle" class="t">I_гл</text>'
                    f'<text x="180" y="100" text-anchor="middle" class="t">ΔJ: 0 на I_min, 1 на I_гл; C_гл: 0 и 90 %</text></svg>')
            cap = f"Из данных: шкала ΔJ по утверждению {sp['claim']}, стр. {c['page']} PDF (10 равных частей)."
        else:  # flow: цепочка утверждений шага
            boxes, y = [], 8
            for i, c in enumerate(n["claims"]):
                vt = vis(c["text"]); w = " ".join(vt.split()[:11]) + ("…" if len(vt.split()) > 11 else "")
                ls = textwrap.wrap(w, 40); h = 14 * len(ls) + 12
                boxes.append(f'<rect x="8" y="{y}" width="344" height="{h}" rx="6" class="box"/>' + "".join(f'<text x="16" y="{y+18+14*j}" class="t">{esc(l)}</text>' for j, l in enumerate(ls))
                             + f'<text x="346" y="{y+h-4}" text-anchor="end" class="t sm">стр. {c["page"]}</text>')
                if i < len(n["claims"]) - 1: boxes.append(f'<path d="M180 {y+h} v10 m-4 -5 l4 5 l4 -5" class="ax" fill="none"/>')
                y += h + 12
            body = f'<svg viewBox="0 0 360 {y}" role="img" aria-label="Цепочка утверждений шага «{esc(short)}»">{"".join(boxes)}</svg>'
            cap = "Схема из слоя: утверждения шага по порядку (начало каждого)."
        alt = alt or cap
        return f'<figure class="fig">{body}<figcaption>{esc(cap)}</figcaption></figure>'

    def redraw(s, kind, n, sp):
        c = s.claim(f"{n['id']}#{sp['claim']}")
        ax = '<line x1="40" x2="40" y1="10" y2="190" class="ax"/><line x1="40" x2="340" y1="190" y2="190" class="ax"/>'
        if kind == "redraw_eta":
            Y = lambda v: 190 - (v - 0.2) / 1.4 * 180; X = lambda d: 40 + d / 50 * 300
            curves = ""
            for a in (.12, .22, .32, .42, .52, .6):
                curves += f'<path class="cv" d="M{X(0)} {Y(1)} ' + " ".join(f"L{X(d):.1f} {Y(1+a*(1-math.exp(-d/20))*1.0):.1f}" for d in range(2, 51, 2)) + '"/>'
            for a in (.08, .18, .3, .45, .6, .75):
                curves += f'<path class="cv" d="M{X(0)} {Y(1)} ' + " ".join(f"L{X(d):.1f} {Y(1-a*(1-math.exp(-d/20))):.1f}" for d in range(2, 51, 2)) + '"/>'
            lab = ('<text x="44" y="16" class="t">η_γ</text><text x="338" y="206" text-anchor="end" class="t">d_c, см (0–50)</text>'
                   f'<text x="250" y="{Y(1.45)}" class="t">вверх: шифр до 200</text><text x="250" y="{Y(0.3)}" class="t">вниз: шифр до 0,2</text><text x="34" y="{Y(1)+4}" text-anchor="end" class="t">1,0</text>')
            for need in ("200", "0,2", "1,0"):
                if need not in c["text"]: s.warn.append(f"{n['id']}: {need} нет в claim")
            return f'<svg viewBox="0 0 360 214" role="img" aria-label="Семейство кривых η_γ от d_c: все выходят из 1,0, с большим шифром идут вверх, с малым вниз">{ax}<line x1="40" x2="340" y1="{Y(1)}" y2="{Y(1)}" class="grid"/>{curves}{lab}</svg>'
        X = lambda v: 40 + v * 300; Y = lambda v: 190 - v * 170
        cv = ""
        for p, nm in ((2.2, "1"), (3.0, "2")):
            cv += f'<path class="cv" d="M{X(0)} {Y(0)} ' + " ".join(f"L{X(t/20):.1f} {Y(1-(1-t/20)**p):.1f}" for t in range(1, 21)) + f'"/><text x="{X(.5)+(8 if nm=="2" else 20)}" y="{Y(1-(0.5)**p)+(-6 if nm=="2" else 14)}" class="t">{nm}</text>'
        lab = ('<text x="44" y="16" class="t">ΔJ</text><text x="190" y="212" text-anchor="middle" class="t">C_гл, % (0–90)</text>'
               f'<line x1="40" x2="340" y1="{Y(1)}" y2="{Y(1)}" class="grid"/><text x="36" y="{Y(1)+4}" text-anchor="end" class="t">1,0</text><text x="{X(1)}" y="203" text-anchor="middle" class="t">90</text><text x="40" y="203" text-anchor="middle" class="t">0</text>')
        return f'<svg viewBox="0 0 360 214" role="img" aria-label="Две возрастающие кривые ΔJ от C_гл из точки 0;0 до 1,0 при 90 %; кривая 2 выше кривой 1">{ax}{cv}{lab}</svg>'

    # ---- таблицы, формулы
    def table_html(s, u):
        rows = [[c.strip() for c in r.strip().strip("|").split("|")] for r in u["text"].splitlines() if not re.match(r"^\|\s*-", r)]
        h = "".join(f"<th scope='col'>{esc(tex_inline(c))}</th>" for c in rows[0])
        b = "".join("<tr>" + "".join(f"<td>{esc(tex_inline(c))}</td>" for c in r) + "</tr>" for r in rows[1:])
        return f'<div class="tw" tabindex="0" role="region" aria-label="Таблица книги, прокрутка"><table><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'

    # ---- страница шага
    def step(s, n, num):
        short = s.cfg["short_titles"].get(n["id"].split(".")[-1][:2], n["title"])
        P = lambda txt: f"<p>{txt}</p>"
        blocks = []  # (id, title, html)
        cs = sorted(n["claims"], key=lambda c: c["kind"] != "вывод")[:3]
        blocks.append(("sut", "Суть", "".join(P(s.cl(f"{n['id']}#{c['id']}", c["text"]) + f" <span class='pg'>[PDF-стр. {c['page']}]</span>") for c in sorted(cs, key=lambda c: c["id"]))))
        L = n.get("layers", {})
        if L.get("mechanism"): blocks.append(("how", "Как это работает", P(s.model_sents(n, "mechanism", L["mechanism"], note="пересказ текста автора"))))
        if n.get("how_now"): blocks.append(("now", "Как делают сейчас", P(s.model_sents(n, "how_now", n["how_now"]))))
        we = n.get("worked_examples") or []
        if we:
            h = ""
            for w in we:
                h += f"<p class='meta'>Пример со стр. {w['page']} PDF</p>"
                if w.get("condition"): h += P("<b>Условие.</b> " + esc(w["condition"]))
                if w.get("steps"): h += "<ol class='steps'>" + "".join(f"<li>{esc(x)}</li>" for x in w["steps"]) + "</ol>"
                if w.get("result"): h += P("<b>Результат.</b> " + esc(w["result"]))
            blocks.append(("ex", "Разбор примера из главы (по шагам)", h))
        if L.get("practice"): blocks.append(("num", "Цифры и условия", P(s.model_sents(n, "practice", L["practice"], note="пересказ текста автора"))))
        if L.get("nuances"): blocks.append(("nu", "Оговорки", P(s.model_sents(n, "nuances", L["nuances"], note="пересказ текста автора"))))
        fh = ""
        for u in n["unit_ids"]:
            U = s.U[u]
            if U["type"] == "formula":
                rd = tex2txt(U["text"]); raw = esc(U["text"].replace("$$", "").strip())
                fh += (f"<p class='fm'><code>{esc(rd)}</code> <span class='meta'>стр. {U['page']} PDF</span></p>" + (f"<details class='meta'><summary>запись TeX</summary><code>{raw}</code></details>" if rd != U["text"].replace("$$", "").strip() else "")) if rd else f"<p class='fm'><code>{raw}</code> <span class='meta'>стр. {U['page']} PDF; запись TeX</span></p>"
        for c in n["claims"]:
            if re.match(r"^(Формул[аы]|Уравнени[ея])\s*\(\d+", c["text"]):
                fh += P(s.cl(f"{n['id']}#{c['id']}", c["text"]) + f" <span class='pg'>[PDF-стр. {c['page']}]</span>")
        if fh: blocks.append(("fm", "Формулы главы", fh + "<p class='meta'>Расшифровка символов и единиц: в утверждениях шага (блок «Источник»).</p>"))
        th = ""
        for u in n["unit_ids"]:
            U = s.U[u]
            if U["type"] == "table":
                th += s.table_html(U) + f"<p class='meta'>Таблица книги целиком, стр. {U['page']} PDF.</p>"
                for c in n["claims"]:
                    if c.get("ocr_note") and u in c["unit_ids"]: th += f"<p class='ocr'><b>Правка OCR:</b> {esc(clean_note(c['ocr_note']))}</p>"
        if th: blocks.append(("tb", "Таблица книги", th))
        te = (n.get("inefficiency_lens") or {}).get("typical_errors")
        if n.get("misconception"): blocks.append(("er", "Частая ошибка", P(s.model_sents(n, "misconception", n["misconception"]))))
        elif te: blocks.append(("er", "Частая ошибка", P(s.model_sents(n, "inefficiency_lens", te, note="поле inefficiency_lens.typical_errors"))))
        di = n.get("data_implication")
        if di and di.get("text"): blocks.append(("di", "Что это значит для данных", P(s.model_sents(n, "data_implication", di["text"], author=di.get("author", "модель")))))
        an = n.get("it_analogy")
        if an and an.get("text"):
            h = P(s.model_sents(n, "it_analogy", an["text"]))
            if an.get("breaks_when"): h += P("<b>Где аналогия ломается.</b> " + s.model_sents(n, "it_analogy_breaks", an["breaks_when"]))
            blocks.append(("an", "Аналогия с границей применимости", h))
        if L.get("deeper"): blocks.append(("dp", "Чего в книге нет", "<ul>" + "".join(f"<li>{s.model_sents(n, f'deeper{i}', d)}</li>" for i, d in enumerate(L["deeper"])) + "</ul>"))
        if n.get("external_prereqs"): blocks.append(("pre", "Опирается на материал вне раздела", "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in n["external_prereqs"]) + "</ul>"))
        if n.get("problems"):
            blocks.append(("pb", "Задачи из книги (ключей в книге нет)", "<ol class='pl'>" + "".join(
                f"<li value='{esc(p.get('number', ''))}'>{esc(p['statement'])} <span class='meta'>стр. {p['page']} PDF" + (f"; OCR: {esc(clean_note(p['ocr_note']))}" if p.get("ocr_note") else "") + (f"; {esc(clean_note(p['figure_note']))}" if p.get("figure_note") else "") + "</span></li>" for p in n["problems"]) + "</ol>"))
        fgh = s.fig(n, short)
        if n.get("figure_note"): fgh += f"<details class='meta'><summary>Примечание к рисунку книги</summary>{esc(clean_note(n['figure_note']))}</details>"
        blocks.append(("fg", "Иллюстрации", fgh))
        allc = "".join(P(s.cl(f"{n['id']}#{c['id']}", c["text"]) + f" <span class='meta'>стр. {c['page']} PDF, {esc(c['author'])}</span>") for c in n["claims"])
        blocks.append(("src", "Источник: все утверждения шага", allc))
        blocks.append(("tk", "Проверьте себя", f'<div class="tasks" data-node="{esc(n["id"])}"></div>'))
        toc = "".join(f'<li><a href="#" data-jump="b-{n["id"]}-{b[0]}">{esc(b[1])}</a></li>' for b in blocks)
        body = "".join(f'<section class="blk" id="b-{n["id"]}-{b[0]}"><h3>{esc(b[1])}</h3>{b[2]}</section>' for b in blocks)
        return short, toc, body

    def render(s):
        s.register(); cfg = s.cfg
        A = s.U[cfg["book"]["author_unit"]]["text"]; T = re.sub(r"(?<=\w)-\s?(?=\w)", "", s.U[cfg["book"]["title_unit"]]["text"].lstrip("# ")).lower().capitalize()
        order = sorted(s.nodes, key=lambda n: n.get("order", {}).get("rank", 0))
        steps = []
        ds = cfg.get("data_step")
        for n in order:
            steps.append(("node", n))
            if ds and n["id"].split(".")[-1][:2] == ds["after"]: steps.append(("data", ds))
        STEPNUM.clear(); STEPNUM.update({n["id"]: i for i, (k, n) in enumerate(steps, 1)})
        SHORTNUM.clear(); SHORTNUM.update({n["id"].split(".")[-1][:2]: i for i, (k, n) in enumerate(steps, 1) if k == "node"})
        part_of = {}
        for p in cfg["parts"]:
            for k in p["nodes"]: part_of[s.nid[k]] = p["title"]
        meta, pages, cards, summary, ntasks = [], "", "", "", {}
        tasks = s.tasks()
        for t in tasks: ntasks[t["node"]] = ntasks.get(t["node"], 0) + 1
        for i, (kind, n) in enumerate(steps, 1):
            if kind == "node":
                short, toc, body = s.step(n, i); sid = n["id"]
                words = len(re.sub(r"<[^>]+>", " ", body).split()); part = part_of.get(sid, "")
                sec = n.get("section", "")
                di = n.get("data_implication", {})
                cards += f'<article class="card" data-id="{esc(sid)}" hidden><h3>{esc(short)}</h3><div class="back" hidden>{"".join("<p>"+s.cl(f"{sid}#{c['id']}", c["text"])+"</p>" for c in sorted(n["claims"], key=lambda c: c["kind"] != "вывод")[:2])}</div></article>'
                summary += (f'<section class="sumstep"><h3>{i}. {esc(short)} <span class="meta">{esc(sid)}</span></h3>'
                            + "".join("<p>" + s.cl(f"{sid}#{c['id']}", c["text"]) + "</p>" for c in sorted(n["claims"], key=lambda c: c["kind"] != "вывод")[:2])
                            + (f'<p><b>Для данных.</b> {s.model_sents(n, "data_implication", di["text"], author=di.get("author", "модель"))}</p>' if di.get("text") else "") + "</section>")
            else:
                sid, short = n["id"], n["title"]; part = "Решение на данных"; sec = ""
                toc, body = s.data_step(n)
                words = len(re.sub(r"<[^>]+>", " ", body).split())
            minutes = max(1, math.ceil(words / 140)) + ntasks.get(sid, 0)
            meta.append({"id": sid, "short": short, "part": part, "min": minutes, "num": i, "kind": kind})
            pages += (f'<article class="view step" id="v-{esc(sid)}" data-step="{esc(sid)}" hidden><p class="crumb">{esc(part)} · шаг {i} из {len(steps)} · {esc(A)}{(", " + esc(sec or cfg["book"].get("section_label", ""))) if (sec or cfg["book"].get("section_label")) else ""} · <code class="idc">{esc(sid)}</code></p>'
                      f'<h2 tabindex="-1">{esc(short)}</h2><p class="meta">{esc(A)}, «{esc(T)}»{(", " + esc(cfg["book"]["year"])) if cfg["book"].get("year") else ""} · ≈{minutes} мин (оценка)</p>'
                      f'<p class="legend" aria-label="Легенда">Нажмите на предложение, чтобы увидеть источник (стр. = номер страницы PDF-скана книги; незнакомый термин: <a href="#/glossary">Словарь</a>): <span class="lg ca">автор</span> <span class="lg cm">модель</span> <span class="lg ch">гипотеза</span> <sup class="vk">✓</sup> проверено.</p>'
                      f'<nav class="toc" aria-label="Оглавление страницы"><b>На странице</b><ul>{toc}</ul></nav>{body}'
                      f'<div class="pn"><button data-prev>← Назад</button><button data-done>Отметить пройденным</button><button data-next>Дальше →</button></div></article>')
        # карта связей
        depth = {}
        def dp(i):
            if i in depth: return depth[i]
            pre = [l["to"] for l in s.byid[i]["links"] if l["type"] == "предпосылка"]
            depth[i] = 0 if not pre else 1 + max(dp(p) for p in pre); return depth[i]
        for n in s.nodes: dp(n["id"])
        cols = {}
        for n in order: cols.setdefault(depth[n["id"]], []).append(n["id"])
        pos = {i: (20 + d * 230, 20 + r * 52) for d, ids in cols.items() for r, i in enumerate(ids)}
        sh = {m["id"]: m for m in meta}
        edges, items = "", ""
        for n in order:
            for l in n["links"]:
                (x1, y1), (x2, y2) = pos[l["to"]], pos[n["id"]]
                edges += f'<path d="M{x1+200} {y1+18} C{x1+215} {y1+18} {x2-15} {y2+18} {x2} {y2+18}" class="edge {"ex" if l["type"]!="предпосылка" else ""}"/>'
            x, y = pos[n["id"]]
            items += f'<a href="#/step/{esc(n["id"])}"><rect x="{x}" y="{y}" width="200" height="36" rx="6" class="box"/><text x="{x+8}" y="{y+22}" class="t">{sh[n["id"]]["num"]}. {esc(textwrap.shorten(sh[n["id"]]["short"], 28, placeholder="…"))}</text></a>'
        W = 20 + (max(cols) + 1) * 230; H = 40 + max(len(v) for v in cols.values()) * 52
        mapsvg = f'<div class="tw" tabindex="0" role="region" aria-label="Карта связей, прокрутка"><svg viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Карта связей: стрелка идёт от шага-предпосылки к шагу, который на него опирается">{edges}{items}</svg></div>'
        maplist = "<ul class='maplist'>" + "".join(
            f'<li><a href="#/step/{esc(n["id"])}">{sh[n["id"]]["num"]}. {esc(sh[n["id"]]["short"])}</a> опирается на: ' +
            (", ".join(f'<a href="#/step/{esc(l["to"])}">{sh[l["to"]]["num"]}</a>' for l in n["links"] if l["type"] == "предпосылка") or "ничего в разделе") +
            (" · примеры: " + ", ".join(f'<a href="#/step/{esc(l["to"])}">{sh[l["to"]]["num"]}</a>' for l in n["links"] if l["type"] == "пример") if any(l["type"] == "пример" for l in n["links"]) else "") + "</li>" for n in order) + "</ul>"
        maxp = max(c["page"] for n in s.nodes for c in n["claims"])
        gl = glossary_rows(ROOT / cfg["book"].get("glossary", "domain-pack/geology/glossary.md"), maxp)
        if gl:
            glh = ("<p class='meta'>Термины и обозначения книги, определённые до конца этого раздела (по глоссарию доменного пакета; определения по книге, стр. = PDF-страница). "
                   f"Терминов: {len(gl)}.</p><p><label>Поиск: <input id='gsearch' type='search' autocomplete='off' aria-label='Поиск по словарю'></label></p>"
                   "<div class='tw' tabindex='0' role='region' aria-label='Словарь, прокрутка'><table><thead><tr><th scope='col'>Термин</th><th scope='col'>Определение по книге</th><th scope='col'>Стр.</th></tr></thead><tbody>"
                   + "".join(f"<tr><td>{esc(tex_inline(a))}</td><td>{esc(tex_inline(b))}</td><td>{esc(c)}</td></tr>" for a, b, c, _ in gl) + "</tbody></table></div>")
        else:
            glh = "<p class='meta'>Словарь для этого раздела не собран.</p>"
        data = {"id": s.chapter, "steps": meta, "parts": [p["title"] for p in cfg["parts"]], "ev": s.EV, "tasks": tasks, "dstep": s.dcalc}
        dj = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
        tpl = (TPL / "template.html").read_text()
        out = (tpl.replace("/*STYLE*/", (TPL / "style.css").read_text()).replace("/*APP*/", (TPL / "app.js").read_text())
               .replace("<!--DATA-->", dj).replace("<!--PAGES-->", pages).replace("<!--CARDS-->", cards).replace("<!--SUMMARY-->", summary)
               .replace("<!--MAP-->", mapsvg + maplist).replace("<!--GLOSSARY-->", glh).replace("<!--BOOK-->", esc(A))
               .replace("<!--TITLE-->", esc(f"Курс: {A}" + (f", {cfg['book']['title_suffix']}" if cfg["book"].get("title_suffix") else ""))))
        return out

    # ---- шаг «решение на данных»
    def data_step(s, d):
        s.dcalc = None; blocks = []; toc = ""
        intro = "<p>" + esc(d.get("intro") or "Три действия: признаки, правило, вывод. Все предложения шага взяты из утверждений слоя; нажмите на предложение, чтобы увидеть источник.") + "</p>"
        blocks.append(("in", "Задача", intro))
        for i, sec in enumerate(d["sections"]):
            h = ""
            for ref in sec["claims"]:
                k = s.key(ref); c = s.claim(k)
                h += f"<p>{s.cl(k, c['text'])} <span class='meta'>стр. {c['page']} PDF</span></p>"
            blocks.append((f"s{i}", sec["label"], h))
        cl = d["calc"]; cin = []
        for x in cl["inputs"]:
            k = s.key(x["claim"])
            if x["v"] not in s.claim(k)["text"]: s.warn.append(f"data_step: {x['v']} нет в {k}")
            cin.append(x)
        outs = []
        for o in cl["outputs"]:
            if o["book"] not in s.claim(s.key(o["claim"]))["text"]: s.warn.append(f"data_step: книжное {o['book']} нет в {o['claim']}")
            outs.append(dict(o, claim=s.key(o["claim"])))
        s.dcalc = {"title": cl["title"], "inputs": [dict(x, claim=s.key(x["claim"])) for x in cin], "outputs": outs}
        blocks.append(("calc", cl["title"], '<div class="wid" data-widget="dcalc"></div>'))
        toc = "".join(f'<li><a href="#" data-jump="b-{d["id"]}-{b[0]}">{esc(b[1])}</a></li>' for b in blocks)
        return toc, "".join(f'<section class="blk" id="b-{d["id"]}-{b[0]}"><h3>{esc(b[1])}</h3>{b[2]}</section>' for b in blocks) + (
            '<section class="blk"><h3>Проверьте себя</h3><div class="tasks" data-node="' + esc(d["id"]) + '"></div></section>')

    # ---- задания
    def tasks(s):
        out = []
        for t in s.cfg["tasks"]:
            nid = s.nid[t["node"]]; key = f"{nid}#{t['claim']}"; c = s.claim(key); txt = nrm(c["text"]); n = s.byid[nid]
            src = txt if t.get("src", "claim") == "claim" else nrm(" ".join(sum((w.get("steps", []) for w in n.get("worked_examples", [])), [])))
            ok = True
            if t["type"] == "single": ok = nrm(t.get("ev", t["answer"])) in txt and t["answer"] in t["options"]
            elif t["type"] == "multi": ok = all(nrm(a) in txt for a in t["answers"]) and set(t["answers"]) <= set(t["options"])
            elif t["type"] == "order":
                pos = -1
                for it in t["items"]:
                    p = src.find(nrm(it), pos + 1)
                    if p < 0: ok = False; break
                    pos = p
            elif t["type"] == "blank": ok = nrm(t["text"].replace("[[", "").replace("]]", "")) in txt and re.search(r"\[\[(.+?)\]\]", t["text"]).group(1) == t["answer"]
            elif t["type"] == "calc": ok = all(x in c["text"] for x in t["nums"])
            if not ok: s.warn.append(f"ЗАДАНИЕ {t['id']}: ответ не найден в {key}")
            out.append(dict(t, node=nid, claim=key))
        return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("chapter"); ap.add_argument("--prefix", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--config", help="путь к обвязке раздела (по умолчанию tools/course_config/<chapter>.json)")
    a = ap.parse_args()
    B = ROOT / "build" / a.chapter
    nodes = [n for n in json.load(open(B / "nodes.json")) if n["id"].startswith(a.prefix)]
    units = json.load(open(B / "units.json")); cfg = json.load(open(Path(a.config) if a.config else ROOT / "tools/course_config" / f"{a.chapter}.json"))
    if not nodes: sys.exit("нет узлов с префиксом " + a.prefix)
    b = Build(nodes, units, cfg, a.chapter); html_ = b.render()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True); (out / "index.html").write_text(html_, encoding="utf-8")
    types = sorted({t["type"] for t in b.tasks()}); st = {}
    for e in b.EV.values(): st[e["st"]] = st.get(e["st"], 0) + 1
    print(f"nodes={len(nodes)} tasks={len(cfg['tasks'])} types={types} claim-status={st} size={len(html_.encode())//1024}KB")
    for w in b.warn: print("WARN", w)
    sys.exit(1 if b.warn else 0)


if __name__ == "__main__": main()
