#!/usr/bin/env python3
"""Делит units.json на сегменты по заголовкам § / Глава / ПРЕДИСЛОВИЕ / ЛИТЕРАТУРА.
split_sections.py <chapter> -> build/<ch>/sections/<key>/units.json + sections.json (индекс).
Каждая единица попадает ровно в один сегмент (проверяется)."""
import json, re, sys
from pathlib import Path
ch = sys.argv[1]
root = Path(__file__).resolve().parent.parent / "build" / ch
U = json.load(open(root / "units.json"))
KEY = [(r"^#+\s*§\s*(\d+)", lambda m: f"s{int(m.group(1)):02d}"),
       (r"^#+\s*ПРЕДИСЛОВИЕ", lambda m: "s00-preface"),
       (r"^#+\s*(СПИСОК\s+)?ЛИТЕРАТУР|^#+\s*ОГЛАВЛЕНИЕ|^#+\s*ПРИЛОЖЕНИЕ|^#+\s*ПРЕДМЕТНЫЙ", lambda m: "s99-tail")]
seg, cur = {}, "s00-front"
for i, u in enumerate(U):
    if u["type"] == "heading":
        m = re.match(r"^#+\s*Глава\s+(\S+)", u["text"].strip())
        # «Глава N» без параграфа сразу после (в 12 следующих единицах) — самостоятельный сегмент
        if m and not any(re.match(r"^#+\s*§", v["text"].strip()) for v in U[i + 1:i + 13] if v["type"] == "heading"):
            cur = f"ch{m.group(1)}"
        for pat, f in KEY:
            m = re.match(pat, u["text"].strip(), re.I)
            if m: cur = f(m); break
    seg.setdefault(cur, []).append(u)
idx = []
for k, us in seg.items():
    d = root / "sections" / k; d.mkdir(parents=True, exist_ok=True)
    json.dump(us, open(d / "units.json", "w"), ensure_ascii=False, indent=1)
    idx.append({"key": k, "units": len(us), "pages": [us[0]["page"], us[-1]["page"]], "chars": sum(len(u["text"]) for u in us)})
assert sum(i["units"] for i in idx) == len(U)
json.dump(idx, open(root / "sections.json", "w"), ensure_ascii=False, indent=1)
for i in idx: print(i["key"], i["units"], i["pages"], i["chars"])
