#!/usr/bin/env python3
"""Делит units.json на сегменты: split_sections.py <chapter> -> build/<ch>/sections/<key>/units.json + sections.json (индекс).
1. Границы по заголовкам § / Глава / ПРЕДИСЛОВИЕ / ЛИТЕРАТУРА (как раньше); оглавление в начале книги = «s00-front», литература и приложения
   (только во второй половине книги) = «s99-tail».
2. Сегмент всегда непрерывный: повторное появление ключа даёт новый сегмент (суффикс x2, x3 ...), а не склейку далёких частей.
3. Размер ограничен (MAX_CHARS, MAX_UNITS): слишком большой сегмент режется по заголовкам (цель TARGET_CHARS), если заголовков нет, по границе страницы.
   Для книг без «§» (главы по 100 страниц) это даёт разделы нужного для агента размера. Ключи разделов, которые собирает курс: s\\d\\d | ch\\w+.
Каждая единица попадает ровно в один сегмент (проверяется). Параметры: SPLIT_MAX_CHARS, SPLIT_TARGET_CHARS, SPLIT_MAX_UNITS (переменные окружения)."""
import json, os, re, sys
from pathlib import Path

MAX_CHARS = int(os.environ.get("SPLIT_MAX_CHARS", 60000))
TARGET_CHARS = int(os.environ.get("SPLIT_TARGET_CHARS", 35000))
MAX_UNITS = int(os.environ.get("SPLIT_MAX_UNITS", 220))

ch = sys.argv[1]
root = Path(__file__).resolve().parent.parent / "build" / ch
U = json.load(open(root / "units.json"))
N = len(U)
KEY = [(r"^#+\s*§\s*(\d+)", lambda m: f"s{int(m.group(1)):02d}"),
       (r"^#+\s*ПРЕДИСЛОВИЕ", lambda m: "s00-preface")]
TAIL = r"^#+\s*(СПИСОК\s+)?ЛИТЕРАТУР|^#+\s*ОГЛАВЛЕНИЕ|^#+\s*СОДЕРЖАНИЕ|^#+\s*ПРИЛОЖЕНИЕ|^#+\s*ПРЕДМЕТНЫЙ|^#+\s*ЗАКЛЮЧЕНИЕ"
TOC = r"^#+\s*(ОГЛАВЛЕНИЕ|СОДЕРЖАНИЕ)\s*$"

# --- 1. первичные границы
runs = []  # (key, [units]) в порядке книги, каждый run непрерывный
cur = "s00-front"; used = {}
def start(key):
    global cur
    if key != cur or not runs:
        n = used.get(key, 0)
        used[key] = n + 1
    cur = key
for i, u in enumerate(U):
    key = None
    if u["type"] == "heading":
        t = u["text"].strip()
        m = re.match(r"^#+\s*Глава\s+(\S+)", t)
        if m and not any(re.match(r"^#+\s*§", v["text"].strip()) for v in U[i + 1:i + 13] if v["type"] == "heading"):
            key = f"ch{m.group(1)}"
        for pat, f in KEY:
            mm = re.match(pat, t, re.I)
            if mm: key = f(mm); break
        else:
            if re.match(TOC, t, re.I) and i < 0.2 * N: key = "s00-front"
            elif re.match(TAIL, t, re.I) and i > 0.7 * N: key = "s99-tail"
    if key is not None and (not runs or runs[-1][0] != key):
        runs.append((key, []))
    if not runs: runs.append((cur, []))
    runs[-1][1].append(u)

# --- 2. непрерывность: повторный ключ получает суффикс
seen = {}; segs = []
for key, us in runs:
    seen[key] = seen.get(key, 0) + 1
    segs.append((key if seen[key] == 1 else f"{key}x{seen[key]}", us))

# --- 3. ограничение размера
def chars(us): return sum(len(u["text"]) for u in us)
def split_big(key, us):
    if chars(us) <= MAX_CHARS and len(us) <= MAX_UNITS: return [(key, us)]
    parts, curp, c = [], [], 0
    for j, u in enumerate(us):
        nxt = us[j + 1] if j + 1 < len(us) else None
        curp.append(u); c += len(u["text"])
        over = c >= TARGET_CHARS or len(curp) >= MAX_UNITS * TARGET_CHARS / MAX_CHARS
        # режем перед заголовком, либо на границе страницы, если заголовка нет слишком долго
        if nxt is not None and over and (nxt["type"] == "heading" or c >= 1.5 * TARGET_CHARS and nxt["page"] != u["page"]):
            parts.append(curp); curp, c = [], 0
    if curp:
        if parts and chars(curp) < 0.25 * TARGET_CHARS: parts[-1] += curp
        else: parts.append(curp)
    base = key if re.fullmatch(r"ch\w+", key) else f"ch_{key.replace('-', '')}"
    return [(f"{base}{chr(97 + k)}" if len(parts) > 1 else key, p) for k, p in enumerate(parts)]

final = []
for key, us in segs:
    final += split_big(key, us)

idx = []
for k, us in final:
    d = root / "sections" / k; d.mkdir(parents=True, exist_ok=True)
    json.dump(us, open(d / "units.json", "w"), ensure_ascii=False, indent=1)
    idx.append({"key": k, "units": len(us), "pages": [us[0]["page"], us[-1]["page"]], "chars": chars(us)})
assert sum(i["units"] for i in idx) == N, "единицы потеряны или продублированы"
assert len({i["key"] for i in idx}) == len(idx), "дубль ключа раздела"
json.dump(idx, open(root / "sections.json", "w"), ensure_ascii=False, indent=1)
for i in idx: print(i["key"], i["units"], i["pages"], i["chars"])
