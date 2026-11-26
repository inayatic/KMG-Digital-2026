#!/usr/bin/env python3
"""Рендер ролика: scene_spec.json + озвучка (lines.json, words.json, voiceover.wav) -> out/video/<id>/<id>.mp4.
Использование: render.py <passport_dir> <audio_dir> <out_dir> [--workers 4] [--fps N] [--hold 1.5] [--keep-frames] [--frames-only-at T]
Время кадров берётся из фактической озвучки: время кадров сцены (scene_spec, расчётное) переводится кусочно-линейно по якорям
«начало реплики в спецификации -> начало реплики в озвучке»; пауза предсказания якорится на вставленную тишину.
Звук нормируется до -16 LUFS (loudnorm, два прохода). Кадры: tools/video/scene.js (Canvas, детерминированная функция времени)."""
import difflib, json, re, shutil, subprocess, sys, unicodedata
from pathlib import Path
HERE = Path(__file__).resolve().parent


def norm_tokens(t):
    t = unicodedata.normalize("NFC", t).replace("́", "").lower().replace("ё", "е")
    return re.findall(r"[а-яa-z0-9]+", t)


def arg(name, d, cast=float):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else d


def build_map(spec_lines, act_lines, pauses, spec_total, act_total):
    anchors = [(0.0, 0.0)]
    for k, (sl, al) in enumerate(zip(spec_lines, act_lines)):
        prev_gap = k > 0 and sl["t0"] - spec_lines[k - 1]["t1"] >= 1.0
        pz = None
        if prev_gap:
            for p in pauses:
                if abs(p["t0"] - act_lines[k - 1]["t1"]) < 1.0 and abs(p["t1"] - al["t0"]) < 1.0: pz = p
        if pz:
            anchors.append((spec_lines[k - 1]["t1"], pz["t0"])); anchors.append((sl["t0"], pz["t1"]))
        else:
            anchors.append((sl["t0"], max(0.0, al["t0"] - 0.05)))
    anchors.append((spec_total, act_total))
    clean = [anchors[0]]
    for a in anchors[1:]:
        if a[0] > clean[-1][0] and a[1] > clean[-1][1]: clean.append(a)
    def f(t):
        for (s0, a0), (s1, a1) in zip(clean, clean[1:]):
            if t <= s1: return a0 + (t - s0) / (s1 - s0) * (a1 - a0)
        return clean[-1][1]
    return f


def sub_chunks(lines_text, lines_t, words, maxw=6):
    """слова из текста сценария со временем из распознавания; чанки по <=maxw слов"""
    hyp_tok = []; owner = []
    for k, w in enumerate(words):
        for tk in norm_tokens(w["text"]): hyp_tok.append(tk); owner.append(k)
    out = []
    for txt, (lt0, lt1) in zip(lines_text, lines_t):
        rw = txt.replace("́", "").split()
        ref_tok, rown = [], []
        for i, w in enumerate(rw):
            for tk in norm_tokens(w): ref_tok.append(tk); rown.append(i)
        # окно распознанных слов внутри реплики
        idx = [i for i, k in enumerate(owner) if words[k]["start"] >= lt0 - 0.05 and words[k]["end"] <= lt1 + 0.05]
        sub_h = [hyp_tok[i] for i in idx]
        sm = difflib.SequenceMatcher(None, ref_tok, sub_h, autojunk=False)
        t0 = [None] * len(rw); t1 = [None] * len(rw)
        for a, b, n in sm.get_matching_blocks():
            for q in range(n):
                wi = rown[a + q]; hw = words[owner[idx[b + q]]]
                if t0[wi] is None: t0[wi] = hw["start"]
                t1[wi] = hw["end"]
        # интерполяция пропусков
        known = [i for i, v in enumerate(t0) if v is not None]
        for i in range(len(rw)):
            if t0[i] is None:
                lo = max([j for j in known if j < i], default=None); hi = min([j for j in known if j > i], default=None)
                a = t1[lo] if lo is not None else lt0; b = t0[hi] if hi is not None else lt1
                nlo = lo if lo is not None else -1; nhi = hi if hi is not None else len(rw)
                frac = (i - nlo) / (nhi - nlo); t0[i] = a + (b - a) * (frac - 0.5 / (nhi - nlo)); t1[i] = t0[i] + 0.2
        ws = [{"t": rw[i], "t0": round(t0[i], 3), "t1": round(max(t1[i], t0[i] + 0.05), 3)} for i in range(len(rw))]
        # чанки: разрыв по знакам препинания, если слов > maxw
        chunks, cur = [], []
        for w in ws:
            cur.append(w)
            if len(cur) >= maxw or (re.search(r"[,;:.?!—]$", w["t"]) and len(cur) >= 3): chunks.append(cur); cur = []
        if cur:
            if chunks and len(cur) < 3: chunks[-1] += cur
            else: chunks.append(cur)
        for c in chunks: out.append({"t0": c[0]["t0"], "t1": c[-1]["t1"] + 0.1, "words": c})
    for a, b in zip(out, out[1:]):
        if a["t1"] > b["t0"]: a["t1"] = b["t0"]
    return out


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode: print(r.stderr[-1500:]); sys.exit(r.returncode)
    return r


def main():
    pdir, adir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    spec = json.load(open(pdir / "scene_spec.json", encoding="utf-8"))
    ld = json.load(open(adir / "lines.json", encoding="utf-8")); act = ld["lines"]
    words = json.load(open(adir / "words.json", encoding="utf-8"))
    vid = spec["video_id"]; W, H = spec["canvas"]["width"], spec["canvas"]["height"]; fps = int(arg("--fps", spec["canvas"].get("fps", 30)))
    hold = arg("--hold", 1.5); total = ld["audio_seconds"] + hold
    sl = spec["voiceover"]["lines"]
    if len(sl) != len(act): print(f"ERR: реплик в scene_spec {len(sl)} != в озвучке {len(act)}"); sys.exit(2)
    mp = build_map(sl, act, ld.get("pauses", []), spec["canvas"]["duration_s"], total)
    frames = []
    for f in spec["frames"]:
        frames.append({**f, "t0": round(mp(f["t"]), 3), "t1": round(mp(f["t_end"]), 3)})
    frames[0]["t0"] = 0.0; frames[-1]["t1"] = round(total, 3)
    for a, b in zip(frames, frames[1:]): b["t0"] = a["t1"]
    texts = [l["text"] for l in act]
    subs = sub_chunks(texts, [(l["t0"], l["t1"]) for l in act], words)
    TL = {"video_id": vid, "canvas": {"width": W, "height": H}, "fps": fps, "duration": round(total, 3), "colors": spec["colors"],
          "safe_zone_px": spec.get("safe_zone_px"), "frames": frames, "subs": subs}
    json.dump(TL, open(out / "timeline.json", "w"), ensure_ascii=False, indent=1)
    model = "-"
    sm = (spec.get("state_model") or {}).get("name")
    if sm:
        mscript = HERE / "models" / f"{sm}.py"
        if mscript.exists():
            mj = out / "model.json"
            args = [sys.executable, str(mscript), str(mj)]
            seed = ((spec["state_model"].get("parameters") or {}).get("random_seed"))
            if seed is not None: args += ["--seed", str(seed)]
            run(args); model = str(mj)
        elif any(f.get("view_type") == "rock_grid" or f.get("params", {}).get("points") == "model_R" for f in spec["frames"]):
            print(f"ПРЕДУПРЕЖДЕНИЕ: нет модели {sm} в tools/video/models/ (виды с моделью не нарисуются)")
    fr = out / "_frames"; shutil.rmtree(fr, ignore_errors=True)
    if "--preview" in sys.argv:
        env = {**__import__("os").environ, "AT": sys.argv[sys.argv.index("--preview") + 1]}
        r = subprocess.run(["node", str(HERE / "render_frames.js"), str(out / "timeline.json"), model, str(out / "_preview"), "1"], capture_output=True, text=True, env=env)
        print(r.stdout, r.stderr[-800:]); return
    r = subprocess.run(["node", str(HERE / "render_frames.js"), str(out / "timeline.json"), model, str(fr), str(int(arg("--workers", 4)))], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip()[-800:])
    if r.returncode: sys.exit(r.returncode)
    # звук: -16 LUFS, два прохода
    wav = adir / "voiceover.wav"
    m = run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    st = json.loads(m[m.rindex("{"):])
    flt = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={st['input_i']}:measured_TP={st['input_tp']}:measured_LRA={st['input_lra']}:"
           f"measured_thresh={st['input_thresh']}:offset={st['target_offset']}:linear=true,apad=whole_dur={total}")
    mp4 = out / f"{vid}.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-framerate", str(fps), "-i", str(fr / "f%05d.png"), "-i", str(wav), "-af", flt, "-t", str(total),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", str(mp4)])
    if "--keep-frames" not in sys.argv: shutil.rmtree(fr, ignore_errors=True)
    print("OK", mp4, f"{total:.1f}s")


if __name__ == "__main__":
    main()
