#!/usr/bin/env python3
"""Детерминированные проверки слоя: check_nodes.py <nodes.json> <units.json>
schema, цитаты на своей PDF-странице вне figure_desc, существование unit_ids/links, покрытие."""
import json, re, sys
from jsonschema import Draft202012Validator
nodes, units = (json.load(open(p)) for p in sys.argv[1:3])
schema = json.load(open(__import__("pathlib").Path(__file__).parent.parent / "schema/node.draft.json"))
norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[«»\"'`]", "", s)).strip().lower()
U = {u["id"]: u for u in units}
ids = {n["id"] for n in nodes}
err, used = [], set()
v = Draft202012Validator(schema)
for n in nodes:
    for e in v.iter_errors(n): err.append(f"{n['id']}: schema {list(e.path)} {e.message[:80]}")
    used |= set(n["unit_ids"])
    for c in n["claims"]:
        for u in c["unit_ids"]:
            if u not in U: err.append(f"{c['id']}: unknown unit {u}")
        if c["author"] == "автор":
            q = norm(c.get("quote", ""))
            pool = [norm(u["text"]) for u in units if u["page"] == c["page"] and u["type"] != "figure_desc"]
            if not q: err.append(f"{c['id']}: author=автор без цитаты")
            elif not any(q in p for p in pool): err.append(f"{c['id']}: цитата не найдена на стр. {c['page']}")
        for u in c["unit_ids"]:
            if u in U and U[u]["type"] == "figure_desc" and c["author"] == "автор": err.append(f"{c['id']}: автор ссылается на figure_desc {u}")
    for l in n["links"]:
        if l["to"] not in ids: err.append(f"{n['id']}: link to unknown {l['to']}")
missing = [u for u in U if u not in used]
print(f"nodes={len(nodes)} units={len(U)} covered={len(used & set(U))} not-in-any-node={len(missing)} errors={len(err)}")
print("\n".join(err[:40])); print("uncovered:", missing[:15])
