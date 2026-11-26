#!/usr/bin/env python3
"""Озвучка ElevenLabs и проверка распознаванием.
Использование: tts_eleven.py <voiceover.txt> <out_dir> [--voice ID] [--keep-stress] [--speed 0.8..1.2] [--force]
Ключ API не читается и не передаётся: заголовок xi-api-key подставляет прокси окружения. Наружу уходит только текст озвучки.
Формат voiceover.txt: одна реплика на строку; строка вида «[пауза 2.0]» вставляет тишину нужной длины (с).
Знаки ударения U+0301 по умолчанию убираются (--keep-stress оставляет).
Фразы между паузами озвучиваются одним запросом (связная интонация); сегменты склеиваются с тишиной.
Пишет в <out>: voiceover.wav (склейка, 44,1 кГц моно), voiceover.mp3, words.json (слова с глобальным временем, Scribe),
lines.json ({lines: начало и конец каждой реплики, pauses: вставленные паузы}), check.json (WER, длительность). Если voiceover.mp3 и words.json уже есть для
того же текста (хеш в check.json) — запросы пропускаются."""
import difflib, hashlib, json, re, subprocess, sys, unicodedata
from pathlib import Path

VOICE = "Xb7hH8MSUJpSbSDYk0k2"  # Alice, Clear, Engaging Educator
MODEL = "eleven_multilingual_v2"
API = "https://api.elevenlabs.io"
PAUSE = re.compile(r"^\[пауза\s+([\d.,]+)\]$", re.I)


def curl(args):
    return subprocess.run(["curl", "-s", "-m", "240", *args], capture_output=True).stdout


def norm_words(t):
    t = unicodedata.normalize("NFC", t).replace("́", "").lower().replace("ё", "е")
    return re.findall(r"[а-яa-z0-9]+", t)


def wer(ref, hyp):
    d = [[0] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    for i in range(len(ref) + 1): d[i][0] = i
    for j in range(len(hyp) + 1): d[0][j] = j
    for i in range(1, len(ref) + 1):
        for j in range(1, len(hyp) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (ref[i - 1] != hyp[j - 1]))
    return d[-1][-1] / max(1, len(ref))


def run(*a):
    subprocess.run(list(a), check=True, capture_output=True)


def stt(path):
    raw = curl(["-X", "POST", f"{API}/v1/speech-to-text", "-F", "model_id=scribe_v1", "-F", "language_code=rus", "-F", f"file=@{path}"])
    j = json.loads(raw)
    if "words" not in j:
        print("STT error:", raw[:300]); sys.exit(3)
    return j


def parse(text):
    """-> список элементов ('line', idx, text) и ('pause', sec)"""
    items, n = [], 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln: continue
        m = PAUSE.match(ln)
        if m: items.append(("pause", float(m.group(1).replace(",", "."))))
        else: items.append(("line", n, ln)); n += 1
    return items


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    voice = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else VOICE
    keep = "--keep-stress" in sys.argv
    speed = float(sys.argv[sys.argv.index("--speed") + 1]) if "--speed" in sys.argv else 1.0
    raw_text = src.read_text()
    text = raw_text if keep else raw_text.replace("́", "")
    key = hashlib.sha256((text + voice + MODEL + str(speed)).encode()).hexdigest()
    chk_path = out / "check.json"
    if "--force" not in sys.argv and chk_path.exists() and (out / "words.json").exists() and (out / "voiceover.wav").exists():
        old = json.loads(chk_path.read_text())
        if old.get("input_hash") == key:
            print("озвучка уже есть для этого текста, пропуск:", {k: old[k] for k in ("wer", "audio_seconds")}); return
    items = parse(text)
    # сегменты: подряд идущие реплики
    segs, cur = [], []
    for it in items:
        if it[0] == "line": cur.append(it)
        else:
            if cur: segs.append(("speech", cur)); cur = []
            segs.append(("pause", it[1]))
    if cur: segs.append(("speech", cur))
    parts, words_all, lines_ref, pauses, t, sidx = [], [], [], [], 0.0, 0
    for kind, val in segs:
        if kind == "pause":
            f = out / f"_sil{sidx}.wav"
            run("ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", str(val), str(f)); sidx += 1
            pauses.append({"t0": round(t, 3), "t1": round(t + val, 3)}); parts.append(f); t += val; continue
        body_text = " ".join(x[2] for x in val)
        body = json.dumps({"text": body_text, "model_id": MODEL, "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True, "speed": speed}}, ensure_ascii=False)
        mp3 = out / f"_seg{sidx}.mp3"
        curl(["-X", "POST", f"{API}/v1/text-to-speech/{voice}?output_format=mp3_44100_128", "-H", "Content-Type: application/json", "-d", body, "-o", str(mp3)])
        if not mp3.exists() or mp3.stat().st_size < 5000:
            print("TTS error:", mp3.read_bytes()[:300] if mp3.exists() else b""); sys.exit(2)
        j = stt(mp3)
        wav = out / f"_seg{sidx}.wav"; sidx += 1
        run("ffmpeg", "-y", "-i", str(mp3), "-ar", "44100", "-ac", "1", str(wav))
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout)
        seg_words = [dict(w, start=w["start"] + t, end=w["end"] + t) for w in j["words"] if w.get("type") == "word"]
        # привязка реплик к словам распознавания
        ref_tok, owner = [], []
        for _, idx, ln in val:
            tk = norm_words(ln); ref_tok += tk; owner += [idx] * len(tk)
        hyp_tok = [norm_words(w["text"]) for w in seg_words]
        hyp_flat = [(k, x) for k, tk in enumerate(hyp_tok) for x in tk]
        sm = difflib.SequenceMatcher(None, ref_tok, [x for _, x in hyp_flat], autojunk=False)
        first, last = {}, {}
        for a, b, n in sm.get_matching_blocks():
            for q in range(n):
                li, wi = owner[a + q], hyp_flat[b + q][0]
                first.setdefault(li, wi); last[li] = max(last.get(li, wi), wi)
        for _, idx, ln in val:
            if idx in first:
                lines_ref.append({"idx": idx, "text": ln.replace("́", ""), "t0": round(seg_words[first[idx]]["start"], 3), "t1": round(seg_words[last[idx]]["end"], 3)})
            else:
                lines_ref.append({"idx": idx, "text": ln.replace("́", ""), "t0": None, "t1": None})
        words_all += seg_words; parts.append(wav); t += dur
    lst = out / "_list.txt"; lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    run("ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-ar", "44100", "-ac", "1", str(out / "voiceover.wav"))
    run("ffmpeg", "-y", "-i", str(out / "voiceover.wav"), "-b:a", "128k", str(out / "voiceover.mp3"))
    for p in list(out.glob("_seg*")) + list(out.glob("_sil*")) + [lst]: p.unlink()
    json.dump(words_all, open(out / "words.json", "w"), ensure_ascii=False, indent=1)
    lines_ref.sort(key=lambda x: x["idx"])
    json.dump({"lines": lines_ref, "pauses": pauses, "audio_seconds": round(t, 3)}, open(out / "lines.json", "w"), ensure_ascii=False, indent=1)
    ref_all = [w for it in items if it[0] == "line" for w in norm_words(it[2])]
    hyp_all = norm_words(" ".join(w["text"] for w in words_all))
    chk = {"input_hash": key, "chars_sent": sum(len(x[2]) for x in items if x[0] == "line"), "words_ref": len(ref_all), "words_heard": len(hyp_all),
           "wer": round(wer(ref_all, hyp_all), 4), "audio_seconds": round(t, 2), "stress_marks_sent": keep, "voice": voice, "model": MODEL, "speed": speed,
           "heard_text": " ".join(w["text"] for w in words_all)}
    json.dump(chk, open(chk_path, "w"), ensure_ascii=False, indent=1)
    print({k: v for k, v in chk.items() if k not in ("heard_text", "input_hash")})


if __name__ == "__main__":
    main()
