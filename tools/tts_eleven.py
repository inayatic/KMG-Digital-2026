#!/usr/bin/env python3
"""Озвучка ElevenLabs и проверка распознаванием: tts_eleven.py <voiceover.txt> <out_dir> [--voice ID] [--keep-stress]
Ключ API НЕ читается из окружения и не передаётся в запросе: заголовок xi-api-key подставляет прокси окружения.
Наружу уходит только текст озвучки. По умолчанию знаки ударения (U+0301) убираются (--keep-stress оставляет).
Пишет: <out>/voiceover.mp3, <out>/words.json (слова с временем от Scribe), <out>/check.json (расхождение текста и распознавания, WER).
Предложения озвучиваются одним запросом для связной интонации."""
import json, re, subprocess, sys, unicodedata
from pathlib import Path

VOICE = "Xb7hH8MSUJpSbSDYk0k2"  # Alice, Clear, Engaging Educator
MODEL = "eleven_multilingual_v2"
API = "https://api.elevenlabs.io"


def curl(args):
    r = subprocess.run(["curl", "-s", "-m", "180", *args], capture_output=True)
    return r.stdout


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


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    voice = sys.argv[sys.argv.index("--voice") + 1] if "--voice" in sys.argv else VOICE
    text = src.read_text()
    text = text if "--keep-stress" in sys.argv else text.replace("́", "")
    text = re.sub(r"\n+", " ", text.strip())
    body = json.dumps({"text": text, "model_id": MODEL, "voice_settings": {"stability": 0.55, "similarity_boost": 0.75, "style": 0.0, "use_speaker_boost": True}}, ensure_ascii=False)
    mp3 = out / "voiceover.mp3"
    curl(["-X", "POST", f"{API}/v1/text-to-speech/{voice}?output_format=mp3_44100_128", "-H", "Content-Type: application/json", "-d", body, "-o", str(mp3)])
    if mp3.stat().st_size < 5000:
        print("TTS error:", mp3.read_bytes()[:300]); sys.exit(2)
    raw = curl(["-X", "POST", f"{API}/v1/speech-to-text", "-F", "model_id=scribe_v1", "-F", "language_code=rus", "-F", f"file=@{mp3}"])
    j = json.loads(raw)
    if "words" not in j: print("STT error:", raw[:300]); sys.exit(3)
    words = [w for w in j["words"] if w.get("type") == "word"]
    json.dump(words, open(out / "words.json", "w"), ensure_ascii=False, indent=1)
    ref, hyp = norm_words(text), norm_words(" ".join(w["text"] for w in words))
    chk = {"chars_sent": len(text), "words_ref": len(ref), "words_heard": len(hyp), "wer": round(wer(ref, hyp), 4), "audio_seconds": j.get("audio_duration_secs"), "stress_marks_sent": "--keep-stress" in sys.argv, "voice": voice, "model": MODEL, "heard_text": j.get("text")}
    json.dump(chk, open(out / "check.json", "w"), ensure_ascii=False, indent=1)
    print({k: v for k, v in chk.items() if k != "heard_text"})


if __name__ == "__main__":
    main()
