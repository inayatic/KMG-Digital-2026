#!/usr/bin/env python3
"""Проверка выдачи в формате организаторов, как это сделает жюри: check_org.py <chapter>
схемы (layer/coverage/routing) + каждая цитата дословно (без пробелов/регистра/кавычек) на странице page_pdf ИСХОДНОГО md главы."""
import json, re, sys
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parent.parent; ch = sys.argv[1]; O = ROOT / "build" / ch / "org"; S = ROOT / "reference/organizers/01_схемы"
raw = next((ROOT / "chapters" / ch).glob("*.md")).read_text()
norm = lambda s: re.sub(r"\s+", "", re.sub(r"[«»\"'`]", "", s)).lower()
parts = re.split(r"<!-- page (\d+) -->", raw); P = {int(parts[i]): norm(parts[i + 1]) for i in range(1, len(parts), 2)}
bad = 0
for name, sch in (("layer", "node"), ("coverage", "coverage"), ("routing", "routing")):
    obj = json.load(open(O / f"{name}.json")); errs = list(Draft202012Validator(json.load(open(S / f"{sch}.schema.json"))).iter_errors(obj))
    print(f"{name}: schema errors {len(errs)}"); bad += len(errs)
L = json.load(open(O / "layer.json"))["nodes"]; fail = []; fd = 0
for n in L:
    for c in n["claims"]:
        if c["source_kind"] == "figure_description_model": fd += 1; continue
        if norm(c["quote"]) not in P.get(c["page_pdf"], ""): fail.append((c["id"], c["page_pdf"], c["quote"][:60]))
print(f"quotes: {sum(len(n['claims']) for n in L)} claims, figure-description {fd}, not found on page in raw md: {len(fail)}")
for f in fail[:40]: print("  ", f)
ids = {n["id"] for n in L}; bl = [(n["id"], l["target"]) for n in L for l in n["links"] if l["type"] in ("prerequisite", "example_of") and l["target"] not in ids]
print("broken node links:", len(bl), bl[:5])
sys.exit(1 if bad or fail or bl else 0)
