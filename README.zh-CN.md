# Bilibili Video Reader

[English](README.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

让支持 Agent Skills 的助手读取 B 站视频，结合平台字幕、实际画面、原声转写和音乐/音效分析，以时间戳为依据回答问题。

**已在 Windows 本地验证。** 本技能面向 Codex 和 Claude Code；尚未在 Claude Code 中实测。当前启动器及可执行文件路径针对 Windows，macOS/Linux 需要适配。

## 可以做什么

- 获取公开 `bilibili.com`、`b23.tv` 链接的元数据与可用字幕。
- 抽取带时间戳的画面，提供场景变化候选和指定时刻的截图。
- 在本地转写原声音轨，自动识别语言，保留语句及词级时间戳；平台字幕与原声结果分开保存。
- 用本地 YAMNet 生成声音事件候选，并分析音量、低频比重、声学瞬态和立体声变化。
- 通过 `summary.json` 汇总每个视频项、每个阶段的状态及产物路径，保留源素材供后续复用。

默认不调用额外模型 API，也不会自动转用云模型。首次安装需要下载工具和模型；在线读视频需要访问 B 站。对已经下载的视频，可在本地处理。

## 安装

当前入口需要 **Windows x64、PowerShell 7、Git 和可正常运行的 Python**，本次验证使用 Python 3.14 x64。

```powershell
# Codex 的技能目录
$skillDir = Join-Path $HOME ".codex\skills\bilibili-video-reader"

# Claude Code 请改用这一目录
# $skillDir = Join-Path $HOME ".claude\skills\bilibili-video-reader"

git clone https://github.com/panzehui-gh/bilibili-video-reader $skillDir
pwsh -NoProfile -File "$skillDir\scripts\setup_runtime.ps1" -Python python
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" -Doctor
```

`-Python` 可以填写 Python 命令或解释器的完整路径；不能使用无法启动解释器的 Windows Store 占位入口。

安装脚本会在 `runtime/` 创建独立环境，按固定版本安装 Python 依赖，下载并校验 FFmpeg、YAMNet，以及多语言 Whisper small 模型。`-SkipModels` 可延后下载模型；语音与声音分类运行前仍须补齐。安装后按宿主应用需要刷新技能发现。

仓库不包含虚拟环境、二进制程序、模型权重、视频素材或本机私人路径。下载地址与校验值在 [assets/downloads.json](assets/downloads.json)；上游文件更新导致校验失败时，应先检查来源再更新清单，不能跳过校验。

## 使用

对助手说：

> 使用 bilibili-video-reader 分析这个 B 站链接，结合画面、原声和音乐音效说明内容，并区分实际核对到的证据与推测。

也可以直接运行：

```powershell
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" `
  -Url "<B站视频链接>" -Mode full -OutDir ".\results"
```

| 参数 | 用途 |
| --- | --- |
| `-Mode full` | 默认：字幕、画面、原声和声音分析 |
| `-Mode visual` | 画面采样与场景变化候选 |
| `-Mode speech` | 本地原声转写 |
| `-Mode sound` | 音乐/音效候选和声学变化 |
| `-Mode subtitles` | 平台字幕及元数据 |
| `-FocusSeconds 12.5` | 聚焦某时刻，并保存该时刻的截图 |
| `-SourceMedia ".\media\video.mp4"` | 复用已下载视频；本地输入可以不传 URL |
| `-SpeechLanguage en` | 有依据时指定原声语言，默认自动识别 |
| `-VerifySpeech` | 另存不启用 VAD 的转写复核，保留两版 |
| `-OutDir ".\results"` | 输出位置 |
| `-Doctor` | 检查运行环境是否就绪 |

## 读取结果与验证范围

先读 `summary.json`（`schema_version: 2`），分别检查元数据、下载、字幕、画面、原声和声音阶段。部分成功应按实际状态报告。

`subtitle_transcript_path` 是平台字幕；`speech_transcript_path` 和 `speech_result_path` 是独立原声 ASR。`frames`、`scene_candidates` 以及声音时间线用于核对时间关系。

**助手必须实际打开相关图片，才能描述画面和解释音画配合。** 脚本负责准备证据，不会仅凭场景变化分数自动理解画面。

- 默认抽帧属于采样，不表示完整看过每一瞬间。
- ASR 是机器识别，不等于人工逐字听校；歌声、合成音和重叠声音可能导致漏词或误识别。
- 声音分类分数不是已确认的乐器、音效来源或曲名；瞬态峰值不能一律称为界面提示音。
- 登录、地区限制、缺字幕或平台风控可能导致部分阶段失败；不会自动读取浏览器 Cookie 或绕过访问限制。
- 本地 Windows 流程已验证；公开仓库的全新安装脚本仅做静态检查，Claude Code 运行及其他系统适配请自行验证。

参见 [SKILL.md](SKILL.md)、[产物说明](references/output-map.md)、[音画分析方法](references/audio-visual-analysis.md)和[本地运行环境](references/local-runtime.md)。

## 来源与许可

本项目基于 [yichen11818/bilibili-video-reader](https://github.com/yichen11818/bilibili-video-reader)，本地音画整合、安装配置和多语言文档由 **PAN ZEHUI** 维护。

检查时上游未提供 LICENSE，本仓库不会为上游内容擅自声明全仓 MIT 许可。第三方工具和模型继续适用各自许可，详情见 [SOURCE_NOTICES.md](SOURCE_NOTICES.md)。
