#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DspRoot = (git rev-parse --show-toplevel),
    # Path to dsp-cli.py. Falls back to $env:DSP_CLI, then to auto-detection.
    [string]$DspCli = $env:DSP_CLI
)

$ErrorActionPreference = 'Stop'

$cliPath = $null
if ($DspCli -and (Test-Path $DspCli)) {
    $cliPath = $DspCli
} else {
    $candidates = @(
        (Join-Path $DspRoot ".cursor\skills\data-structure-protocol\scripts\dsp-cli.py"),
        (Join-Path $DspRoot ".claude\skills\data-structure-protocol\scripts\dsp-cli.py"),
        (Join-Path $DspRoot ".codex\skills\data-structure-protocol\scripts\dsp-cli.py"),
        (Join-Path $DspRoot "skills\data-structure-protocol\scripts\dsp-cli.py")
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $cliPath = $c
            break
        }
    }
}

if (-not $cliPath) {
    Write-Host "[DSP] CLI not found." -ForegroundColor Red
    exit 1
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[DSP] python not found in PATH." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path (Join-Path $DspRoot ".dsp"))) {
    Write-Host "[DSP] No .dsp\ directory found." -ForegroundColor Red
    exit 1
}

$trackableExtensions = @('.ts', '.tsx', '.js', '.jsx', '.py', '.go', '.rs', '.java', '.rb', '.vue', '.svelte')
$issues = 0

# find-by-source prints matching uids; on a miss it prints "not found" to
# stdout and exits 1, so both the output marker and emptiness must be checked.
function Test-DspTracked {
    param([string]$File)
    $result = & python $script:cliPath --root $script:DspRoot find-by-source $File
    $text = (@($result) -join "`n").Trim()
    return [bool]($text -and $text -notmatch 'not found')
}

Write-Host "[DSP] Checking staged files against DSP graph..."
Write-Host ""

$newFiles = @(git diff --cached --name-only --diff-filter=ACMR) | Where-Object { $_ -and $_.Trim() }
foreach ($file in $newFiles) {
    $file = $file.Trim()
    $ext = [System.IO.Path]::GetExtension($file)
    if ($ext -notin $trackableExtensions) { continue }

    if (Test-DspTracked $file) {
        Write-Host "[OK] $file" -ForegroundColor Green
    } else {
        Write-Host "[WARN] NEW/MODIFIED file not in DSP: $file" -ForegroundColor Yellow
        $issues++
    }
}

$deletedFiles = @(git diff --cached --name-only --diff-filter=D) | Where-Object { $_ -and $_.Trim() }
foreach ($file in $deletedFiles) {
    $file = $file.Trim()
    if (Test-DspTracked $file) {
        Write-Host "[ERR] DELETED file still in DSP: $file" -ForegroundColor Red
        $issues++
    }
}

$orphans = & python $cliPath --root $DspRoot get-orphans
$orphansText = (@($orphans) -join "`n").Trim()
if ($orphansText -and $orphansText -notmatch 'no orphans|0 orphan') {
    Write-Host ""
    Write-Host "[WARN] Orphaned DSP entities detected" -ForegroundColor Yellow
    $issues++
}

Write-Host ""
if ($issues -gt 0) {
    Write-Host "[DSP] Found $issues issue(s). Consider updating DSP before committing." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "[DSP] All staged files are consistent with DSP graph." -ForegroundColor Green
}
