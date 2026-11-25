#!/usr/bin/env python3
"""Таймлайн ролика по реальной озвучке: timeline.py <passport_dir> <audio_dir> <out_dir>
Строки voiceover.txt ↔ строки scene_spec.voiceover.lines (по порядку); границы строк берутся из words.json (Scribe).
Пауза предсказания: если в scene_spec между строками есть разрыв (t1 одной < t0 следующей), вставляется тишина той же длины.
Кадры, привязанные к строке, делят её время пропорционально длительностям в спецификации.
Пишет <out>/audio.wav (−16 LUFS), <out>/timeline.json (кадры, субтитры с временем, итоговая длительность)."""
import json, re, subprocess, sys, unicodedata
from pathlib import Path


def norm(t):
    t = unicodedata.normalize("NFC", t).replace("́", "").lower().replace("ё", "е")
    return re.findall(r"[а-яa-z0-9]+", t)


def main():
    pdir, adir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
    spec = json.load(open(pdir / "scene_spec.json"))
    lines_txt = [l.strip() for l in (pdir / "voiceover.txt").read_text().splitlines() if l.strip()]
    vl = spec["voiceover"]["lines"]; assert len(vl) == len(lines_txt), (len(vl), len(lines_txt))
    words = json.load(open(adir / "words.json"))
    # конец каждой строки: первое слово распознавания, совпадающее с последним словом строки, после предыдущей границы
    k = 0; seg = []
    for li, txt in enumerate(lines_txt):
        last = norm(txt)[-1]; start = words[k]["start"]
        while k < len(words) and last not in norm(words[k]["text"]): k += 1
        assert k < len(words), f"не найден конец строки {li + 1}: {last}"
        seg.append([start, words[k]["end"]]); k += 1
    # тишину между строками отдаём предыдущей строке (паузы речи), кроме явной паузы из спецификации
    total_src = float(json.load(open(adir / "check.json"))["audio_seconds"])
    bounds = [0.0] + [(seg[i][1] + seg[i + 1][0]) / 2 for i in range(len(seg) - 1)] + [total_src]
    gaps = [max(0.0, vl[i + 1]["t0"] - vl[i]["t1"]) for i in range(len(vl) - 1)] + [0.0]
    # собрать аудио: куски [bounds[i], bounds[i+1]] + тишина gaps[i]
    parts, t, lt = [], 0.0, []
    filt = []
    for i in range(len(vl)):
        a, b = bounds[i], bounds[i + 1]
        filt.append(f"[0:a]atrim={a:.3f}:{b:.3f},asetpts=PTS-STARTPTS[s{i}]")
        parts.append(f"[s{i}]")
        lt.append({"id": vl[i]["id"], "t0": round(t, 3), "t1": round(t + (b - a), 3), "offset": round(t - a, 3)})
        t += b - a
        if gaps[i] > 0:
            filt.append(f"anullsrc=r=44100:cl=mono,atrim=0:{gaps[i]:.3f}[g{i}]"); parts.append(f"[g{i}]")
            lt[-1]["pause_after"] = round(gaps[i], 3); t += gaps[i]
    tail = 2.5; filt.append(f"anullsrc=r=44100:cl=mono,atrim=0:{tail}[tail]"); parts.append("[tail]"); total = t + tail
    filt.append("".join(parts) + f"concat=n={len(parts)}:v=0:a=1,aformat=channel_layouts=mono[cat]")
    raw = out / "audio_raw.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(adir / "voiceover.mp3"), "-filter_complex", ";".join(filt), "-map", "[cat]", str(raw)], check=True)
    # двухпроходная нормализация громкости до −16 LUFS
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"], capture_output=True, text=True)
    m = json.loads(r.stderr[r.stderr.rindex("{"):])
    af = (f"loudnorm=I=-16:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true,aresample=44100")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", af, "-ar", "44100", str(out / "audio.wav")], check=True)
    raw.unlink()
    # кадры: каждая строка спецификации владеет кадрами, чей t попадает в [t0, следующий t0)
    frames = spec["frames"]; ft = []
    starts = [l["t0"] for l in vl] + [spec["canvas"]["duration_s"]]
    for i, l in enumerate(vl):
        own = [f for f in frames if starts[i] <= f["t"] < starts[i + 1]]
        s0, s1 = starts[i], starts[i + 1]; n0, n1 = lt[i]["t0"], (lt[i + 1]["t0"] if i + 1 < len(lt) else total)
        for f in own:
            g = dict(f); g["t"] = round(n0 + (f["t"] - s0) / (s1 - s0) * (n1 - n0), 3)
            g["t_end"] = round(n0 + (min(f["t_end"], s1) - s0) / (s1 - s0) * (n1 - n0), 3); g["line"] = l["id"]; ft.append(g)
    assert len(ft) == len(frames), "кадр без строки"
    for a, b in zip(ft, ft[1:]): b["t"] = a["t_end"]
    ft[-1]["t_end"] = round(total, 3)
    # субтитры: слова строки группами ≤ 7 слов (≤ 2 строк на экране), время по словам распознавания
    subs = []; k = 0
    for i, txt in enumerate(lines_txt):
        toks = txt.replace("́", "").split(); a, b = seg[i]
        ws = [w for w in words if a - 0.01 <= w["start"] <= b + 0.01]
        groups, cur = [], []
        for ti, tok in enumerate(toks):  # ≤ 2 строк по ~24 знака; рвём после знака препинания, если фраза уже длинная
            cur.append(tok); ln = len(" ".join(cur)); rest = len(" ".join(toks[ti + 1:]))
            if rest and (ln >= 44 or (ln >= 22 and tok[-1] in ",;:—" and rest >= 12)): groups.append(cur); cur = []
        if cur: groups.append(cur)
        if len(groups) > 1 and len(" ".join(groups[-1])) < 12: tail_g = groups.pop(); groups[-1] += tail_g
        n_heard = max(1, len(ws)); pos = 0
        for gi, g in enumerate(groups):
            w0 = ws[min(int(pos / len(toks) * n_heard), n_heard - 1)]; pos += len(g)
            w1 = ws[min(int(pos / len(toks) * n_heard) - 1, n_heard - 1)]
            subs.append({"t0": round(w0["start"] + lt[i]["offset"], 3), "t1": round(w1["end"] + lt[i]["offset"], 3), "text": " ".join(g)})
    for a, b in zip(subs, subs[1:]):
        if b["t0"] - a["t1"] < 0.6: a["t1"] = b["t0"]  # без мигания между соседними фразами
    json.dump({"duration": round(total, 3), "fps": spec["canvas"]["fps"], "lines": lt, "frames": ft, "subtitles": subs,
               "loudness_target_lufs": -16}, open(out / "timeline.json", "w"), ensure_ascii=False, indent=1)
    print("длительность", round(total, 2), "с; кадров", len(ft), "; субтитров", len(subs), "; пауза предсказания", [l.get("pause_after") for l in lt if l.get("pause_after")])


if __name__ == "__main__":
    main()
