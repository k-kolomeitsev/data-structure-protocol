#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DspCli = "python .cursor\skills\data-structure-protocol\scripts\dsp-cli.py",
    [string]$DspRoot = "."
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path "$DspRoot\.dsp")) {
    Write-Host "No .dsp\ directory found. Skipping agent review."
    exit 0
}

$diff = git diff --staged 2>$null
if (-not $diff) { $diff = git diff HEAD~1 }
if (-not $diff) {
    Write-Host "No changes to review."
    exit 0
}

$stagedFiles = (git diff --cached --name-only --diff-filter=ACMRD 2>$null)
if (-not $stagedFiles) {
    $stagedFiles = (git diff HEAD~1 --name-only --diff-filter=ACMRD)
}

$dspContext = ""
foreach ($file in $stagedFiles -split "`n") {
    $file = $file.Trim()
    if (-not $file) { continue }

    $entity = & cmd /c "$DspCli --root $DspRoot find-by-source `"$file`"" 2>$null
    if ($entity) {
        $uid = [regex]::Match($entity, '(obj|func)-[a-f0-9]{8}').Value
        if ($uid) {
            $entityInfo = & cmd /c "$DspCli --root $DspRoot get-entity $uid" 2>$null
            $dspContext += "=== DSP entity for $file ($uid) ===`n$entityInfo`n`n"
        }
    } else {
        $dspContext += "=== $file - NOT in DSP ===`n`n"
    }
}

$stats = & cmd /c "$DspCli --root $DspRoot get-stats" 2>$null
$orphans = & cmd /c "$DspCli --root $DspRoot get-orphans" 2>$null

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
