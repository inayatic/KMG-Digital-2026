#!/usr/bin/env python3
"""Применяет build/<ch>/org/patches/*.json к org/layer.json и org/routing.json, валидирует по схемам организаторов.
apply_patches.py <chapter>"""
import json, sys
from pathlib import Path
from jsonschema import Draft202012Validator
ROOT = Path(__file__).resolve().parent.parent; B = ROOT / "build" / sys.argv[1] / "org"; S = ROOT / "reference/organizers/01_схемы"
layer = json.load(open(B / "layer.json")); routing = json.load(open(B / "routing.json"))
N = {n["id"]: n for n in layer["nodes"]}; R = {r["node_id"]: r for r in routing["routes"]}
FMT = {"шортс", "длинное видео", "интерактив", "практикум на данных", "карточки", "текст"}
DIF = {"М", "В", "И", "Ф", "П", "Пр", "Н", "Р"}
applied = missing = bad = 0
for f in sorted((B / "patches").glob("*.json")):
    for p in json.load(open(f)):
        n = N.get(p["id"])
        if not n: missing += 1; continue
        d = p.get("difficulty") or {}
        if d.get("primary") in DIF:
            n["difficulty"] = {"primary": d["primary"], "secondary": d.get("secondary") if d.get("secondary") in DIF else None}
            n.pop("legacy_difficulty_unverified", None)
        else: bad += 1
        if isinstance(p.get("threshold"), bool): n["threshold"] = p["threshold"]
        n["terms_introduced"] = list(p.get("terms_introduced") or []); n["terms_used"] = list(p.get("terms_used") or [])
        if p.get("main"): n["layers"]["main"] = {"text": p["main"], "by_model": True}
        if p.get("breaks"): n["data_meaning"]["breaks"] = {"text": p["breaks"], "by_model": True}
        n["data_meaning"]["hypotheses"] = [{"text": h if isinstance(h, str) else h.get("text", ""), "by_model": True, "hypothesis": True} for h in (p.get("hypotheses") or [])]
        a = p.get("it_analogy")
        if a and a.get("text") and not n["it_analogy"]["text"]: n["it_analogy"] = {"text": a["text"], "breaks_where": a.get("breaks_where", ""), "by_model": True}
        r = R[p["id"]]; vs = p.get("video_scores") or {}
        if set(vs) == set(r["video_scores"]) and all(isinstance(v, int) and 0 <= v <= 2 for v in vs.values()): r["video_scores"] = vs; r["scored"] = True
        else: bad += 1
        if p.get("route_format") in FMT: r["format"] = p["route_format"]
        if p.get("secondary_format") in FMT: r["secondary_format"] = p["secondary_format"]
        if p.get("route_why"): r["why"] = p["route_why"]
        applied += 1
json.dump(layer, open(B / "layer.json", "w"), ensure_ascii=False, indent=1); json.dump(routing, open(B / "routing.json", "w"), ensure_ascii=False, indent=1)
unscored = sum(1 for r in R.values() if not r.get("scored")); legacy = sum(1 for n in N.values() if "legacy_difficulty_unverified" in n)
for name, obj, sch in (("layer", layer, "node"), ("routing", routing, "routing")):
    errs = list(Draft202012Validator(json.load(open(S / f"{sch}.schema.json"))).iter_errors(obj)); print(name, "schema errors:", len(errs), [e.message[:80] for e in errs[:3]])
print(f"patches applied={applied} missing_nodes={missing} bad_fields={bad}; nodes with old difficulty={legacy}; routes without scores={unscored}")
