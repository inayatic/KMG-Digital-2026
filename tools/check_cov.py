#!/usr/bin/env python3
"""Проверка покрытия и целостности слоя по разделам: check_cov.py <chapter> [--json] [--section KEY]
Ищет в build/<ch>/sections/<key>/: единицы без узла и без причины (причина = строка в coverage.md, где последняя ячейка не id узла),
единицы в двух узлах, ссылки на несуществующие единицы, узлы без маршрута в routing.json, раздел без nodes.json.
Выход: код 0, если проблем нет; код 1 и список. --json печатает словарь {раздел: [проблемы]}."""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def norm_routes(raw):
    if isinstance(raw, dict):
        raw = raw.get("routes") or raw.get("nodes") or (list(raw.values())[0] if raw else [])
    return {(r.get("id") or r.get("node") or r.get("node_id")) for r in (raw or []) if isinstance(r, dict) and r.get("format")}


def check(ch, only=None):
    root = ROOT / "build" / ch / "sections"; pre = ch[:3].lower() + "."
    res = {}
    for d in sorted(root.iterdir()):
        if not d.is_dir() or (only and d.name != only): continue
        probs = []
        U = {u["id"] for u in json.load(open(d / "units.json"))}
        if not (d / "nodes.json").exists():
            res[d.name] = ["нет nodes.json"]; continue
        nodes = json.load(open(d / "nodes.json"))
        reasons = {}
        cov = d / "coverage.md"
        if cov.exists():
            for line in cov.read_text().splitlines():
                c = [x.strip() for x in line.strip().strip("|").split("|")]
                if len(c) >= 2 and re.fullmatch(r"p\d{3}-\d{2}", c[0]) and not c[-1].lower().startswith(pre) and c[-1]: reasons[c[0]] = c[-1]
        owner = {}
        for n in nodes:
            for u in n.get("unit_ids", []):
                if u not in U: probs.append(f"узел {n['id']}: нет единицы {u}")
                elif u in owner: probs.append(f"единица {u} в двух узлах: {owner[u]}, {n['id']}")
                else: owner[u] = n["id"]
        miss = sorted(u for u in U if u not in owner and u not in reasons)
        if miss: probs.append("единицы без узла и без причины: " + ", ".join(miss))
        rt = d / "routing.json"
        have = norm_routes(json.load(open(rt))) if rt.exists() else set()
        nom = [n["id"] for n in nodes if n["id"] not in have]
        if nom: probs.append("узлы без маршрута: " + ", ".join(nom))
        if probs: res[d.name] = probs
    return res


if __name__ == "__main__":
    ch = sys.argv[1]; only = sys.argv[sys.argv.index("--section") + 1] if "--section" in sys.argv else None
    r = check(ch, only)
    if "--json" in sys.argv: print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        for k, v in r.items():
            print(k)
            for x in v: print("  -", x)
        print(f"разделов с проблемами: {len(r)}")
    sys.exit(1 if r else 0)
