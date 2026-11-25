#!/usr/bin/env python3
"""Видеоконвейер: узел слоя -> паспорт -> сценарий -> верификатор -> озвучка -> кадры -> mp4 -> проверки.
    python3 tools/video/pipeline.py <chapter> <node_id> [--format short|long] [--max-rounds 3] [--force]
Каталоги: passports/<video_id>/ (паспорт и сценарий), out/video/<video_id>/ (озвучка, кадры, mp4, checks.json).
video_id = <node_id c '.'->'-'>-<format>. Стадии с готовым результатом пропускаются (--force или FORCE=1 пересчитывает всё).
LLM-стадии: claude -p (агенты scenario-writer и verifier), расход пишется в metrics/metrics.csv (стадия video, video_seconds).
Озвучка: ElevenLabs (наружу уходит только текст озвучки); ключ не нужен (прокси)."""
import json, os, re, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import stage  # noqa: E402  (llm(), metric())

FORCE = "--force" in sys.argv or os.environ.get("FORCE") == "1"
LIM = {"short": (40, 75), "long": (90, 180)}
HOLD = 1.5


def arg(n, d):
    return sys.argv[sys.argv.index(n) + 1] if n in sys.argv else d


def run(cmd, **kw):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, **kw)
    sys.stdout.write(r.stdout[-1500:]); sys.stderr.write(r.stderr[-1500:])
    return r.returncode


def llm(ch, node, agent, prompt, extra):
    return stage.llm(ch, node, agent, str((Path(__file__).parent / "prompts" / prompt).resolve()), "video", extra)


def newer(a, *bs):
    return a.exists() and all(a.stat().st_mtime >= b.stat().st_mtime for b in bs if b.exists())


def verdict(report):
    m = re.search(r"Итого:\s*критических\s+(\d+),\s*существенных\s+(\d+),\s*незначительных\s+(\d+)", report.read_text(encoding="utf-8"))
    return tuple(map(int, m.groups())) if m else None


def main():
    ch, node = sys.argv[1], sys.argv[2]; fmt = arg("--format", "short"); rounds = int(arg("--max-rounds", 3))
    vid = node.replace(".", "-") + "-" + fmt
    pd, vd = ROOT / "passports" / vid, ROOT / "out" / "video" / vid; pd.mkdir(parents=True, exist_ok=True); vd.mkdir(parents=True, exist_ok=True)
    tin = tout = 0; usd = 0.0; t0 = time.time()
    def acc(r):
        nonlocal tin, tout, usd; tin += r[0]; tout += r[1]; usd += r[2]
    sub = f"NODE={node}; FORMAT={fmt}; VIDEO_ID={vid}; PASSPORT_DIR=passports/{vid}\n"
    files = [pd / n for n in ("passport.json", "voiceover.txt", "scene_spec.json")]
    # 1. сценарий
    if FORCE or not all(f.exists() for f in files):
        print("[1/6] scenario-writer …"); acc(llm(ch, node, "scenario-writer", "scenario.md", sub))
        if not all(f.exists() for f in files): sys.exit("ERR: сценарист не создал passport.json, voiceover.txt, scene_spec.json")
    else: print("[1/6] сценарий готов, пропуск")
    # 2. верификатор (до 0 критических и 0 существенных)
    ok = False
    for n in range(1, rounds + 1):
        rep = pd / f"verify-v{n}.md"
        if rep.exists() and not FORCE and newer(rep, *files):
            v = verdict(rep)
        else:
            print(f"[2/6] verifier, круг {n} …")
            acc(llm(ch, node, "verifier", "verify_video.md", sub + f"ROUND={n}; REPORT=passports/{vid}/{rep.name}\n"))
            v = verdict(rep) if rep.exists() else None
        if v is None: sys.exit(f"ERR: нет строки «Итого:» в {rep}")
        print(f"      круг {n}: критических {v[0]}, существенных {v[1]}, незначительных {v[2]}")
        if v[0] == 0 and v[1] == 0: ok = True; break
        if n == rounds: break
        print(f"      исправление по {rep.name} …")
        acc(llm(ch, node, "scenario-writer", "fix_video.md", sub + f"ROUND={n}; REPORT=passports/{vid}/{rep.name}\n"))
    if not ok: sys.exit("ERR: верификатор не дал 0 критических и 0 существенных; рендер не запускается (см. verify-v*.md)")
    # 3. озвучка (скорость подбирается под длительность формата)
    lo, hi = LIM[fmt]; audio = vd / "audio"; spec = json.load(open(pd / "scene_spec.json", encoding="utf-8"))
    cj = audio / "check.json"
    tts = [sys.executable, "tools/tts_eleven.py", str(pd / "voiceover.txt"), str(audio)]
    if FORCE or not cj.exists() or not newer(cj, pd / "voiceover.txt"):
        print("[3/6] озвучка ElevenLabs …"); speed = 1.0
        if run(tts + ["--speed", str(speed), "--force"]): sys.exit("ERR: озвучка")
        total = json.load(open(cj))["audio_seconds"] + HOLD
        if total > hi:
            speed = min(1.2, round(total / (hi - 2.5) + 0.005, 2)); print(f"      {total:.1f} с > {hi} с: повтор со скоростью {speed}")
            if run(tts + ["--speed", str(speed), "--force"]): sys.exit("ERR: озвучка")
        total = json.load(open(cj))["audio_seconds"] + HOLD
        if not lo <= total <= hi: print(f"ПРЕДУПРЕЖДЕНИЕ: длительность {total:.1f} с вне {lo}–{hi} с; нужна правка сценария")
    else: print("[3/6] озвучка готова, пропуск")
    # 4. кадры + сборка
    mp4 = vd / f"{vid}.mp4"
    if FORCE or not newer(mp4, pd / "scene_spec.json", cj):
        print("[4/6] рендер …")
        if run([sys.executable, "tools/video/render.py", str(pd), str(audio), str(vd), "--workers", os.environ.get("JOBS", "6")]): sys.exit("ERR: рендер")
    else: print("[4/6] mp4 готов, пропуск")
    # 5. проверки
    print("[5/6] проверки дорожки …")
    rc = run([sys.executable, "tools/video/check_track.py", str(mp4), str(vd / "timeline.json"), str(pd / "voiceover.txt"), "--kind", fmt])
    # 6. паспорт и метрики
    run([sys.executable, "tools/video/update_passport.py", str(pd), str(vd)])
    secs = json.load(open(vd / "timeline.json"))["duration"]
    stage.metric(ch, "video", 1, tin, tout, usd, round(secs, 1))
    print(f"[6/6] готово: {mp4} ({secs:.1f} с), LLM ${usd:.2f}, {time.time() - t0:.0f} с на этом запуске; проверки дорожки: {'пройдены' if rc == 0 else 'НЕ ПРОЙДЕНЫ (см. checks.json)'}")
    sys.exit(0 if rc == 0 else 6)


if __name__ == "__main__":
    main()
