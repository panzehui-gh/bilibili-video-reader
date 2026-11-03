# 本机运行环境

## 从仓库首次安装

公开仓库只保存源代码与下载清单，不包含 `runtime/`。在 Windows x64、PowerShell 7 和可运行的 Python 环境中执行：

```powershell
pwsh -NoProfile -File "$skillRoot\scripts\setup_runtime.ps1" -Python python
pwsh -NoProfile -File "$skillRoot\scripts\run_bilibili.ps1" -Doctor
```

本次已有环境使用 Python 3.14 x64。新机器须重建虚拟环境。`setup_runtime.ps1` 首次安装需要联网；本地既有流水线经过视频验证，仓库安装脚本仅做静态检查，需在目标宿主中验证。

脚本读取 `assets/downloads.json`，验证下载文件的 SHA-256。若上游版本变化导致不匹配，先检查新文件和来源，再更新清单，不能移除校验。`-SkipModels` 可延后模型下载。

正常使用 `scripts/run_bilibili.ps1`，无需激活环境或配置系统 PATH。

```powershell
& "$skillRoot\scripts\run_bilibili.ps1" -Doctor
```

运行环境位于 skill 自己的 `runtime/`：

- `venv/Scripts/python.exe`：专用 Python 环境。
- `ffmpeg/ffmpeg.exe` 与 `ffmpeg/ffprobe.exe`：解码、抽帧、音轨提取。
- `models/whisper-small/`：本地多语言 Whisper 模型。
- `yamnet/yamnet.onnx` 与 `yamnet_class_map.csv`：本地声音候选分类。
- `runtime-info.json`：来源、安装版本及校验记录。

这套环境已在当前 Windows 电脑验证；不声称可直接复制到其他操作系统。Python 基础解释器路径记录在 `runtime/venv/pyvenv.cfg`，不是历史聊天目录。若基础解释器被移除，可用现有兼容 Python 重建此 venv，并按 `scripts/requirements-local.txt` 修复依赖；不要用 WindowsApps 的占位 Python 启动器。

ASR 将 FFmpeg 解码的 PCM 波形直接传入 faster-whisper，避开本次出现的 PyAV `metadata_errors` 兼容问题。语言自动识别；只有明确指定时才固定语言。原声、平台字幕分别落盘。

模型和工具已经就位时，日常分析不需要重新下载模型。若组件缺失，先用 `-Doctor` 定位缺项，再在当前任务授权范围内修复。

来源记录：

- yt-dlp、faster-whisper、NumPy、ONNX Runtime：固定版本见 requirements-local.txt。
- FFmpeg：来自 [FFmpeg 官方下载页推荐的 Gyan Windows 构建](https://ffmpeg.org/download.html)。
- 语音模型：[Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)。
- 声音模型：[audiomagic/yamnet-onnx](https://huggingface.co/audiomagic/yamnet-onnx)，Google YAMNet 的 ONNX 导出；程序校验模型 SHA-256。
