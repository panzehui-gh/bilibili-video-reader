"""Prepare local visual, speech and sound evidence for a Bilibili video."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

import read_bilibili_video as reader


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(args):
    process = subprocess.run([str(x) for x in args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if process.returncode:
        raise RuntimeError(process.stderr[-1600:] or f"Command exited with {process.returncode}")
    return process


def probe(media, runtime):
    result = command([runtime / "ffmpeg/ffprobe.exe", "-v", "error", "-show_entries",
                      "format=duration:stream=codec_type,sample_rate,channels", "-of", "json", media])
    data = json.loads(result.stdout)
    raw_duration = data.get("format", {}).get("duration")
    duration = float(raw_duration) if raw_duration not in (None, "N/A") else None
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        duration = None
    return {"duration_seconds": duration, "has_audio": any(s.get("codec_type") == "audio" for s in data.get("streams", [])),
            "has_video": any(s.get("codec_type") == "video" for s in data.get("streams", [])), "streams": data.get("streams", [])}


def doctor(runtime):
    packages = {}
    for name in ("yt_dlp", "faster_whisper", "numpy", "onnxruntime"):
        packages[name] = importlib.util.find_spec(name) is not None
    paths = ["ffmpeg/ffmpeg.exe", "ffmpeg/ffprobe.exe", "models/whisper-small/model.bin",
             "models/whisper-small/config.json", "models/whisper-small/tokenizer.json", "models/whisper-small/vocabulary.txt",
             "yamnet/yamnet.onnx", "yamnet/yamnet_class_map.csv"]
    files = {p: (runtime / p).is_file() for p in paths}
    return {"ready": all(packages.values()) and all(files.values()), "python": sys.executable,
            "runtime_dir": str(runtime), "packages": packages, "files": files, "cloud_api_used": False}


def scene_candidates(media, runtime, duration, limit=16):
    # Differences at 2 fps suggest locations to inspect, not verified scene cuts.
    result = command([runtime / "ffmpeg/ffmpeg.exe", "-hide_banner", "-nostats", "-i", media,
                      "-vf", "fps=2,scale=320:-2,select='gt(scene,0.18)',showinfo", "-an", "-f", "null", "-"])
    values = sorted(set(float(x) for x in re.findall(r"pts_time:([0-9.]+)", result.stderr)))
    values = [t for t in values if t > .25 and (duration is None or t < duration)]
    if len(values) > limit:
        indices = [round(i * (len(values) - 1) / (limit - 1)) for i in range(limit)]
        values = [values[i] for i in indices]
    return [{"timestamp_seconds": t, "source": "frame_difference_2fps", "verified_scene_cut": False} for t in values]


def process_item(entry, index, item_url, args, runtime, run_dir):
    item_dir = run_dir / f"{index:02d}-{reader.slugify(str(entry.get('id') or 'local-video'), limit=40)}"
    item_dir.mkdir()
    result = {"index": index, "source_url": item_url, "title": entry.get("title"), "item_id": entry.get("id"),
              "output_dir": str(item_dir), "status": "complete", "stages": {}, "frames": [], "scene_candidates": []}
    stages = result["stages"]

    def failed(stage, error):
        stages[stage] = {"status": "failed", "error": str(error)[-2000:]}
        result["status"] = "partial"

    metadata = {k: entry.get(k) for k in ("id", "title", "uploader", "description", "duration", "webpage_url", "upload_date")}
    metadata_path = item_dir / "metadata.json"
    write_json(metadata_path, metadata)
    result["metadata_path"] = str(metadata_path)
    stages["metadata"] = {"status": "complete"}
    needs_visual = args.mode in ("full", "visual")
    needs_speech = args.mode in ("full", "speech")
    needs_sound = args.mode in ("full", "sound")
    needs_media = needs_visual or needs_speech or needs_sound
    media = Path(args.source_media).expanduser().resolve() if args.source_media else None
    if media:
        stages["download"] = {"status": "reused", "path": str(media)}
        stages["subtitles"] = {"status": "not_requested", "reason": "Using existing local media; no network subtitle request."}
    else:
        options = {"noplaylist": True, "outtmpl": str(item_dir / "%(id)s.%(ext)s"),
                   "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["all"],
                   "subtitlesformat": "vtt/srt/ass/json3/best", "ffmpeg_location": str(runtime / "ffmpeg"),
                   "socket_timeout": 20, "retries": 2, "fragment_retries": 2}
        if needs_media:
            options["format"] = "bv*+ba/b" if needs_visual else "bestaudio/best"
            if needs_visual:
                options["merge_output_format"] = "mp4"
        else:
            options["skip_download"] = True
        try:
            downloaded = reader.extract_info(item_url, download=True, options=options)
            metadata.update({k: downloaded.get(k, metadata.get(k)) for k in metadata})
            write_json(metadata_path, metadata)
            stages["download"] = {"status": "complete" if needs_media else "not_requested"}
        except Exception as error:
            failed("download", error)
        subtitles, audio_files, video_files, danmaku_files = reader.find_generated_files(item_dir)
        if not media:
            media = (video_files or audio_files or [None])[0]
        text, source_files = reader.build_transcript(subtitles)
        if text:
            path = item_dir / "subtitle-transcript.txt"
            path.write_text(text + "\n", encoding="utf-8")
            result["subtitle_transcript_path"] = str(path)
        result["subtitle_files"] = [str(p) for p in source_files]
        stages["subtitles"] = {"status": "complete" if text else "unavailable", "source": "caption_tracks", "not_original_audio_asr": True}
        if danmaku_files:
            path = item_dir / "danmaku-summary.json"
            write_json(path, reader.summarize_danmaku(reader.parse_danmaku_file(danmaku_files[0]),
                       focus_seconds=args.focus_seconds, focus_window_seconds=45))
            result["danmaku_summary_path"] = str(path)
    if not needs_media:
        for stage in ("visual", "speech", "sound"):
            stages[stage] = {"status": "not_requested"}
        return result
    if media is None or not media.is_file():
        failed("media", "No downloadable media was available. Public/login/region restrictions may apply.")
        return result
    result["media_path"] = str(media)
    try:
        media_info = probe(media, runtime)
    except Exception as error:
        failed("media", error)
        return result
    result["media_info"] = media_info
    result["focus_seconds"] = args.focus_seconds
    if needs_visual and media_info["has_video"]:
        try:
            frames = reader.extract_frames_from_video(media, item_dir / "frames", args.frame_count, args.frame_width,
                      focus_seconds=args.focus_seconds, focus_window_seconds=45)
            for f in frames:
                f["origin"] = "uniform_sample" if args.focus_seconds is None else "focus_sample"
            focus = args.focus_seconds
            if focus is not None and (media_info["duration_seconds"] is None or focus < media_info["duration_seconds"]):
                if not any(abs(focus - f["timestamp_seconds"]) < .02 for f in frames):
                    anchor = item_dir / "frames" / f"focus-anchor-{round(focus*1000):09d}ms.jpg"
                    command([runtime / "ffmpeg/ffmpeg.exe", "-v", "error", "-y", "-ss", focus, "-i", media,
                             "-frames:v", "1", "-vf", f"scale={args.frame_width}:-2", "-q:v", "4", anchor])
                    if anchor.is_file():
                        frames.append({"path": str(anchor), "timestamp_seconds": focus,
                                       "timestamp_label": reader.format_timestamp(focus), "origin": "focus_anchor"})
            candidates = scene_candidates(media, runtime, media_info["duration_seconds"])
            if args.focus_seconds is not None:
                candidates = [c for c in candidates if abs(c["timestamp_seconds"] - args.focus_seconds) <= 22.5]
            result["scene_candidates"] = candidates
            extra = item_dir / "frames"
            for i, c in enumerate(candidates):
                t = c["timestamp_seconds"]
                if any(abs(t - f["timestamp_seconds"]) < .3 for f in frames):
                    continue
                path = extra / f"candidate-{i+1:02d}-{round(t*1000):09d}ms.jpg"
                command([runtime / "ffmpeg/ffmpeg.exe", "-v", "error", "-y", "-ss", t, "-i", media,
                         "-frames:v", "1", "-vf", f"scale={args.frame_width}:-2", "-q:v", "4", path])
                if path.is_file():
                    frames.append({"path": str(path), "timestamp_seconds": t, "timestamp_label": reader.format_timestamp(t), "origin": "scene_candidate"})
            frames.sort(key=lambda f: f["timestamp_seconds"])
            if not frames:
                raise RuntimeError("Frame extraction produced no image files")
            result["frames"] = frames
            path = item_dir / "frames.json"
            write_json(path, frames)
            result["frame_manifest_path"] = str(path)
            stages["visual"] = {"status": "complete", "sampling_only": True, "frame_count": len(frames),
                                "requires_image_inspection": True}
        except Exception as error:
            failed("visual", error)
    else:
        stages["visual"] = {"status": "not_requested" if not needs_visual else "unavailable"}
    wav, event_wav = item_dir / "original-stereo.wav", item_dir / "audio-16khz.wav"
    if (needs_speech or needs_sound) and media_info["has_audio"]:
        try:
            command([runtime / "ffmpeg/ffmpeg.exe", "-v", "error", "-y", "-i", media, "-vn", "-c:a", "pcm_s16le", wav])
            command([runtime / "ffmpeg/ffmpeg.exe", "-v", "error", "-y", "-i", media, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", event_wav])
            result["original_audio_path"], result["event_audio_path"] = str(wav), str(event_wav)
        except Exception as error:
            failed("audio", error)
    if needs_speech and event_wav.is_file():
        try:
            from local_speech import transcribe_local, export_speech
            speech = transcribe_local(event_wav, runtime / "models/whisper-small", language=args.speech_language)
            result.update(export_speech(speech, item_dir))
            stages["speech"] = {"status": "complete", "backend": "local", "language": speech["language"],
                                "segment_count": len(speech["segments"]), "not_caption_or_visual_text": True}
            if args.verify_speech:
                alternate = transcribe_local(event_wav, runtime / "models/whisper-small", language=speech["language"], vad=False)
                alternate_files = export_speech(alternate, item_dir, stem="speech-full-audio-check")
                result["speech_verification"] = {"primary_and_check_identical": speech["text"].casefold() == alternate["text"].casefold(),
                                                  "files": alternate_files, "requires_review": True}
        except Exception as error:
            failed("speech", error)
    else:
        stages["speech"] = {"status": "not_requested" if not needs_speech else "unavailable"}
    if needs_sound and event_wav.is_file():
        try:
            from analyze_audio import analyze_audio
            sound = analyze_audio(wav, event_wav=event_wav, out_dir=item_dir / "sound", model_dir=runtime / "yamnet")
            result["sound_summary"] = sound
            for key in ("audio_timeline_path", "event_tags_path", "transient_candidates_path"):
                result[key] = sound[key]
            stages["sound"] = {"status": "complete", "backend": "local", "classification_only": True}
        except Exception as error:
            failed("sound", error)
    else:
        stages["sound"] = {"status": "not_requested" if not needs_sound else "unavailable"}
    return result


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--source-media")
    parser.add_argument("--mode", choices=("full", "visual", "speech", "sound", "subtitles"), default="full")
    parser.add_argument("--out-dir", default="work/bilibili")
    parser.add_argument("--runtime-dir", type=Path, default=Path(__file__).resolve().parent.parent / "runtime")
    parser.add_argument("--frame-count", type=int, default=12)
    parser.add_argument("--frame-width", type=int, default=1280)
    parser.add_argument("--focus-seconds", type=float)
    parser.add_argument("--speech-language")
    parser.add_argument("--verify-speech", action="store_true")
    parser.add_argument("--doctor", action="store_true")
    args = parser.parse_args()
    runtime = args.runtime_dir.expanduser().resolve()
    os.environ["PATH"] = str(runtime / "ffmpeg") + os.pathsep + os.environ.get("PATH", "")
    if args.doctor:
        report = doctor(runtime)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ready"] else 1
    if not args.url and not args.source_media:
        parser.error("Provide --url or --source-media")
    if args.frame_count < 1 or args.frame_width < 160 or (args.focus_seconds is not None and args.focus_seconds < 0):
        parser.error("Frame count/width and focus timestamp must be positive")
    if args.url:
        reader.ensure_bilibili_url(args.url)
        if args.focus_seconds is None:
            args.focus_seconds = reader.focus_seconds_from_url(args.url)
    root = Path(args.out_dir).expanduser().resolve()
    run_dir = root / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S-%fZ")
    run_dir.mkdir(parents=True)
    summary = {"schema_version": 2, "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "source_url": args.url, "mode": args.mode, "status": "complete", "cloud_api_used": False,
               "output_dir": str(run_dir), "items": []}
    try:
        if args.source_media:
            media = Path(args.source_media).expanduser().resolve()
            if not media.is_file():
                raise FileNotFoundError(media)
            nearby_metadata = media.parent / "metadata.json"
            entry = json.loads(nearby_metadata.read_text(encoding="utf-8")) if nearby_metadata.is_file() else {"title": media.stem, "id": media.stem}
            entries = [entry]
        else:
            reader.require_yt_dlp()
            info = reader.extract_info(args.url, download=False, options={"skip_download": True, "socket_timeout": 20, "retries": 2})
            entries = reader.resolve_entries(info)
        for index, entry in enumerate(entries, 1):
            print(f"Preparing item {index}/{len(entries)}: {entry.get('title') or entry.get('id')}", flush=True)
            item_url = args.url if args.source_media else reader.pick_item_url(entry, args.url)
            item = process_item(entry, index, item_url, args, runtime, run_dir)
            write_json(Path(item["output_dir"]) / "summary.json", item)
            summary["items"].append(item)
        if any(i["status"] != "complete" for i in summary["items"]):
            summary["status"] = "partial"
    except (Exception, SystemExit) as error:
        summary["status"], summary["error"] = "failed", str(error)
    path = run_dir / "summary.json"
    write_json(path, summary)
    print(f"Summary: {path}", flush=True)
    print(f"Status: {summary['status']}; local-only evidence preparation", flush=True)
    return {"complete": 0, "partial": 2, "failed": 1}[summary["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
