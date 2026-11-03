---
name: bilibili-video-reader
description: "Read Bilibili and b23.tv video links using local subtitles, timestamped frames, independent original-audio ASR, and music/sound-event analysis. Use when a B站链接 is supplied for viewing, summarizing, scene explanation, spoken-content checks, 音乐/提示音/音效分析, or audio-visual timing. Select this skill for these requests even when the user does not name it."
---

# B站视频音画读取

把视频变成可核对的本地证据，再结合用户的问题解释。默认使用随 skill 保存的本地运行环境，不依赖之前聊天的工作目录，也不自动调用云模型。

## 单一入口

从 GitHub 首次下载时，仓库不包含二进制、模型或虚拟环境。先检查 `runtime/venv/Scripts/python.exe` 是否存在；若缺失，读取 [local-runtime.md](references/local-runtime.md)，用 `scripts/setup_runtime.ps1` 完成本地安装，再运行 `-Doctor`。不要复制其他机器的虚拟环境。

从本 `SKILL.md` 所在目录解析 `$skillRoot`，在 PowerShell 中调用：

```powershell
& "$skillRoot\scripts\run_bilibili.ps1" -Url $url -OutDir $outDir
```

`-Mode` 默认是 `full`。按问题选择需要的信号：

| Mode | 主要用途 |
| --- | --- |
| `full` | 字幕、画面、原声转写、声音事件及音画对应 |
| `visual` | 场景、图表、演示、界面变化 |
| `speech` | 原声中实际说了什么，与字幕核对 |
| `sound` | 音乐、非语音声音、声学变化和时间位置 |
| `subtitles` | 获取平台提供的字幕与元数据 |

可选参数：

- `-FocusSeconds 12.5`：聚焦某个时刻。链接中的时间参数也应作为关注点。
- `-SourceMedia $mediaPath`：复用已下载视频，避免再次下载。
- `-SpeechLanguage en`：只有用户指定语言或已有可靠依据时才传；省略时自动识别，不能把中文界面当作中文原声的证据。
- `-VerifySpeech`：保留不启用 VAD 的原声复核版本，用于漏词或音乐混合情况。
- `-OutDir $outDir`：指定本次产物位置；省略时使用入口返回的位置。

原声复核或声音分析即使已有字幕，也要读取原声音轨。不要把字幕或画面文字复制成“听到的话”。
默认保留本次视频素材，供后续通过 `-SourceMedia` 复用；不要擅自清理源视频。

## 读取与解释

1. 运行入口，打开返回的 `summary.json`（`schema_version: 2`）。先看 `items` 中每项的 `status`、`stages`、失败原因和绝对产物路径；退出码或某个文件的存在不等于所有阶段成功。读取布局见 [output-map.md](references/output-map.md)。
2. 用图像查看工具实际打开采样帧，按时间戳检查场景变化。`frames` 和 `scene_candidates` 只提供线索，文件名、缩略图地址或变化分数不能代替看图。
3. 按用户问题分别使用平台字幕、原声 ASR、声音分类和声学指标。涉及音乐、提示音或音画配合时，读 [audio-visual-analysis.md](references/audio-visual-analysis.md)，再核对对应时刻的画面。
4. 回答中区分直接看到的画面、模型转写/分类结果与解释。用必要的时间点说明依据，并简短交代缺失内容及采样范围。

短视频也可能漏掉瞬间变化。长视频或时长未知时，按问题和关注时刻分段采样；需要时补取相关区间。只有实际覆盖并核查了相应内容，才描述该范围，不能把默认采样称为“完整看完”。

## 本地运行约定

入口使用 skill 内的 `runtime/venv`、`runtime/ffmpeg`、`runtime/models/whisper-small` 和 `runtime/yamnet`。运行时优先使用这些路径，不借用历史聊天目录或依赖系统 `PATH` 恰好配置正确。
可用 `-Doctor` 检查就绪状态；修复细节见 [local-runtime.md](references/local-runtime.md)。

- ASR 使用本地模型，语言默认自动识别；产物是机器转写，不表示逐字听校。
- 声音分类给出候选标签与分数。分数不能直接证明某种乐器、音效来源或音乐风格；短促能量峰也不能一律称为“UI 提示音”。
- 缺少组件时报告具体缺项及已完成阶段，按当前请求范围修复；不自动换用付费 API。只有用户明确要求云模型时，才另行处理相应服务配置与费用。
- 登录、权限、地区限制或风控失败时保留明确错误；不自动读取浏览器 Cookie。已有用户提供的视频可通过 `-SourceMedia` 继续本地分析。

上游脚本若仍保留在目录中，仅作兼容资源；日常任务使用上述入口，不从旧的 `--analyze` 或云端 ASR 路径开始。
