#!/usr/bin/env python3
"""Сводка метрик: summary_metrics.py -> metrics/summary.md. Источники: metrics/metrics.csv (пишет tools/stage.py), metrics/manual_edits.csv (tools/edit-log).
Деньги и токены — по данным вызовов claude -p (list-цены CLI), это оценка стоимости, не счёт. Строки с нулями — стадии, прогнанные без вызовов; если стадия возобновлялась после сбоя, учтён только последний запуск (первые прогоны могли не попасть в metrics.csv), поэтому суммы занижены."""
import csv, collections
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
rows = list(csv.DictReader(open(ROOT / "metrics/metrics.csv"))) if (ROOT / "metrics/metrics.csv").exists() else []
ed = list(csv.DictReader(open(ROOT / "metrics/manual_edits.csv"))) if (ROOT / "metrics/manual_edits.csv").exists() else []
agg = collections.defaultdict(lambda: collections.defaultdict(float)); nodes = {}
for r in rows:
    a = agg[r["chapter"]]; a[r["stage"]] += float(r["money_usd"] or 0); a["tin"] += float(r["llm_tokens_in"] or 0); a["tout"] += float(r["llm_tokens_out"] or 0)
    if r["stage"] == "layer" and r["nodes"]: nodes[r["chapter"]] = int(r["nodes"])
man = collections.Counter()
for e in ed: man[e["chapter"]] += float(e["person_minutes"] or 0)
out = ["# Сводка метрик (оценка, генерируется tools/summary_metrics.py)", "",
       "| Глава | Узлов | слой $ | проверка $ | маршрутизация $ | курс $ | всего $ | $ на узел | ручные мин |", "|---|---|---|---|---|---|---|---|---|"]
for ch, a in sorted(agg.items()):
    tot = sum(a[s] for s in ("layer", "review", "routing", "course")); n = nodes.get(ch)
    out.append(f"| {ch} | {n or ''} | {a['layer']:.2f} | {a['review']:.2f} | {a['routing']:.2f} | {a['course']:.2f} | {tot:.2f} | {tot / n:.3f} |" .replace("| |", "| — |") + f" {man.get(ch, 0):g} |" if n else f"| {ch} |  | {a['layer']:.2f} | {a['review']:.2f} | {a['routing']:.2f} | {a['course']:.2f} | {tot:.2f} | — | {man.get(ch, 0):g} |")
out += ["", "Ручные минуты считаются из metrics/manual_edits.csv. Цель на тестовую главу ≤30 мин. Деньги на минуту видео: см. docs/video.md (роль B).", ""]
(ROOT / "metrics/summary.md").write_text("\n".join(out))
print("\n".join(out))
