#!/usr/bin/env python3
"""Курс целой главы: build_course_all.py <chapter>. Пишет out/<ch>/index.html (оглавление) и out/<ch>/<раздел>/index.html на каждый раздел.
Конфиг строится из слоя (разделы = части, заголовки шагов = заголовки узлов). Задания: build/<ch>/course/tasks-<раздел>.json (агент), проверяются как в build_course.py.
Без сервера и внешних запросов. Разделы без заданий собираются, но с предупреждением."""
import copy, html, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_course as bc

ROOT = bc.ROOT
esc = html.escape

def main(ch):
    B = ROOT / "build" / ch
    nodes = json.load(open(B / "nodes.json")); units = json.load(open(B / "units.json"))
    secs = [s for s in json.load(open(B / "sections.json")) if re.fullmatch(r"s\d\d|ch\w+", s["key"])]
    base = json.load(open(ROOT / f"tools/course_config/{ch}.json")) if (ROOT / f"tools/course_config/{ch}.json").exists() else {}
    book = base.get("book") or {"author_unit": units[0]["id"], "title_unit": units[1]["id"]}
    out = ROOT / "out" / ch; out.mkdir(parents=True, exist_ok=True)
    rows, warn_total, missing = [], 0, []
    for s in secs:
        key = s["key"]; pre = f"{ch[:3]}.{key}.".lower()
        ns = copy.deepcopy([n for n in nodes if n["id"].lower().startswith(pre)])
        if not ns: continue
        ids = {n["id"] for n in ns}
        for n in ns: n["links"] = [l for l in n.get("links", []) if l["to"] in ids]
        title = ns[0].get("section") or key
        tf = B / "course" / f"tasks-{key}.json"
        tasks = json.load(open(tf)) if tf.exists() else []
        if not tasks: missing.append(key)
        keys = [n["id"].split(".")[-1][:2] for n in ns]
        cfg = {"book": book, "parts": [{"title": title, "nodes": keys}], "short_titles": {}, "illustrations": {}, "tasks": tasks,
               "no_default_fig": True, "public": True, "home": '<a href="../index.html">Оглавление главы</a>', "title": f"Курс: {title}"}
        b = bc.Build(ns, units, cfg, f"{ch}.{key}")
        page = b.render(); d = out / key; d.mkdir(exist_ok=True); (d / "index.html").write_text(page, encoding="utf-8")
        for w in b.warn: print(f"WARN {key}: {w}")
        warn_total += len(b.warn)
        rows.append((key, title, len(ns), len(tasks), len(page.encode()) // 1024))
    idx = "".join(f'<li><a href="{k}/index.html">{esc(t)}</a> <span class="meta">шагов {n}, заданий {tk}</span></li>' for k, t, n, tk, _ in rows)
    (out / "index.html").write_text(f'<!DOCTYPE html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Курс по главе</title>'
        f'<style>body{{font:16px/1.5 system-ui;max-width:46rem;margin:0 auto;padding:1rem 16px}}.meta{{color:#666}}li{{margin:.4rem 0}}</style>'
        f'<h1>Курс по главе</h1><p class="meta">Учебник с доказательствами: у каждого утверждения есть источник (страница и цитата). Разделов: {len(rows)}.</p><ol>{idx}</ol>', encoding="utf-8")
    print(f"sections={len(rows)} nodes={sum(r[2] for r in rows)} tasks={sum(r[3] for r in rows)} warnings={warn_total} sections-without-tasks={missing}")
    sys.exit(1 if warn_total else 0)

if __name__ == "__main__": main(sys.argv[1])
