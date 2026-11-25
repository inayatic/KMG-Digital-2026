#!/usr/bin/env python3
"""Диспетчер стадий: stage.py <nodes|routing|verify|org|course> <chapter>.
LLM-стадии запускают `claude -p` (агент из .claude/agents + промпт из tools/prompts) по одному вызову на раздел,
параллельно (JOBS, по умолчанию 4). Модель: LLM_MODEL. Токены и деньги пишутся в metrics/metrics.csv.
Раздел пропускается, если его результат уже есть (пересборка только недостающего); FORCE=1 пересчитывает; fix пропускается, если есть fixes*.md."""
import csv, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
MET = ROOT / "metrics/metrics.csv"
HEAD = ["chapter", "stage", "nodes", "llm_tokens_in", "llm_tokens_out", "money_usd", "person_minutes", "mentor_minutes", "video_seconds", "manual_share"]
FORCE = os.environ.get("FORCE") == "1"

def py(*a):
    subprocess.run(["python3", "-I", *map(str, a)], cwd=ROOT, check=True)

def llm(ch, key, agent, prompt, stage):
    """Один вызов агента на раздел. Подстановки CHAPTER/KEY/PREFIX даём строкой перед промптом."""
    text = (ROOT / "tools/prompts" / prompt).read_text()
    head = f"CHAPTER={ch}; KEY={key}; PREFIX={ch[:3]}.{key}\n\n"
    cmd = ["claude", "-p", "--agent", agent, "--output-format", "json", "--permission-mode", "acceptEdits", "--allowedTools", "Read,Write,Edit,Grep,Glob,Bash"]
    if os.environ.get("LLM_MODEL"): cmd += ["--model", os.environ["LLM_MODEL"]]
    r = subprocess.run(cmd, input=head + text, cwd=ROOT, capture_output=True, text=True)
    try: j = json.loads(r.stdout)
    except Exception: sys.exit(f"{stage} {key}: агент не вернул JSON: {r.stderr[:300]}")
    if j.get("is_error"): sys.exit(f"{stage} {key}: {j.get('result','')[:300]}")
    u = j.get("usage", {})
    tin = u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
    return tin, u.get("output_tokens", 0), j.get("total_cost_usd", 0.0)

def per_section(ch, stage, agent, prompt, done, keys=None):
    root = ROOT / "build" / ch
    keys = keys or [s["key"] for s in json.load(open(root / "sections.json"))]
    if keys == ["_all"]: root = root / "x"  # один вызов на всю главу
    todo = [k for k in keys if FORCE or not done(root / "sections" / k)]
    print(f"{stage}: {len(todo)} из {len(keys)} разделов к запуску")
    with ThreadPoolExecutor(int(os.environ.get("JOBS", 4))) as ex:
        res = list(ex.map(lambda k: llm(ch, k, agent, prompt, stage), todo))
    return len(todo), sum(r[0] for r in res), sum(r[1] for r in res), sum(r[2] for r in res)

def metric(ch, stage, nodes, tin, tout, usd):
    new = not MET.exists(); MET.parent.mkdir(exist_ok=True)
    with MET.open("a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(HEAD)
        w.writerow([ch, stage, nodes, tin, tout, round(usd, 4), "", "", "", ""])

def nodes(ch):
    if not (ROOT / "build" / ch / "sections.json").exists(): py("tools/split_sections.py", ch)
    n, tin, tout, usd = per_section(ch, "layer", "layer-extractor", "extract.md", lambda d: (d / "nodes.json").exists())
    py("tools/merge_layer.py", ch)
    cnt = len(json.load(open(ROOT / "build" / ch / "nodes.json")))
    metric(ch, "layer", cnt, tin, tout, usd)

def verify(ch):
    """verify -> fix (один круг; больше кругов: ROUNDS=2 запускает fix_r2 и reverify вручную по промптам)."""
    n, tin, tout, usd = per_section(ch, "verify", "verifier", "verify.md", lambda d: (d / "verify.md").exists())
    n2, tin2, tout2, usd2 = per_section(ch, "fix", "layer-extractor", "fix.md", lambda d: any(d.glob("fixes*.md")))
    py("tools/merge_layer.py", ch)
    metric(ch, "review", "", tin + tin2, tout + tout2, usd + usd2)
    (ROOT / "build" / ch / "verify.md").write_text(f"Сводка: verify по {n} разделам, fix по {n2}; замечания в sections/*/verify.md, правки в fixes.md\n")

def org(ch):
    """слой в формате организаторов: конверсия, enrich (тип трудности, термины, оценки видео), патчи, проверка."""
    py("tools/to_organizer_schema.py", ch)
    n, tin, tout, usd = per_section(ch, "enrich", "layer-extractor", "enrich.md", lambda d: (ROOT / "build" / ch / "org/patches" / (d.name + ".json")).exists())
    py("tools/apply_patches.py", ch); py("tools/check_org.py", ch)
    metric(ch, "routing", "", tin, tout, usd)

def course(ch):
    """задания по разделам (агент, course_tasks.md) -> детерминированная сборка build_course_all.py с проверкой ответов по утверждениям."""
    import re
    keys = [k["key"] for k in json.load(open(ROOT / "build" / ch / "sections.json")) if re.fullmatch(r"s\d\d|ch\w+", k["key"])]
    (ROOT / "build" / ch / "course").mkdir(exist_ok=True)
    prompt, pre = ("course_tasks2.md", "tasks2-") if os.environ.get("TASKS_V") != "1" else ("course_tasks.md", "tasks-")  # v2 по умолчанию
    n, tin, tout, usd = per_section(ch, "course", "course-builder", prompt, lambda d: (d.parent.parent / "course" / f"{pre}{d.name}.json").exists(), keys=keys)
    py("tools/build_course_all.py", ch)
    metric(ch, "course", "", tin, tout, usd)

if __name__ == "__main__":
    st, ch = sys.argv[1:3]
    {"nodes": nodes, "verify": verify, "org": org, "routing": org, "course": course}[st](ch)
