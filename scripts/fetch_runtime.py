"""Download runtime assets on explicit setup; never upload user media."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import sys
import urllib.request
import zipfile


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def fetch(url, target, expected):
    if target.is_file() and digest(target) == expected:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(target.name + ".part")
    print(f"Downloading {target.name}", flush=True)
    request = urllib.request.Request(url, headers={"User-Agent": "bilibili-video-reader-setup"})
    with urllib.request.urlopen(request, timeout=120) as source, temporary.open("wb") as output:
        shutil.copyfileobj(source, output)
    if digest(temporary) != expected:
        raise RuntimeError(f"Checksum mismatch for {target.name}. Review assets/downloads.json against the upstream release; do not skip verification.")
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-dir", type=Path)
    parser.add_argument("--skip-models", action="store_true")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("The packaged launcher currently targets Windows x64; adapt executable paths before using another OS.")
    root = Path(__file__).resolve().parent.parent
    runtime = (args.runtime_dir or root / "runtime").expanduser().resolve()
    manifest = json.loads((root / "assets/downloads.json").read_text(encoding="utf-8"))
    ffmpeg = manifest["ffmpeg"]
    target_dir = runtime / "ffmpeg"
    binaries_ready = all((target_dir / name).is_file() and digest(target_dir / name) == sha for name, sha in ffmpeg["binaries"].items())
    if not binaries_ready:
        bundle = runtime / "downloads/ffmpeg-essentials.zip"
        fetch(ffmpeg["url"], bundle, ffmpeg["sha256"])
        target_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle) as archive:
            for name, sha in ffmpeg["binaries"].items():
                matches = [entry for entry in archive.infolist() if entry.filename.endswith("/bin/" + name)]
                if len(matches) != 1:
                    raise RuntimeError(f"Unexpected FFmpeg archive layout for {name}")
                target = target_dir / name
                with archive.open(matches[0]) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if digest(target) != sha:
                    raise RuntimeError(f"Binary checksum mismatch: {name}")
    if not args.skip_models:
        yamnet = manifest["yamnet"]
        fetch(yamnet["url"], runtime / "yamnet/yamnet.onnx", yamnet["sha256"])
        fetch(yamnet["labels_url"], runtime / "yamnet/yamnet_class_map.csv", yamnet["labels_sha256"])
        whisper = manifest["whisper"]
        whisper_dir = runtime / "models/whisper-small"
        ready = all((whisper_dir / name).is_file() for name in whisper["files"])
        if not ready or digest(whisper_dir / "model.bin") != whisper["model_sha256"]:
            from huggingface_hub import snapshot_download
            print("Downloading the local multilingual Whisper small model", flush=True)
            snapshot_download(whisper["repo_id"], local_dir=str(whisper_dir), allow_patterns=whisper["files"], token=False)
        if digest(whisper_dir / "model.bin") != whisper["model_sha256"]:
            raise RuntimeError("Whisper model checksum changed; review the upstream model before updating the manifest.")
    versions = {name: importlib.metadata.version(name) for name in ("yt-dlp", "faster-whisper", "numpy", "onnxruntime")}
    record = {"configured_at_utc": datetime.now(timezone.utc).isoformat(), "platform": sys.platform,
              "python": sys.version, "versions": versions, "models_deferred": args.skip_models,
              "sources": manifest, "default_inference": "local", "auto_cloud_fallback": False}
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "runtime-info.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Runtime assets prepared", flush=True)


if __name__ == "__main__":
    main()
