#!/usr/bin/env python3
"""Стадия 1а: единицы главы. make_units.py <chapter> -> build/<ch>/units.json
Детерминированно (без модели): clean.md -> абзацы, формулы, таблицы, рисунки, задачи, примеры.
id = p<PDF-страница>-<номер на странице>; тип figure_desc = описание рисунка от модели (не слова автора)."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent

def kind(b, in_tasks):
    s = b.lstrip()
    if s.startswith("━━━ FORMAT"): return "figure_desc"
    if s.startswith("#"): return "heading"
    if s.startswith("|"): return "table"
    if s.startswith("$$") or (s.startswith("\\(") and s.rstrip().endswith("\\)") and len(s) < 200): return "formula"
    if re.match(r"(Рис\.|РИС\.)\s*\d+", s): return "caption"
    if re.match(r"(Таблица|ТАБЛИЦА)\s*\d+", s): return "caption"
    if re.match(r"[¹²³⁴⁵⁶⁷⁸⁹*]\s", s): return "footnote"
    if re.match(r"Пример\s*\d*", s): return "example"
    if in_tasks and re.match(r"\d+[.)]\s", s): return "problem"
    return "paragraph"

def main(ch):
    t = (ROOT / "build" / ch / "clean.md").read_text()
    units, section, in_tasks = [], "", False
    parts = re.split(r"<!-- page (\d+) -->", t)
    for i in range(1, len(parts), 2):
        page, body = int(parts[i]), parts[i + 1]
        blocks, cur = [], []
        # блок FORMAT целиком: от "----" до закрывающей "----"
        body = re.sub(r"-{3,}\s*\n+(━━━ FORMAT.*?)\n-{3,}", lambda m: "\n\n" + m.group(1).replace("\n\n", "\n") + "\n\n", body, flags=re.S)
        body = re.sub(r"\s*(?=━━━ FORMAT)", "\n\n", body)
        for b in re.split(r"\n\s*\n", body):
            b = b.strip()
            if b and not re.fullmatch(r"-{3,}", b): blocks.append(b)
        n = 0
        for b in blocks:
            k = kind(b, in_tasks)
            if k == "heading":
                section = re.sub(r"^#+\s*", "", b)
                in_tasks = bool(re.search(r"задач", b, re.I))
            n += 1
            units.append({"id": f"p{page:03d}-{n:02d}", "type": k, "page": page, "section": section, "text": b})
    o = ROOT / "build" / ch; (o / "units.json").write_text(json.dumps(units, ensure_ascii=False, indent=1))
    cnt = {}
    for u in units: cnt[u["type"]] = cnt.get(u["type"], 0) + 1
    print(ch, len(units), "units", cnt)

if __name__ == "__main__":
    main(sys.argv[1])
