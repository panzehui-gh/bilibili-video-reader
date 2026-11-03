[CmdletBinding()]
param(
    [string]$Url,
    [ValidateSet('full','visual','speech','sound','subtitles')][string]$Mode = 'full',
    [string]$OutDir,
    [string]$SourceMedia,
    [Nullable[double]]$FocusSeconds,
    [string]$SpeechLanguage,
    [int]$FrameCount = 12,
    [switch]$VerifySpeech,
    [switch]$Doctor
)
$ErrorActionPreference = 'Stop'
$skillRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $skillRoot 'runtime'
$runtimePython = Join-Path $runtimeRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    throw "Missing skill Python runtime: $runtimePython. See references/local-runtime.md."
}
$env:PATH = (Join-Path $runtimeRoot 'ffmpeg') + [IO.Path]::PathSeparator + $env:PATH
$pipelineArgs = @('-X', 'utf8', (Join-Path $PSScriptRoot 'analyze_bilibili.py'), '--runtime-dir', $runtimeRoot)
if ($Doctor) {
    $pipelineArgs += '--doctor'
} else {
    if (-not $Url -and -not $SourceMedia) { throw 'Provide -Url or -SourceMedia.' }
    if (-not $OutDir) { $OutDir = Join-Path (Get-Location).Path 'work\bilibili' }
    $pipelineArgs += @('--mode', $Mode, '--out-dir', $OutDir, '--frame-count', [string]$FrameCount)
    if ($Url) { $pipelineArgs += @('--url', $Url) }
    if ($SourceMedia) { $pipelineArgs += @('--source-media', $SourceMedia) }
    if ($null -ne $FocusSeconds) { $pipelineArgs += @('--focus-seconds', ([double]$FocusSeconds).ToString([Globalization.CultureInfo]::InvariantCulture)) }
    if ($SpeechLanguage) { $pipelineArgs += @('--speech-language', $SpeechLanguage) }
    if ($VerifySpeech) { $pipelineArgs += '--verify-speech' }
}
& $runtimePython @pipelineArgs
exit $LASTEXITCODE
