"""Local soundtrack measurements and AudioSet event candidates, without uploads.

Event labels are model scores, not calibrated probabilities or evidence of a
particular sound's source. Transients can include speech consonants and music.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import wave

import numpy as np

YAMNET_SHA256 = "d3835ffbbd4a1bb3e777f0ca217b5007907f5171dd5d17c4236b95b2af8f908e"
EVENT_RATE = 16000
EVENT_HOP = 7680
EVENT_COVERAGE = 15600


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def wav_info(path: Path) -> dict:
    with wave.open(str(path), "rb") as source:
        if source.getcomptype() != "NONE":
            raise ValueError("Provide an uncompressed integer PCM WAV, for example FFmpeg pcm_s16le.")
        if source.getsampwidth() not in (1, 2, 3, 4):
            raise ValueError("Supported PCM widths are 8, 16, 24 and 32 bits.")
        rate = source.getframerate()
        channels = source.getnchannels()
        frames = source.getnframes()
        width = source.getsampwidth()
    if not rate or not channels:
        raise ValueError("WAV sample rate and channel count must be positive.")
    return {"sample_rate": rate, "channels": channels, "sample_width": width,
            "frames": frames, "duration_seconds": frames / rate}


def read_pcm(source: wave.Wave_read, frame_count: int) -> np.ndarray:
    """Read normalized floating samples, preserving channels."""
    raw = source.readframes(frame_count)
    width = source.getsampwidth()
    if width == 1:
        values = (np.frombuffer(raw, np.uint8).astype(np.float32) - 128) / 128
    elif width == 2:
        values = np.frombuffer(raw, "<i2").astype(np.float32) / 32768
    elif width == 3:
        octets = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        values = octets[:, 0] | (octets[:, 1] << 8) | (octets[:, 2] << 16)
        values = np.where(values & 0x800000, values - 0x1000000, values).astype(np.float32) / 8388608
    else:
        values = np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648
    return values.reshape(-1, source.getnchannels())


def make_event_wav(input_wav: Path, output: Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required to prepare mono 16 kHz audio; set PATH or pass --event-wav.")
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(input_wav),
                    "-vn", "-ac", "1", "-ar", str(EVENT_RATE), "-c:a", "pcm_s16le", str(output)], check=True)
    return output


def event_scores(event_wav: Path, model_dir: Path) -> tuple[np.ndarray, list[str]]:
    """Evaluate bounded batches on a single global 0.48-second frame grid."""
    import onnxruntime as ort

    model_file = model_dir / "yamnet.onnx"
    if not model_file.is_file():
        raise FileNotFoundError(f"Missing local sound-event model: {model_file}")
    with model_file.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != YAMNET_SHA256:
            raise ValueError("YAMNet checksum does not match the configured model export.")
    with (model_dir / "yamnet_class_map.csv").open(encoding="utf-8", newline="") as source:
        labels = [row["display_name"] for row in csv.DictReader(source)]
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    session = ort.InferenceSession(str(model_file), sess_options=options, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output_name = next((item.name for item in session.get_outputs()
                        if len(item.shape) == 2 and item.shape[1] == len(labels)), None)
    if output_name is None:
        raise ValueError("The model has no AudioSet score output matching its label map.")
    info = wav_info(event_wav)
    if info["sample_rate"] != EVENT_RATE or info["channels"] != 1:
        raise ValueError("--event-wav must be a mono 16 kHz PCM WAV.")
    count = info["frames"]
    if count == 0:
        return np.zeros((0, len(labels)), np.float32), labels
    total = 1 + max(0, math.ceil((count - EVENT_COVERAGE) / EVENT_HOP))
    batches = []
    with wave.open(str(event_wav), "rb") as source:
        for first in range(0, total, 125):
            wanted = min(125, total - first)
            required = EVENT_COVERAGE + (wanted - 1) * EVENT_HOP
            source.setpos(min(first * EVENT_HOP, count))
            waveform = read_pcm(source, required).ravel().astype(np.float32)
            waveform = np.pad(waveform, (0, max(0, required - len(waveform))))
            result = session.run([output_name], {input_name: waveform})[0]
            if result.shape[0] < wanted:
                raise RuntimeError("YAMNet returned fewer frames than the requested batch.")
            batches.append(result[:wanted])
    return np.concatenate(batches), labels


def top_tags(values: np.ndarray, labels: list[str], count: int = 7) -> list[dict]:
    return [{"label": labels[index], "score": round(float(values[index]), 5)}
            for index in np.argsort(values)[-count:][::-1]]


def spectral_metrics(input_wav: Path) -> dict[str, np.ndarray]:
    """Bounded STFT batches with continuous time and spectral-flux history."""
    info = wav_info(input_wav)
    rate, count = info["sample_rate"], info["frames"]
    size = max(128, 2 ** math.ceil(math.log2(max(1, rate * .04))))
    hop = max(1, round(rate * .01))
    total = max(1, math.ceil(max(0, count - size) / hop) + 1) if count else 0
    frequency = np.fft.rfftfreq(size, 1 / rate)
    low_mask = frequency < 150
    window = np.hanning(size)
    collected = {key: [] for key in ("times", "rms_dbfs", "low_fraction", "spectral_flux")}
    previous = None
    with wave.open(str(input_wav), "rb") as source:
        for first in range(0, total, 1000):
            wanted = min(1000, total - first)
            required = size + (wanted - 1) * hop
            source.setpos(min(first * hop, count))
            mono = read_pcm(source, required).mean(axis=1)
            mono = np.pad(mono, (0, max(0, required - len(mono))))
            frames = np.lib.stride_tricks.sliding_window_view(mono, size)[::hop][:wanted]
            magnitude = np.abs(np.fft.rfft(frames * window, axis=1))
            power = magnitude ** 2
            first_previous = magnitude[:1] if previous is None else previous[None, :]
            flux = np.maximum(np.diff(magnitude, axis=0, prepend=first_previous), 0).sum(axis=1)
            previous = magnitude[-1]
            times = (np.arange(first, first + wanted) * hop + size / 2) / rate
            times = np.minimum(times, max(0, (count - .5) / rate))
            rms = np.sqrt(np.mean(frames ** 2, axis=1))
            collected["times"].append(times)
            collected["rms_dbfs"].append(20 * np.log10(np.maximum(rms, 1e-8)))
            collected["low_fraction"].append(power[:, low_mask].sum(axis=1) / np.maximum(power.sum(axis=1), 1e-15))
            collected["spectral_flux"].append(flux)
    return {key: np.concatenate(value).astype(np.float32) if value else np.empty(0, np.float32)
            for key, value in collected.items()}


def interval_rows(input_wav: Path, edges: list[float], features: dict, scores: np.ndarray, labels: list[str]) -> list[dict]:
    info = wav_info(input_wav)
    rate, frames = info["sample_rate"], info["frames"]
    score_start = np.arange(len(scores)) * .48
    score_end = score_start + .975
    rows = []
    with wave.open(str(input_wav), "rb") as source:
        for start, end in zip(edges, edges[1:]):
            if end <= start:
                continue
            # Read at most one second at a time, even for long custom stages.
            position, end_position = round(start * rate), min(frames, round(end * rate))
            source.setpos(min(position, frames))
            squares = mid_squares = side_squares = samples = 0
            while position < end_position:
                audio = read_pcm(source, min(rate, end_position - position)).astype(np.float64)
                if not len(audio):
                    break
                squares += float(np.sum(audio ** 2))
                samples += audio.size
                if audio.shape[1] == 2:
                    mid_squares += float(np.sum(audio.mean(axis=1) ** 2))
                    side_squares += float(np.sum(((audio[:, 0] - audio[:, 1]) / 2) ** 2))
                position += len(audio)
            rms = math.sqrt(squares / max(samples, 1))
            mask = (features["times"] >= start) & (features["times"] < end)
            low = float(np.median(features["low_fraction"][mask])) if np.any(mask) else None
            flux = float(np.max(features["spectral_flux"][mask])) if np.any(mask) else None
            weights = np.maximum(0, np.minimum(end, score_end) - np.maximum(start, score_start))
            tags = top_tags(np.average(scores, axis=0, weights=weights), labels) if weights.sum() else []
            row = {"start": round(start, 6), "end": round(end, 6),
                   "rms_dbfs": round(20 * math.log10(max(rms, 1e-8)), 3),
                   "low_frequency_fraction_median": round(low, 5) if low is not None else None,
                   "spectral_flux_max": round(flux, 5) if flux is not None else None,
                   "stereo_side_to_mid_db": round(10 * math.log10(max(side_squares, 1e-15) / max(mid_squares, 1e-15)), 3)
                   if info["channels"] == 2 and mid_squares + side_squares > 1e-12 else None,
                   "tags": tags}
            rows.append(row)
    return rows


def parse_boundaries(value: str | None) -> list[float] | None:
    if not value:
        return None
    candidate = Path(value)
    raw = json.loads(candidate.read_text(encoding="utf-8")) if candidate.is_file() else value.split(",")
    if isinstance(raw, dict):
        raw = raw.get("boundaries", [])
    result = [float(item) for item in raw]
    if any(not math.isfinite(item) for item in result):
        raise ValueError("Boundaries must be finite seconds.")
    return result


def analyze_audio(input_wav: Path | str, *, out_dir: Path | str, model_dir: Path | str,
                  event_wav: Path | str | None = None, window_seconds: float = 1,
                  boundaries: list[float] | None = None, save_metrics: bool = False) -> dict:
    input_wav, out_dir, model_dir = Path(input_wav).resolve(), Path(out_dir).resolve(), Path(model_dir).resolve()
    if not math.isfinite(window_seconds) or window_seconds <= 0:
        raise ValueError("window_seconds must be finite and positive.")
    out_dir.mkdir(parents=True, exist_ok=True)
    info = wav_info(input_wav)
    duration = info["duration_seconds"]
    event_wav = Path(event_wav).resolve() if event_wav else input_wav
    event_info = wav_info(event_wav)
    if event_info["sample_rate"] != EVENT_RATE or event_info["channels"] != 1:
        if event_wav != input_wav:
            raise ValueError("Explicit event_wav must be mono 16 kHz.")
        event_wav = make_event_wav(input_wav, out_dir / "event-input-16khz.wav")
        event_info = wav_info(event_wav)
    if abs(event_info["duration_seconds"] - duration) > .1:
        raise ValueError("The event WAV must cover the same full time range as the input WAV.")
    scores, labels = event_scores(event_wav, model_dir)
    events = [{"start": round(index * .48, 6), "end": round(min(duration, index * .48 + .975), 6),
               "tags": top_tags(row, labels)} for index, row in enumerate(scores)]
    write_json(out_dir / "event-tags.json", events)
    features = spectral_metrics(input_wav)
    edges = [min(index * window_seconds, duration) for index in range(math.ceil(duration / window_seconds) + 1)] if duration else [0]
    timeline = interval_rows(input_wav, edges, features, scores, labels)
    stage_rows = []
    if boundaries is not None:
        if any(not math.isfinite(value) for value in boundaries):
            raise ValueError("Boundaries must be finite seconds.")
        stage_edges = sorted({0., duration, *(float(x) for x in boundaries if 0 < x < duration)})
        stage_rows = interval_rows(input_wav, stage_edges, features, scores, labels)
    # A spectral change is not itself evidence of a UI tone or an instrument.
    flux, db, times = features["spectral_flux"], features["rms_dbfs"], features["times"]
    candidates = []
    for index in np.argsort(flux)[::-1]:
        instant = float(times[index])
        if flux[index] <= 0 or db[index] < -55 or any(abs(instant - row["time"]) < .28 for row in candidates):
            continue
        candidates.append({"time": round(instant, 6), "rms_dbfs": round(float(db[index]), 3),
                           "spectral_flux": round(float(flux[index]), 5), "kind": "signal_change_candidate"})
        if len(candidates) >= max(20, min(500, math.ceil(duration * 2))):
            break
    candidates.sort(key=lambda row: row["time"])
    write_json(out_dir / "transient-candidates.json", candidates)
    output = {"schema_version": 1, "source_wav": str(input_wav), "event_wav": str(event_wav), **info,
              "window_seconds": window_seconds, "low_frequency_cutoff_hz": 150,
              "event_hop_seconds": .48, "event_coverage_seconds": .975,
              "limitations": ["AudioSet labels are model scores, not calibrated confidence or proof of a sound source.",
                              "Signal-change candidates may be speech, music or effects; do not label every peak as a UI tone.",
                              "No source separation was performed. Low-frequency fractions describe the mixed track.",
                              "Stereo width is null for mono, multichannel and silent inputs. No timbre or beat guarantee is implied."],
              "windows": timeline, "stages": stage_rows}
    write_json(out_dir / "audio-timeline.json", output)
    if save_metrics:
        np.savez_compressed(out_dir / "metrics.npz", **features)
    return {"duration_seconds": duration, "audio_timeline_path": str(out_dir / "audio-timeline.json"),
            "event_tags_path": str(out_dir / "event-tags.json"),
            "transient_candidates_path": str(out_dir / "transient-candidates.json"),
            "metrics_path": str(out_dir / "metrics.npz") if save_metrics else None,
            "window_count": len(timeline), "event_frame_count": len(events)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_wav", type=Path)
    parser.add_argument("--event-wav", type=Path, help="Matching full-length mono 16 kHz PCM WAV, if already extracted")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--window-seconds", type=float, default=1)
    parser.add_argument("--boundaries", help="Comma-separated absolute seconds or a JSON list/file with a boundaries field")
    parser.add_argument("--save-metrics", action="store_true")
    args = parser.parse_args()
    result = analyze_audio(args.input_wav, out_dir=args.out_dir, model_dir=args.model_dir,
                           event_wav=args.event_wav, window_seconds=args.window_seconds,
                           boundaries=parse_boundaries(args.boundaries), save_metrics=args.save_metrics)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
