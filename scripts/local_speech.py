"""Local original-audio transcription, independent from caption text."""
from pathlib import Path
import json
import wave

import numpy as np


def transcribe_local(wav_path, model_dir, *, language=None, vad=True):
    from faster_whisper import WhisperModel

    with wave.open(str(wav_path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("ASR requires a mono, 16 kHz, PCM16 WAV")
        waveform = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if waveform.size == 0:
        raise ValueError("Audio is empty")
    model = WhisperModel(str(model_dir), device="cpu", compute_type="int8", local_files_only=True)
    segments, info = model.transcribe(waveform, language=language, vad_filter=vad,
                                     word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    rows = []
    for segment in segments:
        if not segment.text.strip():
            continue
        rows.append({
            "start": round(float(segment.start), 3), "end": round(float(segment.end), 3),
            "text": segment.text.strip(), "avg_logprob": float(segment.avg_logprob),
            "no_speech_prob": float(segment.no_speech_prob),
            "words": [{"start": round(float(w.start), 3), "end": round(float(w.end), 3),
                       "word": w.word, "probability": float(w.probability)} for w in (segment.words or [])],
        })
    return {"backend": "local", "model": str(Path(model_dir).resolve()),
            "language": info.language, "language_probability": float(info.language_probability),
            "language_requested": language, "vad_filter": vad, "duration_seconds": len(waveform) / 16000,
            "text": "\n".join(r["text"] for r in rows), "segments": rows,
            "limitations": ["Automatic ASR, not an independently listened-to verbatim transcript.",
                            "Words, proper names, and timestamps may be inaccurate; no speech does not establish silence."]}


def export_speech(result, out_dir, stem="speech"):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, text_path, srt_path = [out_dir / f"{stem}.{ext}" for ext in ("json", "txt", "srt")]
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    text_path.write_text(result["text"] + "\n", encoding="utf-8")

    def stamp(value):
        millis = max(0, round(float(value) * 1000))
        seconds, ms = divmod(millis, 1000)
        minutes, sec = divmod(seconds, 60)
        hours, minute = divmod(minutes, 60)
        return f"{hours:02d}:{minute:02d}:{sec:02d},{ms:03d}"

    blocks = [f"{i}\n{stamp(s['start'])} --> {stamp(s['end'])}\n{s['text']}"
              for i, s in enumerate(result["segments"], 1)]
    srt_path.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")
    return {"speech_result_path": str(json_path.resolve()), "speech_transcript_path": str(text_path.resolve()),
            "speech_subtitle_path": str(srt_path.resolve())}
