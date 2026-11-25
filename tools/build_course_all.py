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
    secs = [s for s in json.load(open(B / "sections.json")) if not re.match(r"s00|s99", s["key"])]
    base = json.load(open(ROOT / f"tools/course_config/{ch}.json")) if (ROOT / f"tools/course_config/{ch}.json").exists() else {}
    book = base.get("book") or {"author_unit": units[0]["id"], "title_unit": units[1]["id"]}
    out = ROOT / "out" / ch; out.mkdir(parents=True, exist_ok=True)
    rows, warn_total, missing, dropped, rejected = [], 0, [], 0, 0
    for s in secs:
        key = s["key"]; pre = f"{ch[:3]}.{key}.".lower()
        ns = copy.deepcopy([n for n in nodes if n["id"].lower().startswith(pre)])
        if not ns: continue
        ids = {n["id"] for n in ns}
        for n in ns: n["links"] = [l for l in n.get("links", []) if l["to"] in ids]
        title = ns[0].get("section") or key
        tf = B / "course" / f"tasks2-{key}.json"
        if not tf.exists(): tf = B / "course" / f"tasks-{key}.json"  # v2 (применение правила к новой ситуации) приоритетнее v1
        tasks = json.load(open(tf)) if tf.exists() else []
        rf = B / "course" / f"review-out-{key}.json"  # решения verifier по заданиям: reject снимает, fix заменяет по id
        if rf.exists():
            r = json.load(open(rf)); bad = {x["id"] for x in r.get("reject", [])}; fx = {x["id"]: x for x in r.get("fix", [])}
            tasks = [fx.get(t["id"], t) for t in tasks if t["id"] not in bad]; rejected += len(bad)
        if not tasks: missing.append(key)
        keys = [n["id"].split(".")[-1][:2] for n in ns]
        cfg = {"book": book, "parts": [{"title": title, "nodes": keys}], "short_titles": {}, "illustrations": {}, "tasks": tasks,
               "no_default_fig": True, "drop_bad": True, "public": True, "home": '<a href="../index.html">Оглавление главы</a>', "title": f"Курс: {title}"}
        b = bc.Build(ns, units, cfg, f"{ch}.{key}")
        page = b.render(); d = out / key; d.mkdir(exist_ok=True); (d / "index.html").write_text(page, encoding="utf-8")
        # вход для проверки заданий: только прошедшие сборку, с утверждениями-основаниями
        cl = {(n["id"], c["id"]): c for n in ns for c in n["claims"]}; w0, d0 = list(b.warn), getattr(b, 'dropped', 0); b.warn.clear(); good = b.tasks(); b.warn[:] = w0; b.dropped = d0
        rv = [{"task": t, "basis_claims": [{"id": x, "page": cl[(t["claim"].split("#")[0], x)]["page"], "text": cl[(t["claim"].split("#")[0], x)]["text"], "quote": cl[(t["claim"].split("#")[0], x)].get("quote", "")} for x in (t.get("basis") or [t["claim"].split("#")[1]])]} for t in good]
        (B / "course" / f"review-in-{key}.json").write_text(json.dumps(rv, ensure_ascii=False, indent=1))
        (B / "course" / f"final-{key}.json").write_text(json.dumps(b.tasks(), ensure_ascii=False, indent=1)); b.warn[:] = w0; b.dropped = d0  # итоговые задания (после проверки и решений verifier)
        for w in b.warn: print(f"WARN {key}: {w}")
        drop = getattr(b, "dropped", 0); warn_total += len(b.warn) - drop; dropped += drop  # отброшенные задания не ломают сборку, но считаются
        rows.append((key, title, len(ns), len(tasks) - drop, len(page.encode()) // 1024))
    idx = "".join(f'<li><a href="{k}/index.html">{esc(t)}</a> <span class="meta">шагов {n}, заданий {tk}</span></li>' for k, t, n, tk, _ in rows)
    (out / "index.html").write_text(f'<!DOCTYPE html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Курс по главе</title>'
        f'<style>body{{font:16px/1.5 system-ui;max-width:46rem;margin:0 auto;padding:1rem 16px}}.meta{{color:#666}}li{{margin:.4rem 0}}</style>'
        f'<h1>Курс по главе</h1><p class="meta">Учебник с доказательствами: у каждого утверждения есть источник (страница и цитата). Разделов: {len(rows)}.</p><ol>{idx}</ol>', encoding="utf-8")
    print(f"sections={len(rows)} nodes={sum(r[2] for r in rows)} tasks={sum(r[3] for r in rows)} warnings={warn_total} dropped-tasks={dropped} rejected-by-verifier={rejected} sections-without-tasks={missing}")
    sys.exit(1 if warn_total else 0)

if __name__ == "__main__": main(sys.argv[1])
