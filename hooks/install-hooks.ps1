#Requires -Version 5.1

$hooksDir = Join-Path (git rev-parse --git-dir) "hooks"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "Installing DSP git hooks..."

Copy-Item (Join-Path $scriptDir "pre-commit") (Join-Path $hooksDir "pre-commit") -Force
Copy-Item (Join-Path $scriptDir "pre-push") (Join-Path $hooksDir "pre-push") -Force

Write-Host "[OK] DSP git hooks installed" -ForegroundColor Green
Write-Host ""
Write-Host "Configuration (environment variables):"
Write-Host "  DSP_PRECOMMIT_MODE=warn|block  (default: warn)"
Write-Host "  DSP_CLI=<path-to-dsp-cli.py>   (auto-detected)"
Write-Host "  DSP_SKIP_PATTERNS=<glob,...>    (files to skip)"
