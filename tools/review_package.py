#!/usr/bin/env python3
"""Модуль проверки внешнего пакета одной командой: make review PACKAGE=<путь к package.json> [OUT=<ответ.json>].

Пакет по reference/organizers/02_модуль_проверки/review_package.schema.json (любая глава, любое число целей).
1) копирует пакет, md главы и кадры в рабочий каталог build/review/<package_id>/input (агент видит только его);
2) режет цели на срезы (утверждения; аналогии+фразы+факты сцены; кадры) с контекстом (claim_ref, сцены);
3) параллельно запускает агента verifier (`claude -p`, промпт tools/prompts/review_package.md) на каждый срез;
4) склеивает: одно замечание на цель, только цели пакета, категории/тяжесть из схемы, page_pdf целое и есть в главе;
5) валидирует по review_output.schema.json и пишет ответ.json; токены и деньги — в metrics/metrics.csv через stage.metric.
Ключ (key.json) не копируется и не читается. Переменные: JOBS (4), CLAIMS_PER_SLICE (20), OTHER_PER_SLICE (25),
FRAMES_PER_SLICE (5), LLM_MODEL, FORCE=1 (пересчитать срезы с готовым результатом)."""
import json, math, os, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import stage  # noqa: E402  (metric, формат вызова claude -p)

SCHEMA_DIR = ROOT / "reference/organizers/02_модуль_проверки"
CATS = ["overgeneralization", "sign_flip", "measured_vs_inferred", "lost_condition", "missing_caveat", "wrong_scaling",
        "wrong_mechanism", "outdated_as_current", "analogy_without_limit", "frame_error", "other"]
SEV = ["critical", "significant", "minor"]
FORCE = os.environ.get("FORCE") == "1"


def chunks(xs, size):
    if not xs: return []
    n = math.ceil(len(xs) / size); k = math.ceil(len(xs) / n)
    return [xs[i:i + k] for i in range(0, len(xs), k)]


def pages(md):
    """номер страницы -> текст по меткам <!-- page N -->"""
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"\s*<!--\s*page\s+(\d+)\s*-->", line)
        if m: cur = int(m.group(1)); out.setdefault(cur, ""); continue
        if cur is not None: out[cur] += line + "\n"
    return out


def norm(s): return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", (s or "").lower().replace("ё", "е"))).strip()


def quote_on_page(q, text):
    q, t = norm(q), norm(text)
    if not q: return True
    if q in t: return True
    m = SequenceMatcher(None, t, q, autojunk=False).find_longest_match(0, len(t), 0, len(q))
    return m.size >= 0.6 * len(q)


def prepare(pkg_path, work):
    pkg = json.load(open(pkg_path)); src = pkg_path.parent
    inp = work / "input"; inp.mkdir(parents=True, exist_ok=True)
    chap = src / pkg["chapter_file"]
    if not chap.exists():  # глава может лежать рядом или в chapters/
        cand = list(src.rglob(pkg["chapter_file"])) + list((ROOT / "chapters").rglob(pkg["chapter_file"]))
        if not cand: sys.exit(f"нет файла главы {pkg['chapter_file']} рядом с пакетом")
        chap = cand[0]
    shutil.copy(chap, inp / "chapter.md")
    shutil.copy(pkg_path, inp / "package.json")
    for fr in pkg.get("frames", []):
        f = src / fr["file"]
        if not f.exists(): print(f"внимание: нет кадра {f}"); continue
        dst = inp / "frames" / f.name; dst.parent.mkdir(exist_ok=True); shutil.copy(f, dst)
        fr["file_abs"] = str(dst)
    return pkg, inp / "chapter.md"


def make_slices(pkg, chapter_abs):
    items = pkg["items"]; by_id = {i["id"]: i for i in items}
    scenes = {s["video_id"]: s for s in pkg.get("scenes", [])}
    lines_by_video = {}
    for i in items:
        if i["type"] == "script_line": lines_by_video.setdefault(i.get("video_id"), []).append(i)

    def ctx(targets):
        c, vids = {}, set()
        for t in targets:
            if t.get("claim_ref") in by_id: c[t["claim_ref"]] = by_id[t["claim_ref"]]
            if t.get("type") == "analogy" and t.get("node_id"):
                for i in items:
                    if i["type"] == "claim" and i.get("node_id") == t["node_id"]: c[i["id"]] = i
            if t.get("type") in ("scene_fact", "frame"): vids.add(t.get("video_id"))
        for v in vids:
            for l in lines_by_video.get(v, []):
                c[l["id"]] = l
                if l.get("claim_ref") in by_id: c[l["claim_ref"]] = by_id[l["claim_ref"]]
        tid = {t["id"] for t in targets}
        return {"related_items": [v for k, v in c.items() if k not in tid], "scenes": [scenes[v] for v in vids if v in scenes],
                "all_frames_meta": [{k: f[k] for k in ("id", "t", "label", "shows", "plaque") if k in f} for f in pkg.get("frames", []) if f.get("video_id") in vids]}

    claims = [i for i in items if i["type"] == "claim"]
    other = [i for i in items if i["type"] != "claim"]
    frames = [dict(f, type="frame") for f in pkg.get("frames", [])]
    groups = [("C", chunks(claims, int(os.environ.get("CLAIMS_PER_SLICE", 20)))),
              ("O", chunks(other, int(os.environ.get("OTHER_PER_SLICE", 25)))),
              ("F", chunks(frames, int(os.environ.get("FRAMES_PER_SLICE", 5))))]
    out = []
    for g, parts in groups:
        for n, part in enumerate(parts, 1):
            out.append((f"{g}{n}", {"package_id": pkg["package_id"], "chapter_file": str(chapter_abs), "language": pkg.get("language"),
                                    "categories": CATS, "targets": part, "context": ctx(part)}))
    return out


def run_slice(work, name, sl):
    sdir = work / "slices"; sdir.mkdir(exist_ok=True)
    sp, outp, notes = sdir / f"{name}.json", sdir / f"out-{name}.json", sdir / f"out-{name}-notes.md"
    sp.write_text(json.dumps(sl, ensure_ascii=False, indent=1))
    if not FORCE and outp.exists():
        try: json.load(open(outp)); return name, 0, 0, 0.0, "готово ранее"
        except Exception: pass
    head = f"SLICE={sp}\nWORK={work}\nOUT={outp}\nNOTES={notes}\n\n"
    prompt = (ROOT / "tools/prompts/review_package.md").read_text()
    cmd = ["claude", "-p", "--agent", "verifier", "--output-format", "json", "--permission-mode", "acceptEdits",
           "--allowedTools", "Read,Write,Edit,Grep,Glob,Bash"]
    if os.environ.get("LLM_MODEL"): cmd += ["--model", os.environ["LLM_MODEL"]]
    tin = tout = 0; usd = 0.0; msg = ""
    for attempt in range(2):  # один повтор, если агент не оставил валидный OUT
        r = subprocess.run(cmd, input=head + prompt, cwd=ROOT, capture_output=True, text=True)
        try:
            j = json.loads(r.stdout); u = j.get("usage", {})
            tin += u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            tout += u.get("output_tokens", 0); usd += j.get("total_cost_usd", 0.0) or 0.0
            msg = (j.get("result") or "")[:200].replace("\n", " ")
            if j.get("is_error"): msg = "ошибка агента: " + msg
        except Exception:
            msg = "агент не вернул JSON: " + r.stderr[:200]
        try: json.load(open(outp)); break
        except Exception: print(f"{name}: попытка {attempt + 1} без валидного результата ({msg})")
    return name, tin, tout, usd, msg


def merge(pkg, work, slices, chapter_md):
    pg = pages(chapter_md)
    valid_ids = {i["id"] for i in pkg["items"]} | {f["id"] for f in pkg.get("frames", [])}
    order = {t["id"]: n for n, (_, sl) in enumerate(slices) for t in sl["targets"]}
    remarks, seen, log = [], set(), []
    for name, sl in slices:
        p = work / "slices" / f"out-{name}.json"
        try: data = json.load(open(p))
        except Exception as e: log.append(f"{name}: нет результата ({e})"); continue
        own = {t["id"] for t in sl["targets"]}
        for r in data.get("remarks", data if isinstance(data, list) else []):
            t = str(r.get("target", "")).strip()
            if t not in valid_ids: log.append(f"{name}: отброшено, цели {t!r} нет в пакете"); continue
            if t not in own: log.append(f"{name}: {t} не из своего среза (оставлено)")
            if t in seen: log.append(f"{name}: второе замечание на {t} отброшено"); continue
            cat = r.get("category") if r.get("category") in CATS else "other"
            sev = r.get("severity") if r.get("severity") in SEV else "significant"
            try: page = int(r.get("page_pdf"))
            except Exception: page = None
            if page is not None and pg and page not in pg: log.append(f"{t}: страницы {page} нет в главе")
            if page is None: log.append(f"{t}: нет page_pdf (зачёт наполовину)")
            fix = str(r.get("fix") or "").strip()
            if not fix: log.append(f"{t}: пустой fix (зачёт наполовину)")
            q = r.get("quote") or None
            if q and page in pg and not quote_on_page(q, pg[page]): log.append(f"{t}: цитата не найдена на стр. {page}")
            seen.add(t)
            remarks.append({"target": t, "category": cat, "severity": sev, "problem": str(r.get("problem") or "").strip(),
                            "fix": fix, "page_pdf": page, "quote": q})
    remarks.sort(key=lambda r: order.get(r["target"], 10**6))
    return {"package_id": pkg["package_id"], "remarks": remarks}, log


def main():
    if len(sys.argv) < 2: sys.exit("usage: review_package.py <package.json> [ответ.json]")
    t0 = time.time()
    pkg_path = Path(sys.argv[1]).resolve()
    import jsonschema
    pkg_raw = json.load(open(pkg_path))
    jsonschema.validate(pkg_raw, json.load(open(SCHEMA_DIR / "review_package.schema.json")))
    work = ROOT / "build/review" / pkg_raw["package_id"]
    pkg, chap = prepare(pkg_path, work)
    slices = make_slices(pkg, chap)
    ntar = sum(len(s["targets"]) for _, s in slices)
    print(f"пакет {pkg['package_id']}: целей {ntar}, срезов {len(slices)} ({', '.join(f'{n}:{len(s['targets'])}' for n, s in slices)})")
    with ThreadPoolExecutor(int(os.environ.get("JOBS", 4))) as ex:
        res = list(ex.map(lambda x: run_slice(work, *x), slices))
    for name, _, _, usd, msg in res: print(f"  {name}: ${usd:.2f} {msg[:120]}")
    ans, log = merge(pkg, work, slices, chap.read_text())
    jsonschema.validate(ans, json.load(open(SCHEMA_DIR / "review_output.schema.json")))
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else work / "ответ.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ans, ensure_ascii=False, indent=1))
    (work / "merge-log.md").write_text("\n".join(log) + "\n")
    notes = "\n".join((work / "slices" / f"out-{n}-notes.md").read_text() for n, _ in slices if (work / "slices" / f"out-{n}-notes.md").exists())
    (work / "notes.md").write_text(notes)
    tin, tout, usd = sum(r[1] for r in res), sum(r[2] for r in res), sum(r[3] for r in res)
    if tin or tout: stage.metric(pkg["package_id"], "review_package", ntar, tin, tout, usd)
    print(f"ответ: {out} — замечаний {len(ans['remarks'])} на {ntar} целей; схема ок; ${usd:.2f}; {(time.time() - t0) / 60:.1f} мин")
    for l in log: print("  " + l)


if __name__ == "__main__":
    main()
