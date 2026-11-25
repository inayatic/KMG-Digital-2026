#!/usr/bin/env python3
"""Конвертер нашего слоя в схемы организаторов: to_organizer_schema.py <chapter>
build/<ch>/{nodes,coverage...} -> build/<ch>/org/{layer,coverage,routing}.json + conversion-report.md
Детерминированно переносит, что есть; чего в слое нет — ставит пустое значение и пишет в отчёт (пробелы заполняет агент)."""
import json, re, sys
from collections import Counter
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parent.parent
ch = sys.argv[1]; B = ROOT / "build" / ch; S = ROOT / "reference/organizers/01_схемы"
nodes = json.load(open(B / "nodes.json")); units = json.load(open(B / "units.json")); U = {u["id"]: u for u in units}
reasons = {}
for line in open(B / "coverage.md"):
    c = [x.strip() for x in line.strip().strip("|").split("|")]
    if len(c) == 3 and re.fullmatch(r"p\d{3}-\d{2}", c[0]): reasons[c[0]] = c[2]
SK = {"formula": "formula", "table": "table", "problem": "task", "caption": "figure_caption", "figure_desc": "figure_description_model"}
KIND = {"наблюдение": "observation", "вывод": "inference", "допущение": "assumption"}
LT = {"предпосылка": "prerequisite", "пример": "example_of", "опровергает заблуждение": "refutes_misconception", "переход к данным": "to_data"}
CK = {"figure_desc": "figure", "caption": "figure", "formula": "formula", "table": "table", "example": "worked_example", "problem": "task", "heading": "heading"}
gaps = Counter()
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[«»\"'`]", "", s)).strip().lower()

def pad(u, t):  # слишком короткая единица («Рис.19.»): дописываем конец предыдущей единицы той же страницы (в md они подряд), иначе начало следующей
    if len(t) >= 8: return t
    clean = lambda x: re.sub(r"\s+", " ", x["text"].lstrip("#| ").strip())
    same = [x for x in units if x["page"] == u["page"] and x["type"] != "figure_desc"]
    prev = [x for x in same if x["id"] < u["id"]]; nxt = [x for x in same if x["id"] > u["id"]]
    if prev: return (clean(prev[-1])[-80:] + " " + t).strip()
    if nxt: return (t + " " + clean(nxt[0])[:80]).strip()
    return t

def quote_for(c, ut):
    q = (c.get("quote") or "").strip()
    pool = [(u, U[u]) for u in c["unit_ids"] if u in U]
    if q and len(q) >= 8: return q
    if q:  # слишком короткая: расширяем до контекста внутри той же единицы
        for _, u in pool:
            i = u["text"].lower().find(q.lower())
            if i >= 0: gaps["quote_extended"] += 1; return pad(u, re.sub(r"\s+", " ", u["text"][i:i + 90]).strip())
    for _, u in pool:  # цитаты нет (утверждение модели): первая фраза опорной единицы
        if u["type"] != "figure_desc":
            t = re.sub(r"\s+", " ", u["text"].lstrip("#| ").strip()); gaps["quote_from_unit"] += 1
            t = pad(u, t)
            return t[:160]
    if pool: gaps["quote_from_figure_desc"] += 1; return re.sub(r"\s+", " ", pool[0][1]["text"])[:120]
    gaps["quote_missing"] += 1; return "(нет цитаты)"

def fld(t, by_model=True, hyp=False):
    d = {"text": t or "", "by_model": by_model}
    if hyp: d["hypothesis"] = True
    if not t: gaps["empty_field"] += 1
    return d

out = []
for n in nodes:
    nid = n["id"]; L = n.get("layers") or {}; cl = []; ns = []
    for i, c in enumerate(n["claims"], 1):
        u0 = U.get(c["unit_ids"][0]) if c["unit_ids"] else None
        sk = "text"
        if u0 and u0["type"] in SK: sk = SK[u0["type"]]
        o = {"id": f"{nid}#c{i}", "text": c["text"], "kind": KIND[c["kind"]], "page_pdf": c["page"], "page_print": None,
             "quote": quote_for(c, nid), "source_kind": sk, "by_model": c.get("author") != "автор", "unit_ids": c["unit_ids"]}
        if c.get("author") == "гипотеза": o["hypothesis"] = True
        if c.get("ocr_note"):
            o["ocr_note"] = c["ocr_note"]
            if re.search(r"скан", c["ocr_note"], re.I): o["needs_scan"] = True; ns.append({"page": c["page"], "what": c["ocr_note"][:160]})
        cl.append(o)
    pages = sorted({c["page"] for c in n["claims"]} | {U[u]["page"] for u in n["unit_ids"] if u in U})
    di = n.get("data_implication") or {}; ia = n.get("it_analogy"); il = n.get("inefficiency_lens")
    if not ia: gaps["it_analogy_missing"] += 1
    if not di: gaps["data_meaning_missing"] += 1
    gaps["data_meaning.breaks_missing"] += 1; gaps["threshold_defaulted_false"] += 1; gaps["terms_introduced_empty"] += 1
    gaps["difficulty_old_semantics"] += 1; gaps["layers.main_from_claims"] += 1
    main = " ".join(c["text"] for c in n["claims"][:2])
    node = {
     "id": nid, "order": n["order"]["rank"], "title": n["title"],
     "why_here": fld((n.get("order") or {}).get("why_before_next", "")),
     "difficulty": {"primary": n["difficulty"]["primary"], "secondary": n["difficulty"].get("secondary")},
     "threshold": False, "pages": pages,
     "layers": {"topic": fld(n["title"]), "main": fld(main), "mechanism": fld(L.get("mechanism")), "practice": fld(L.get("practice")),
                "nuances": fld(L.get("nuances")), "deeper": [fld(x) for x in (L.get("deeper") or [])]},
     "claims": cl,
     "links": [{"type": LT[l["type"]], "target": l["to"]} for l in n["links"]],
     "misconception": ({"ref": None, "text": n["misconception"], "by_model": True} if n.get("misconception") else None),
     "data_meaning": {"from_chapter": fld(di.get("text"), di.get("author") != "автор", di.get("author") == "гипотеза"), "breaks": fld(""), "hypotheses": []},
     "it_analogy": {"text": (ia or {}).get("text", ""), "breaks_where": (ia or {}).get("breaks_when", ""), "by_model": True},
     "now_practice": fld(n["how_now"]) if n.get("how_now") else None,
     "inefficiency_lens": ({**{k: il.get(k, "") for k in ("inputs", "manual_steps", "judgment_points", "time", "typical_errors")}, "by_model": True} if il else None),
     "terms_introduced": [], "terms_used": [], "needs_scan": ns, "decision_on_data": None,
     "worked_examples": [{"page_pdf": w["page"], "condition": w.get("condition", ""), "steps": w.get("steps") or [], "result": w.get("result", ""), "figure": None} for w in (n.get("worked_examples") or [])],
     "book_tasks": [{"number": str(p.get("number", "")), "page_pdf": p["page"], "text": p.get("statement", ""), "figure": p.get("figure_unit_id")} for p in (n.get("problems") or [])],
     "unit_ids": n["unit_ids"], "external_prereqs": n.get("external_prereqs") or [], "field_authors": n.get("field_authors") or {}, "section": n.get("section"),
     "legacy_difficulty_unverified": n["difficulty"],
    }
    out.append(node)
chap = f"{ch}_full"; src = next((ROOT / "chapters" / ch).glob("*.md")).as_posix().replace(ROOT.as_posix() + "/", "")
layer = {"chapter": chap, "source": src, "pdf_pages": sorted({str(p) for n in out for p in n["pages"]}, key=int), "generated_by": "конвейер команды; слой по разделам агентами Claude, сборка tools/merge_layer.py", "nodes": out}
cov = []
owner = {u: n["id"] for n in nodes for u in n["unit_ids"]}
for u in units:
    ex = re.sub(r"\s+", " ", u["text"].lstrip("#| ").strip()); ex = " ".join(ex.split()[:15])
    cov.append({"unit_id": u["id"].replace("-", "."), "kind": CK.get(u["type"], "paragraph"), "page_pdf": u["page"], "excerpt": ex,
                "node_ids": [owner[u["id"]]] if u["id"] in owner else [], "reason": None if u["id"] in owner else reasons.get(u["id"], "??")})
route_src = json.load(open(B / "routing.json"))
routes = []
for n in nodes:
    r = n.get("route") or route_src.get(n["id"]) or {}
    gaps["routing.video_scores_missing"] += 1
    routes.append({"node_id": n["id"], "format": r.get("format"), "video_scores": {k: 0 for k in ("time", "invisible", "scale", "counterintuitive", "cause_effect")}, "template": None, "why": r.get("why", "")})
org = B / "org"; org.mkdir(exist_ok=True)
for name, obj, sch in (("layer", layer, "node"), ("coverage", {"chapter": chap, "rows": cov}, "coverage"), ("routing", {"chapter": chap, "routes": routes}, "routing")):
    json.dump(obj, open(org / f"{name}.json", "w"), ensure_ascii=False, indent=1)
    v = Draft202012Validator(json.load(open(S / f"{sch}.schema.json"))); errs = list(v.iter_errors(obj))
    print(name, "schema errors:", len(errs)); [print("  ", list(e.path)[:4], e.message[:110]) for e in errs[:5]]
raw = norm(next((ROOT / "chapters" / ch).glob("*.md")).read_text())
bad = [(c["id"], c["page_pdf"]) for n in out for c in n["claims"] if c["source_kind"] != "figure_description_model" and norm(c["quote"]) not in raw]
with open(org / "conversion-report.md", "w") as f:
    f.write(f"# Отчёт конвертации {ch} -> схемы организаторов\n\nУзлов {len(out)}, утверждений {sum(len(n['claims']) for n in out)}.\n\n## Пробелы (заполняет агент, не выдумывать)\n")
    for k, v in gaps.most_common(): f.write(f"- {k}: {v}\n")
    f.write(f"\n## Цитаты, которых нет в ИСХОДНОМ md (только в нашем clean.md): {len(bad)}\n" + "\n".join(f"- {a} (стр. {p})" for a, p in bad[:80]) + "\n")
print(dict(gaps)); print("quotes not in raw md:", len(bad))
