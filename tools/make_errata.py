#!/usr/bin/env python3
"""Лист опечаток и огрехов распознавания главы: make_errata.py <chapter> [domain]
Собирает все ocr_note утверждений и узлов из build/<ch>/sections/*/nodes.json в domain-pack/<domain>/errata/<ch>.md.
Ничего не выдумывает: только записи слоя (их оставили агенты и проверка), с узлом, страницей и текстом."""
import json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
ch = sys.argv[1]; domain = sys.argv[2] if len(sys.argv) > 2 else "geology"
secs = sorted((ROOT / "build" / ch / "sections").glob("*/nodes.json"))
rows = []
for f in secs:
    for n in json.load(open(f)):
        if n.get("ocr_note"):
            rows.append((n["id"], "узел", "", n["ocr_note"]))
        for c in n.get("claims") or []:
            if c.get("ocr_note"):
                rows.append((n["id"], c.get("id", ""), c.get("page", ""), c["ocr_note"]))
        for key in ("worked_examples", "problems"):
            for w in n.get(key) or []:
                if w.get("ocr_note"):
                    rows.append((n["id"], key, w.get("page", ""), w["ocr_note"]))
esc = lambda s: re.sub(r"\s+", " ", str(s)).replace("|", "\\|").strip()
out = ROOT / "domain-pack" / domain / "errata"; out.mkdir(parents=True, exist_ok=True)
with open(out / f"{ch}.md", "w") as fh:
    fh.write(f"# Лист опечаток и огрехов распознавания: {ch}\n\n")
    fh.write("Собран скриптом `tools/make_errata.py` из полей `ocr_note` учебного слоя (узлов, утверждений, примеров, задач). "
             "Что в книге записано у автора с ошибкой, а что исказило распознавание, указано в самой записи. "
             "Страницы = PDF-страницы. Чтения «по скану» сверены агентами при проверке слоя; остальное не подтверждено.\n\n")
    fh.write(f"Записей: {len(rows)}.\n\n| Узел | Где | Стр. | Запись |\n|---|---|---|---|\n")
    for nid, where, pg, note in rows:
        fh.write(f"| {nid} | {esc(where)} | {pg} | {esc(note)} |\n")
print(f"{ch}: {len(rows)} записей -> {out / (ch + '.md')}")
