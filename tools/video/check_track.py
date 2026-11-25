#!/usr/bin/env python3
"""Проверка готового ролика: check_track.py <video.mp4> <timeline.json> <voiceover.txt> [--out checks.json] [--kind short|long]
1) громкость (ffmpeg ebur128, цель -16 LUFS ±1), пик; 2) длительность видео и дорожки, разрешение; 3) распознавание ДОРОЖКИ ГОТОВОГО ФАЙЛА (Scribe):
WER к тексту озвучки (<=10%); 4) рассинхрон: сдвиг начала каждого слова, распознанного в файле, от времени этого слова в субтитрах (<=0,5 с).
Код возврата 1, если порог нарушен."""
import difflib, json, re, subprocess, sys, tempfile, unicodedata
from pathlib import Path


def nt(t):
    t = unicodedata.normalize("NFC", t).replace("́", "").lower().replace("ё", "е")
    return re.findall(r"[а-яa-z0-9]+", t)


def wer(ref, hyp):
    d = list(range(len(hyp) + 1))
    for i in range(1, len(ref) + 1):
        p, d[0] = d[0], i
        for j in range(1, len(hyp) + 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (ref[i - 1] != hyp[j - 1]))
    return d[-1] / max(1, len(ref))


def main():
    mp4, tlp, vo = sys.argv[1], sys.argv[2], sys.argv[3]
    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path(mp4).with_name("checks.json")
    TL = json.load(open(tlp, encoding="utf-8"))
    pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,duration,r_frame_rate", "-show_entries", "format=duration", "-of", "json", mp4], capture_output=True, text=True).stdout)
    v = [s for s in pr["streams"] if s["codec_type"] == "video"][0]; a = [s for s in pr["streams"] if s["codec_type"] == "audio"][0]
    e = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mp4, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    summ = e[e.rindex("Summary:"):]
    lufs = float(re.search(r"I:\s+(-?[\d.]+) LUFS", summ).group(1)); tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ).group(1))
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.mp3"
        subprocess.run(["ffmpeg", "-y", "-i", mp4, "-vn", "-ac", "1", "-b:a", "96k", str(wav)], capture_output=True, check=True)
        raw = subprocess.run(["curl", "-s", "-m", "240", "-X", "POST", "https://api.elevenlabs.io/v1/speech-to-text", "-F", "model_id=scribe_v1", "-F", "language_code=rus", "-F", f"file=@{wav}"], capture_output=True).stdout
    j = json.loads(raw)
    if "words" not in j: print("STT error", raw[:300]); sys.exit(3)
    hw = [w for w in j["words"] if w.get("type") == "word"]
    ref = nt(" ".join(l for l in Path(vo).read_text(encoding="utf-8").splitlines() if not l.strip().startswith("[пауза")))
    hyp = nt(" ".join(w["text"] for w in hw)); W = wer(ref, hyp)
    # рассинхрон со словами субтитров
    sw = [(tk, w["t0"]) for c in TL["subs"] for w in c["words"] for tk in nt(w["t"])]
    hk = [(tk, w["start"]) for w in hw for tk in nt(w["text"])]
    sm = difflib.SequenceMatcher(None, [x[0] for x in sw], [x[0] for x in hk], autojunk=False)
    dl = [abs(sw[a + q][1] - hk[b + q][1]) for a, b, n in sm.get_matching_blocks() for q in range(n)]
    rep = {"video": {"width": v["width"], "height": v["height"], "fps": v["r_frame_rate"], "duration_s": round(float(pr["format"]["duration"]), 2), "audio_duration_s": round(float(a.get("duration", 0)), 2)},
           "loudness_lufs": lufs, "true_peak_dbfs": tp, "wer": round(W, 4), "words_ref": len(ref), "words_heard": len(hyp), "heard_text": j.get("text"),
           "sync_matched_words": len(dl), "sync_max_s": round(max(dl), 3) if dl else None, "sync_mean_s": round(sum(dl) / len(dl), 3) if dl else None}
    rep["pass"] = {"loudness_-16±1": abs(lufs + 16) <= 1.0, "wer<=0.10": W <= 0.10, "sync<=0.5s": bool(dl) and max(dl) <= 0.5 and len(dl) >= 0.8 * len(ref),
                   "duration_ok": (40 <= rep["video"]["duration_s"] <= 75) if "--kind" not in sys.argv or sys.argv[sys.argv.index("--kind") + 1] == "short" else (90 <= rep["video"]["duration_s"] <= 180)}
    json.dump(rep, open(out, "w"), ensure_ascii=False, indent=1)
    print({k: v for k, v in rep.items() if k != "heard_text"})
    sys.exit(0 if all(rep["pass"].values()) else 1)


if __name__ == "__main__":
    main()
