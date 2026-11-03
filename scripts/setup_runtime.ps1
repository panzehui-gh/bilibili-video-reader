[CmdletBinding()]
param(
    [string]$Python = 'python',
    [switch]$SkipModels
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSVersion.Major -lt 7 -or -not $IsWindows -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'This setup script currently requires PowerShell 7 on Windows x64.'
}
$skillRoot = Split-Path -Parent $PSScriptRoot
$runtimeRoot = Join-Path $skillRoot 'runtime'
$runtimePython = Join-Path $runtimeRoot 'venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython)) {
    & $Python -c 'import sys; print(sys.version)'
    if ($LASTEXITCODE -ne 0) { throw 'Provide a working Python executable with -Python. The validated environment uses Python 3.14 x64.' }
    & $Python -m venv (Join-Path $runtimeRoot 'venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
}
& $runtimePython -m pip install --disable-pip-version-check --only-binary=:all: -r (Join-Path $PSScriptRoot 'requirements-local.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed; check the selected Python version and network access.' }
$assetArgs = @('-X', 'utf8', (Join-Path $PSScriptRoot 'fetch_runtime.py'), '--runtime-dir', $runtimeRoot)
if ($SkipModels) { $assetArgs += '--skip-models' }
& $runtimePython @assetArgs
if ($LASTEXITCODE -ne 0) { throw 'Runtime asset preparation failed; inspect the reported error.' }
if ($SkipModels) {
    Write-Output 'Model downloads deferred. Run setup again without -SkipModels before speech/sound analysis.'
} else {
    & (Join-Path $PSScriptRoot 'run_bilibili.ps1') -Doctor
    if ($LASTEXITCODE -ne 0) { throw 'Runtime readiness check failed.' }
}
