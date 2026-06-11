#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DspRoot = ".",
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
    Write-Host "No dsp-cli.py found. Skipping agent review."
    exit 0
}

if (-not (Test-Path (Join-Path $DspRoot ".dsp"))) {
    Write-Host "No .dsp\ directory found. Skipping agent review."
    exit 0
}

# Prefer the staged diff; fall back to the last commit (post-commit review).
$diff = git diff --staged
if (-not $diff) { $diff = git diff HEAD~1 }
if (-not $diff) {
    Write-Host "No changes to review."
    exit 0
}

$stagedFiles = @(git diff --cached --name-only --diff-filter=ACMRD)
if (-not $stagedFiles) {
    $stagedFiles = @(git diff HEAD~1 --name-only --diff-filter=ACMRD)
}

$dspContext = ""
foreach ($file in $stagedFiles) {
    $file = "$file".Trim()
    if (-not $file) { continue }

    # find-by-source prints "not found" to stdout (exit 1) on a miss.
    $entity = & python $cliPath --root $DspRoot find-by-source $file
    $entityText = (@($entity) -join "`n").Trim()
    if ($entityText -and $entityText -notmatch 'not found') {
        $uid = [regex]::Match($entityText, '(obj|func)-[a-f0-9]{8}').Value
        if ($uid) {
            $entityInfo = & python $cliPath --root $DspRoot get-entity $uid
            $entityInfoText = (@($entityInfo) -join "`n")
            $dspContext += "=== DSP entity for $file ($uid) ===`n$entityInfoText`n`n"
        }
    } else {
        $dspContext += "=== $file - NOT in DSP ===`n`n"
    }
}

$stats = (@(& python $cliPath --root $DspRoot get-stats) -join "`n")
$orphans = (@(& python $cliPath --root $DspRoot get-orphans) -join "`n")

$reviewFile = Join-Path $env:TEMP "dsp-review-$([guid]::NewGuid().ToString('N').Substring(0,8)).md"

@"
# DSP Consistency Review Request

## Git Diff

``````diff
$($diff -join "`n")
``````

## DSP State for Affected Files

$dspContext

## Project Stats

$stats

## Current Orphans

$orphans

## Review Instructions

Check all items from the DSP consistency review checklist.
For each issue found, provide the exact dsp-cli command to fix it.
"@ | Set-Content -Path $reviewFile -Encoding UTF8

Write-Host ""
Write-Host "Review context saved to: $reviewFile" -ForegroundColor Cyan
Write-Host ""
Write-Host "Send this to your agent for review:"
Write-Host "  Get-Content $reviewFile | Set-Clipboard"
Write-Host ""
Write-Host "Or pipe to agent CLI directly."
