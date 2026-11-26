#!/usr/bin/env python3
"""Метрики качества главы для сравнения обучающей главы и двойников (без LLM): review_doubles.py <ch> [<ch> ...]
Считает по build/<ch>/: узлы; замечания стадии verify (sections/*/verify.md: всего, по тяжести, на узел); задания курса
(build/<ch>/course/tasks2-*.json, иначе tasks-*.json) по видам и долю «поиск фразы» (эвристика: ≥80 % значимых основ
верного ответа встречаются в одном утверждении узла — ответ можно найти в тексте, не применяя правило); проблемы покрытия
(tools/check_cov.py --json); деньги и токены по metrics/metrics.csv. Печатает таблицу markdown."""
import csv, glob, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V1 = "--v1" in sys.argv  # задания первой версии (tasks-*.json) вместо tasks2
STOP = set("это этот эта эти как что при или для его она они так также если чем быть было были будет может могут более менее только всегда".split())


def stems(s):
    return {w[:5] for w in re.findall(r"[а-яёa-z0-9]+", (s or "").lower().replace("ё", "е")) if len(w) >= 4 and w not in STOP}


def phrase_lookup(task, node):
    ans = task.get("answer")
    if isinstance(ans, list): ans = " ".join(map(str, ans))
    a = stems(str(ans))
    if len(a) < 2: return False
    return any(len(a & stems(c.get("text", "") + " " + (c.get("quote") or ""))) >= 0.8 * len(a) for c in node.get("claims", []))


def chapter(ch):
    B = ROOT / "build" / ch
    nodes = json.load(open(B / "nodes.json"))
    by = {n["id"]: n for n in nodes}
    sev = Counter(); nrem = 0
    for f in glob.glob(str(B / "sections/*/verify.md")):
        t = open(f).read()
        nrem += len(re.findall(r"(?m)^id:\s*V-", t))
        for m in re.findall(r"(?m)^тяжесть:\s*(\S+)", t): sev[m.strip(".,").lower()[:5]] += 1
    files = (sorted(glob.glob(str(B / "course/tasks2-*.json"))) if not V1 else []) or sorted(glob.glob(str(B / "course/tasks-*.json")))
    kinds = Counter(); n = phr = 0
    pre = f"{ch[:3]}."
    for f in files:
        d = json.load(open(f)); ts = d if isinstance(d, list) else d.get("tasks", [])
        key = re.sub(r"^tasks2?-", "", Path(f).stem)
        for t in ts:
            n += 1; kinds[t.get("kind") or t.get("type")] += 1
            nid = t.get("node", "")
            node = by.get(nid) or next((v for k, v in by.items() if k.startswith(f"{pre}{key}.{nid}")), None)
            if node and phrase_lookup(t, node): phr += 1
    r = subprocess.run(["python3", "-I", str(ROOT / "tools/check_cov.py"), ch, "--json"], cwd=ROOT, capture_output=True, text=True)
    try: cov = json.loads(r.stdout or "{}")
    except Exception: cov = {"?": [r.stdout[-200:]]}
    usd = tin = 0.0
    if (ROOT / "metrics/metrics.csv").exists():
        for row in csv.DictReader(open(ROOT / "metrics/metrics.csv")):
            if row["chapter"] == ch:
                usd += float(row["money_usd"] or 0); tin += float(row["llm_tokens_in"] or 0)
    pages = len(re.findall(r"<!-- page \d+ -->", (B / "clean.md").read_text()))
    return dict(ch=ch, pages=pages, nodes=len(nodes), rem=nrem, crit=sev["крити"], sig=sev["сущес"], minor=sev["незна"],
                per_node=nrem / max(len(nodes), 1), tasks=n, kinds=dict(kinds), phrase=phr / max(n, 1), cov=sum(len(v) for v in cov.values()),
                usd=usd, usd_page=usd / max(pages, 1))


if __name__ == "__main__":
    rows = [chapter(c) for c in sys.argv[1:] if not c.startswith("--")]
    print("| глава | стр. | узлов | замечаний verify (крит/сущ/незн) | замечаний на узел | заданий | виды заданий | «поиск фразы» | проблем покрытия | $ всего (metrics.csv) | $ на стр. |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['ch']} | {r['pages']} | {r['nodes']} | {r['rem']} ({r['crit']}/{r['sig']}/{r['minor']}) | {r['per_node']:.2f} | {r['tasks']} | "
              f"{', '.join(f'{k} {v}' for k, v in r['kinds'].items())} | {r['phrase']:.0%} | {r['cov']} | {r['usd']:.2f} | {r['usd_page']:.3f} |")
