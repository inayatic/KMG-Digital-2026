#!/usr/bin/env python3
"""Исправляет направление связей «предпосылка»: fix_prereq_direction.py <chapter> [--dry]
Связь A --предпосылка--> B означает «A требует B», то есть B должен идти раньше A (order.rank меньше).
Если B стоит ПОЗЖЕ A, агент записал связь в обратную сторону («A — предпосылка для B»). Скрипт переворачивает её:
удаляет A->B и добавляет B->A, если такой связи ещё нет. Только внутри раздела, порядок по order.rank.
Циклы вида A<->B после этого исчезают (остаётся только связь назад по порядку)."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ch = sys.argv[1]; dry = "--dry" in sys.argv
tot = 0
for f in sorted((ROOT / "build" / ch / "sections").glob("*/nodes.json")):
    d = json.load(open(f)); by = {n["id"]: n for n in d}
    rank = {n["id"]: (n.get("order") or {}).get("rank") for n in d}
    flips = []
    for n in d:
        keep = []
        for l in n.get("links") or []:
            t = l.get("to")
            if l.get("type") == "предпосылка" and t in rank and None not in (rank[n["id"]], rank[t]) and rank[t] > rank[n["id"]]:
                flips.append((n["id"], t))
            else:
                keep.append(l)
        n["links"] = keep
    for a, b in flips:
        tgt = by[b]
        if not any(l.get("type") == "предпосылка" and l.get("to") == a for l in tgt["links"]):
            tgt["links"].append({"to": a, "type": "предпосылка"})
    if flips:
        tot += len(flips); print(f"{f.parent.name}: перевёрнуто {len(flips)}")
        if not dry: json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
print(f"всего: {tot}" + (" (dry-run)" if dry else ""))
