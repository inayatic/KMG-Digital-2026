#!/usr/bin/env python3
"""update_passport.py <passport_dir> <video_dir> — переносит в passport.json фактические данные после озвучки, рендера и проверок:
времена реплик и кадров (timeline.json), audio_check (озвучка, громкость, WER, рассинхрон), путь к mp4, длительность."""
import json, sys
from pathlib import Path
pd, vd = Path(sys.argv[1]), Path(sys.argv[2])
P = json.load(open(pd / "passport.json", encoding="utf-8")); TL = json.load(open(vd / "timeline.json", encoding="utf-8"))
A = json.load(open(vd / "audio" / "check.json", encoding="utf-8")); LN = json.load(open(vd / "audio" / "lines.json", encoding="utf-8"))
CK = json.load(open(vd / "checks.json", encoding="utf-8")) if (vd / "checks.json").exists() else {}
lines = LN["lines"]
if len(lines) == len(P["script"]):
    for s, l in zip(P["script"], lines):
        s["t_start"], s["t_end"] = l["t0"], l["t1"]
P["frames"] = [{"t": f["t0"], "class": f["class"], "label": f["label"]} for f in TL["frames"]]
P["node_card"]["duration_s"] = TL["duration"]
speech = sum(l["t1"] - l["t0"] for l in lines)
ac = P.get("audio_check", {})
ac.update({"words": A["words_ref"], "speech_seconds": round(speech, 1), "duration_s": TL["duration"], "wpm_total": round(A["words_ref"] / TL["duration"] * 60),
           "tts": {"service": "ElevenLabs", "model": A["model"], "voice": A["voice"], "speed": A.get("speed"), "stress_marks_sent": A["stress_marks_sent"]},
           "stress_marks_note": "знаки ударения в voiceover.txt оставлены для чтения человеком; в синтез не отправлялись (по WER различия нет, на слух не проверено)",
           "wer_tts_vs_text": A["wer"]})
if CK:
    ac.update({"loudness_lufs": CK["loudness_lufs"], "true_peak_dbfs": CK["true_peak_dbfs"], "wer_final_track": CK["wer"], "sync_max_s": CK["sync_max_s"], "checks_pass": CK["pass"]})
if lines and P["script"]: ac["pause_before_answer_s"] = LN["pauses"][0]["t1"] - LN["pauses"][0]["t0"] if LN.get("pauses") else None
P["audio_check"] = ac
P["video_file"] = str(vd / f"{P['video_id']}.mp4")
json.dump(P, open(pd / "passport.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("passport updated:", P["video_file"], TL["duration"])
