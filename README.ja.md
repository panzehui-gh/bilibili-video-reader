# Bilibili Video Reader

[English](README.md) · [日本語](README.ja.md) · [简体中文](README.zh-CN.md)

Bilibili の動画を、字幕、抽出した画像、原音声の文字起こし、音の分析から読み取る Agent Skill です。エージェントが内容を確かめ、時刻とともに説明できるように、必要なデータをローカルで用意します。

**Windows 上でのローカル実行は確認済みです。** Codex と Claude Code での利用を想定していますが、Claude Code 内での動作はまだ検証していません。macOS と Linux では、Windows 用の起動スクリプトや実行ファイルのパスを変更する必要があります。

## できること

- 公開された `bilibili.com`・`b23.tv` のリンクから、動画情報と取得可能な字幕を読み込みます。
- 時刻付きの画像と画面変化の候補を抽出し、スライド、操作画面、実演、場面を確認できます。
- 原音声をローカルの多言語 Whisper で文字起こしします。言語は自動判定し、区間・単語の時刻を保存します。プラットフォームの字幕とは別に扱います。
- ローカルの YAMNet による音の分類候補、波形、音響指標、時系列の分析結果を作成します。
- 動画ごと・処理段階ごとの状態と出力先を `summary.json` に記録します。取得した動画は、後の確認にも使えるように残します。

通常の処理に追加のモデル API は不要で、クラウドへ自動的に切り替えることもありません。初回設定時にはツールやモデルをダウンロードし、動画リンクの読み込み時には Bilibili にアクセスします。設定後は、取得済みの動画をローカルで処理できます。

## 必要な環境とインストール

現在の起動スクリプトは **Windows x64・PowerShell 7 用**です。確認済みのローカル環境では Python 3.14 x64 を使っています。Git と実際に起動できる Python を用意し、利用するエージェントに合わせて保存先を選びます。

```powershell
# Codex
$skillDir = Join-Path $HOME ".codex\skills\bilibili-video-reader"

# Claude Code の場合は、代わりにこちらを指定
# $skillDir = Join-Path $HOME ".claude\skills\bilibili-video-reader"

git clone https://github.com/panzehui-gh/bilibili-video-reader $skillDir
pwsh -NoProfile -File "$skillDir\scripts\setup_runtime.ps1" -Python python
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" -Doctor
```

`-Python` には、利用可能な Python コマンドまたは実行ファイルのパスを指定できます。Python が起動しない Windows Store の案内用コマンドでは実行できません。

設定スクリプトは `runtime/venv` を作り、`scripts/requirements-local.txt` の依存パッケージを入れます。また、FFmpeg と YAMNet をダウンロードして検証し、多言語 Whisper の small モデルを取得します。モデルの取得を後回しにする場合は `-SkipModels` を指定できます。その場合、音声認識や音の分類を使う前にモデルを用意してください。必要に応じて、利用するアプリの skill 読み込みを更新します。

実行環境、バイナリ、モデルの重み、ユーザーの動画・音声、個人の環境に固有のパスは、このリポジトリに含めていません。

## 使い方

エージェントには、例えば次のように依頼できます。

> bilibili-video-reader の skill でこの Bilibili 動画を調べてください。画面、原音声、音の変化を確認し、どの範囲を実際に確認したかも説明してください。

URL の部分を置き換えて、起動スクリプトを直接実行することもできます。

```powershell
pwsh -NoProfile -File "$skillDir\scripts\run_bilibili.ps1" `
  -Url "<Bilibili の URL>" -Mode full -OutDir ".\results"
```

| オプション | 用途 |
| --- | --- |
| `-Mode full` | 字幕、画像、原音声の認識、音の分析を行います。既定値です |
| `-Mode visual` | 抽出画像と画面変化の候補を確認します |
| `-Mode speech` | 原音声をローカルで文字起こしします |
| `-Mode sound` | 音楽や音の分類候補と音響的な変化を調べます |
| `-Mode subtitles` | 字幕などのテキストを取得します |
| `-FocusSeconds 12.5` | 指定した時刻の周辺を中心に画面を確認します |
| `-SourceMedia ".\media\video.mp4"` | 取得済みの動画を使います。ローカル入力なら URL は不要です |
| `-SpeechLanguage en` | 言語が分かっている場合に、自動判定の代わりに指定します |
| `-VerifySpeech` | 音声区間検出を使わない認識結果も作り、最初の結果と両方を残します |
| `-OutDir ".\results"` | 出力先を指定します |
| `-Doctor` | ローカルの実行環境が使える状態か確認します |

ダウンロードした動画は保持します。出力先は `summary.json` に記録されるため、追加の質問では `-SourceMedia` で再利用できます。

## 結果の確認

最初に `summary.json`（`schema_version: 2`）を開きます。各項目の `status` と、`metadata`、`download`、`subtitles`、`visual`、`speech`、`sound` の各段階を確認してください。一部だけ成功した場合は、その範囲を明示します。

プラットフォームの字幕は `subtitle_transcript_path`、原音声の認識結果は `speech_transcript_path` と `speech_result_path` に分かれています。時刻付きの `frames`、画面変化の `scene_candidates`、音の分析結果の `audio_timeline_path`、`event_tags_path`、`transient_candidates_path` も記録します。

**画面や音との対応を説明する前に、エージェントは対象の画像を実際に開いて確認する必要があります。** 画面変化の数値だけでは、その場面の内容は分かりません。確認した画像と原音声の結果を時刻で照合し、どこで映像と音が対応しているかを説明します。

## 制約と検証状況

既存の Windows 実行環境では実際の動画で動作を確認しました。公開用の初期設定スクリプトは静的チェックのみ実施しており、新規インストールと Claude Code 内での実行は利用先で検証してください。

- 画像は動画から一部を抽出したものです。特に長い動画や長さが不明な動画では、既定の処理だけで全編を確認したことにはなりません。
- 音声認識は機械による文字起こしで、人が一語ずつ確認した記録ではありません。音楽、歌声、合成音声、音の重なりによって、抜けや誤認識が起こります。
- YAMNet のスコアは分類候補です。楽器、音の発生源、曲名を確定するものではありません。短い音の変化を、すべて UI の通知音やクリック音と判断しないでください。
- 権限、字幕の有無、Bilibili 側のアクセス制限などで処理できない場合があります。ブラウザの Cookie を自動取得したり、アクセス制限を回避したりする機能はありません。
- 現在は Windows の `.exe` パスと PowerShell の起動スクリプトを使います。macOS・Linux 対応と Claude Code 内での動作は、別途検証が必要です。

エージェント向けの手順は [SKILL.md](SKILL.md)、[出力の説明](references/output-map.md)、[原音声と映像の確認手順](references/audio-visual-analysis.md)を参照してください。実行環境の詳細は [local-runtime.md](references/local-runtime.md)にあります。

## 出典とライセンス

このプロジェクトは [yichen11818/bilibili-video-reader](https://github.com/yichen11818/bilibili-video-reader) を基にしています。ローカルでの音声・映像処理とパッケージ構成は **PAN ZEHUI** が保守しています。

確認時点では、元のリポジトリに `LICENSE` ファイルはありませんでした。そのため、元のコードを含む全体に独自の MIT ライセンスを付与していません。外部ツールとモデルには、それぞれのライセンスが適用されます。実行時に取得するファイルは、このリポジトリでは再配布していません。
