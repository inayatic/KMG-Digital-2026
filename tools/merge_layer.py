#!/usr/bin/env python3
"""Сборка единого слоя: merge_layer.py <chapter>
Сливает build/<ch>/sections/*/{nodes,routing}.json в build/<ch>/{nodes,routing}.json + coverage.md.
Сквозной order.rank по порядку книги; field_authors по умолчанию; проверка: id уникальны, каждая единица ровно в одном узле либо с причиной."""
import json, re, sys
from pathlib import Path


def norm_routes(raw):
    """routing.json разных агентов -> список {id, format, why}. Принимает список или словарь-обёртку {nodes|routes: [...]}, ключ id: id | node | node_id;
    если why нет, пустая строка. Записи без id или format пропускаются (маршрут узла тогда берётся из запасного значения)."""
    if isinstance(raw, dict):
        raw = raw.get("routes") or raw.get("nodes") or list(raw.values())[0] if raw else []
    out = []
    for r in raw or []:
        if not isinstance(r, dict): continue
        i = r.get("id") or r.get("node") or r.get("node_id")
        if i and r.get("format"): out.append({"id": i, "format": r["format"], "why": r.get("why", "")})
    return out

root = Path(__file__).resolve().parent.parent / "build" / sys.argv[1]
units = json.load(open(root / "units.json")); U = {u["id"]: u for u in units}
secs = sorted(json.load(open(root / "sections.json")), key=lambda s: (s["pages"][0], s["key"]))
nodes, routes, reasons, errs = [], {}, {}, []
for s in secs:
    d = root / "sections" / s["key"]
    for n in json.load(open(d / "nodes.json")): n["_sec"] = s["key"]; nodes.append(n)
    for r in norm_routes(json.load(open(d / "routing.json"))):
        routes[r["id"]] = {"format": r["format"], "why": r["why"]}
    for line in (d / "coverage.md").read_text().splitlines():
        c = [x.strip() for x in line.strip().strip("|").split("|")]
        if len(c) >= 2 and re.fullmatch(r"p\d{3}-\d{2}", c[0]) and not c[-1].lower().startswith(sys.argv[1][:3].lower() + "."): reasons[c[0]] = c[-1]
ap = root / "adopt.json"  # единицы на границах сегментов: докладываем в узел соседнего сегмента
for u, a in (json.load(open(ap)).items() if ap.exists() else []):
    tgt = next(n for n in nodes if n["id"] == a["node"])
    tgt["unit_ids"].append(u); tgt["claims"].append(a["claim"])
ids = [n["id"] for n in nodes]
errs += [f"дубль id {i}" for i in {x for x in ids if ids.count(x) > 1}]
owner = {}
for n in nodes:
    for u in n["unit_ids"]:
        if u not in U: errs.append(f"{n['id']}: нет единицы {u}")
        elif u in owner: errs.append(f"единица {u} в двух узлах: {owner[u]}, {n['id']}")
        else: owner[u] = n["id"]
unc = [u for u in U if u not in owner]
errs += [f"единица {u} без узла и без причины" for u in unc if u not in reasons]
DEF = {"it_analogy": "модель", "how_now": "модель", "inefficiency_lens": "модель", "misconception": "модель", "layers": "модель (пересказ текста автора)"}
for i, n in enumerate(nodes, 1):
    n["order"] = {**n.get("order", {}), "section_rank": n.get("order", {}).get("rank"), "rank": i}
    fa = n.setdefault("field_authors", {})
    for k, v in DEF.items(): 
        if k in n: fa.setdefault(k, v)
    if "route" not in n and n["id"] in routes: n["route"] = routes[n["id"]]
    n.pop("_sec", None)
    if "route" not in n: errs.append(f"{n['id']}: нет маршрута")
json.dump(nodes, open(root / "nodes.json", "w"), ensure_ascii=False, indent=1)
json.dump({n["id"]: n.get("route") for n in nodes}, open(root / "routing.json", "w"), ensure_ascii=False, indent=1)
fm = {}
for n in nodes: f = (n.get("route") or {}).get("format", "?"); fm[f] = fm.get(f, 0) + 1
with open(root / "coverage.md", "w") as f:
    f.write(f"# Покрытие {sys.argv[1]}\n\nЕдиниц: {len(U)}; в узлах: {len(owner)}; без узла, с причиной: {len(unc)}; узлов: {len(nodes)}.\nФорматы: {fm}\n\n## Единицы без узла\n| Единица | Стр. | Причина |\n|---|---|---|\n")
    for u in unc: f.write(f"| {u} | {U[u]['page']} | {reasons.get(u, '??')} |\n")
print(f"nodes={len(nodes)} units={len(U)} in-nodes={len(owner)} no-node={len(unc)} formats={fm} errors={len(errs)}")
print("\n".join(errs[:30]))
