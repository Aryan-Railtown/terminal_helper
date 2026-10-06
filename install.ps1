# Installs sage for the current Windows user. Run from the repo folder:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# Installs uv if missing (uv also fetches Python 3.11 if needed), installs the `sage`
# command, and creates %USERPROFILE%\.sage\.env and config.toml from the examples.
# Safe to re-run: it upgrades sage and never overwrites your existing .env/config.

param(
    # Skip adding uv's tool folder to your user PATH (for CI/testing).
    [switch]$NoPathUpdate
)

$ErrorActionPreference = "Stop"
$repo = $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "Installing uv (Python package manager)..." -ForegroundColor Cyan
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

Write-Host "Installing sage..." -ForegroundColor Cyan
uv tool install --force --reinstall-package terminal-helper "$repo"
if ($LASTEXITCODE -ne 0) { throw "uv tool install failed" }
if (-not $NoPathUpdate) { uv tool update-shell | Out-Null }

$sageHome = if ($env:SAGE_HOME) { $env:SAGE_HOME } else { Join-Path $HOME ".sage" }
New-Item -ItemType Directory -Force $sageHome | Out-Null
$envFile = Join-Path $sageHome ".env"
$configFile = Join-Path $sageHome "config.toml"
if (-not (Test-Path $envFile)) { Copy-Item (Join-Path $repo ".env.example") $envFile }
if (-not (Test-Path $configFile)) { Copy-Item (Join-Path $repo "config.example.toml") $configFile }

Write-Host ""
Write-Host "sage is installed." -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Add your API key:   notepad `"$envFile`""
Write-Host "     (Gemini has a free tier: https://aistudio.google.com/apikey)"
Write-Host "  2. Open a NEW terminal, then check setup:   sage --debug"
Write-Host "  3. Ask something:      sage how do I find what is using port 3000"
