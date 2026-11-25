#!/usr/bin/env python3
"""Стадия 0: чистый эталон главы. clean_ref.py <chapter>
Читает chapters/<ch>/*.md (маркеры <!-- page N --> = номер PDF-страницы) и PDF.
Страницы md с OCR-мусором заменяются текстом из PDF-слоя, если он чище.
Для сканов (нет текстового слоя) мусорные страницы только помечаются: нужна ручная сверка.
Пишет build/<ch>/clean.md и build/<ch>/clean-report.json."""
import json, re, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATH = re.compile(r"\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|\$.*?\$", re.S)
# описания рисунков, добавленные моделью (не текст автора): "---- ━━━ FORMAT n: ..." до конца абзаца-блока
FIG = re.compile(r"-{3,}\s*━+ FORMAT.*?(?=\n\n\n|\Z)", re.S)
ODD = re.compile(r"\b[A-Za-z]*[a-z][A-Z]{2,}[A-Za-z]*\b")

def latin_share(t):
    t = MATH.sub("", t)
    t = FIG.sub("", t)
    lat, cyr = len(re.findall(r"[A-Za-z]", t)), len(re.findall(r"[А-Яа-яЁё]", t))
    return lat / (lat + cyr) if lat + cyr else 0

def garbled(t):
    t = FIG.sub("", MATH.sub("", t))
    return len(ODD.findall(t)) >= 5 or (latin_share(t) > 0.4 and len(re.findall(r"[А-Яа-яЁё]", t)) > 20)

def pdf_pages(pdfs):
    out = []
    for p in pdfs:  # части одной книги идут подряд
        out += subprocess.run(["pdftotext", str(p), "-"], capture_output=True, text=True).stdout.split("\f")[:-1]
    return out

def main(ch):
    d = ROOT / "chapters" / ch
    md = next(d.glob("*.md")).read_text()
    pdfs = sorted(d.glob("*.pdf"), key=lambda p: [int(x) for x in re.findall(r"\d+", p.stem)])
    pdf = pdf_pages(pdfs) if pdfs else []
    head, *rest = re.split(r"(<!-- page \d+ -->)", md)
    pages = {int(re.search(r"\d+", rest[i]).group()): rest[i + 1] for i in range(0, len(rest), 2)}
    # метки = номера PDF-страниц. Глава-выдержка: md содержит часть страниц, PDF вся книга (индекс по метке)
    # или только глава (столько же страниц, сколько в md: по порядку); иначе PDF-текст не используется.
    if pdf and max(pages) > len(pdf):
        if len(pdf) == len(pages): pdf = {n: pdf[i] for i, n in enumerate(sorted(pages))}
        else:
            print(f"{ch}: {len(pdf)} PDF pages vs {len(pages)} md pages (max {max(pages)}): PDF-текст не используется")
            pdf = {}
    else: pdf = {i + 1: t for i, t in enumerate(pdf)}
    rep, out = {}, [head]
    for n, t in pages.items():
        src = "md"
        if garbled(t):
            p = pdf.get(n, "")
            if len(p.strip()) >= 40 and not garbled(p) and latin_share(p) <= latin_share(t):
                t, src = f"\n{p.strip()}\n\n", "pdf-text"
            else:
                src = "FLAG-manual"  # скан или текстовый слой не лучше
        rep[n] = src
        out.append(f"<!-- page {n} -->" + t)
    o = ROOT / "build" / ch; o.mkdir(parents=True, exist_ok=True)
    (o / "clean.md").write_text("".join(out))
    (o / "clean-report.json").write_text(json.dumps(rep, indent=1))
    c = {k: list(rep.values()).count(k) for k in ("md", "pdf-text", "FLAG-manual")}
    print(ch, len(pages), "pages:", c, "flagged:", [n for n, s in rep.items() if s == "FLAG-manual"][:30])

if __name__ == "__main__":
    main(sys.argv[1])
