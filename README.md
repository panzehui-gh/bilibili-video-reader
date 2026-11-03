# Bilibili Video Reader

[English](README.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

An Agent Skill for reading Bilibili videos through local subtitles, sampled frames, original-audio transcription, and sound-event analysis. It prepares evidence that an agent can inspect and explain with timestamps.

**Local execution has been verified on Windows.** The skill is intended for Codex and Claude Code; execution within Claude Code has not yet been verified. macOS and Linux require changes to the Windows launcher and executable paths.

## What it provides

- Metadata and available subtitle tracks from public `bilibili.com` and `b23.tv` links.
- Timestamped frames and candidate visual changes for inspecting slides, interfaces, demonstrations, and scenes.
- Local multilingual Whisper transcription of the original audio, with automatic language detection and segment/word timestamps. Platform subtitles remain separate.
- Local YAMNet sound-event candidates, waveform and acoustic measurements, and a sound timeline.
- A `summary.json` manifest with per-item and per-stage status, artifact paths, and retained source media for follow-up questions.

The default workflow uses no additional model API and has no automatic cloud fallback. Setup downloads tools and model weights; reading an online video still accesses Bilibili. Once setup is complete, previously downloaded media can be processed locally.

## Requirements and installation

The current launcher targets **Windows x64 with PowerShell 7**; the validated local environment uses Python 3.14 x64. Install Git and a working Python interpreter, then choose a skill destination:

```powershell
# Codex
$skillDir = Join-Path $HOME ".codex\skills\bilibili-video-reader"

# Or Claude Code: use this destination instead
# $skillDir = Join-Path $HOME ".claude\skills\bilibili-video-reader"

git clone https://github.com/panzehui-gh/bilibili-video-reader $skillDir
pwsh -NoProfile -File "$skillDir\scripts\setup_runtime.ps1" -Python python
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" -Doctor
```

`-Python` accepts a working Python command or executable path. A Windows Store placeholder that does not start Python is not sufficient.

The setup script creates `runtime/venv`, installs `scripts/requirements-local.txt`, downloads and checks FFmpeg and YAMNet, and downloads the multilingual Whisper small model. Use `-SkipModels` to defer model downloads; speech and sound classification will then need their model files before use. After installation, refresh the host's skill discovery if necessary.

Runtime environments, executables, model weights, user media, and machine-specific paths are not included in this repository.

## Usage

Ask the agent to use the skill:

> Use the bilibili-video-reader skill to analyze this Bilibili link. Check the visible scenes, original speech, and sound changes, and explain which parts you actually inspected.

Or invoke the local launcher directly, replacing the URL placeholder:

```powershell
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" `
  -Url "<Bilibili URL>" -Mode full -OutDir ".\results"
```

| Option | Purpose |
| --- | --- |
| `-Mode full` | Prepare subtitles, visual, speech, and sound evidence; this is the default |
| `-Mode visual` | Inspect sampled frames and visual-change candidates |
| `-Mode speech` | Transcribe the original audio locally |
| `-Mode sound` | Analyze music/sound candidates and acoustic changes |
| `-Mode subtitles` | Retrieve text evidence without the full audiovisual workflow |
| `-FocusSeconds 12.5` | Focus the visual inspection around a particular time |
| `-SourceMedia ".\media\video.mp4"` | Reuse an existing local video; no URL is needed for local input |
| `-SpeechLanguage en` | Override language detection when the language is known |
| `-VerifySpeech` | Save an additional transcription without voice activity detection, retaining both versions |
| `-OutDir ".\results"` | Choose the output location |
| `-Doctor` | Check local runtime readiness |

Downloaded media is retained for later inspection. The manifest identifies its location so another request can reuse it through `-SourceMedia`.

## Reading the results

Start with `summary.json` (`schema_version: 2`). Check each item's `status` and its `metadata`, `download`, `subtitles`, `visual`, `speech`, and `sound` stages. A partial result should be reported as partial.

The manifest separates `subtitle_transcript_path` from `speech_transcript_path` and `speech_result_path`. It also records timestamped `frames`, `scene_candidates`, and sound artifacts such as `audio_timeline_path`, `event_tags_path`, and `transient_candidates_path`.

**An agent must open the relevant images before describing the visuals or drawing audiovisual conclusions.** The scripts prepare evidence; a scene-change score alone does not explain a scene. Match the timestamps of inspected frames with the original-audio results when discussing how picture and sound work together.

## Limits and verification

The existing Windows pipeline was verified with real media. The repository's fresh-install bootstrap has received static checks only; installation and execution inside Claude Code are left for the target host to verify.

- Frames are samples. A default run does not mean every moment of a video has been watched, especially for long videos or unknown durations.
- ASR is machine transcription, not a manually checked verbatim record. Music, singing, synthesized voices, and overlapping sounds can produce omissions or false words.
- YAMNet scores are candidate labels, not confirmed instruments, sound sources, or song identities. An acoustic transient is not automatically a UI notification or a click.
- Access restrictions, missing subtitles, and platform risk controls may prevent some stages from completing. The workflow does not automatically extract browser cookies or bypass access restrictions.
- The current implementation uses Windows `.exe` paths and a PowerShell launcher. macOS/Linux support and execution under Claude Code remain to be validated separately.

See [SKILL.md](SKILL.md), the [output map](references/output-map.md), and the [audio/visual analysis guide](references/audio-visual-analysis.md) for agent-facing instructions. Runtime details are in [local-runtime.md](references/local-runtime.md).

## Attribution and licensing

This project builds on [yichen11818/bilibili-video-reader](https://github.com/yichen11818/bilibili-video-reader). The local audiovisual workflow and packaging are maintained by **PAN ZEHUI**.

The upstream repository did not provide a `LICENSE` file when reviewed. This repository does not assign a blanket MIT license to that upstream material. Third-party tools and model weights retain their respective licenses; runtime downloads are not redistributed here.
