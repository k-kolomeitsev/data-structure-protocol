#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$DspRoot = (git rev-parse --show-toplevel)
)

$ErrorActionPreference = 'Stop'

$dspCli = $null
$candidates = @(
    "$DspRoot\.cursor\skills\data-structure-protocol\scripts\dsp-cli.py",
    "$DspRoot\.claude\skills\data-structure-protocol\scripts\dsp-cli.py",
    "$DspRoot\.codex\skills\data-structure-protocol\scripts\dsp-cli.py",
    "$DspRoot\skills\data-structure-protocol\scripts\dsp-cli.py"
)

foreach ($c in $candidates) {
    if (Test-Path $c) {
        $dspCli = "python $c"
        break
    }
}

if (-not $dspCli) {
    Write-Host "[DSP] CLI not found." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$DspRoot\.dsp")) {
    Write-Host "[DSP] No .dsp\ directory found." -ForegroundColor Red
    exit 1
}

$trackableExtensions = @('.ts', '.tsx', '.js', '.jsx', '.py', '.go', '.rs', '.java', '.rb', '.vue', '.svelte')
$issues = 0

Write-Host "[DSP] Checking staged files against DSP graph..."
Write-Host ""

$newFiles = (git diff --cached --name-only --diff-filter=ACMR) -split "`n" | Where-Object { $_.Trim() }
foreach ($file in $newFiles) {
    $ext = [System.IO.Path]::GetExtension($file)
    if ($ext -notin $trackableExtensions) { continue }

    $result = & cmd /c "$dspCli --root $DspRoot find-by-source `"$file`"" 2>$null
    if (-not $result) {
        Write-Host "⚠ NEW/MODIFIED file not in DSP: $file" -ForegroundColor Yellow
        $issues++
    } else {
        Write-Host "✓ $file" -ForegroundColor Green
    }
}

$deletedFiles = (git diff --cached --name-only --diff-filter=D) -split "`n" | Where-Object { $_.Trim() }
foreach ($file in $deletedFiles) {
    $result = & cmd /c "$dspCli --root $DspRoot find-by-source `"$file`"" 2>$null
    if ($result) {
        Write-Host "✗ DELETED file still in DSP: $file" -ForegroundColor Red
        $issues++
    }
}

$orphans = & cmd /c "$dspCli --root $DspRoot get-orphans" 2>$null
if ($orphans -and $orphans -notmatch "No orphans|0 orphan") {
    Write-Host ""
    Write-Host "⚠ Orphaned DSP entities detected" -ForegroundColor Yellow
    $issues++
}

Write-Host ""
if ($issues -gt 0) {
    Write-Host "[DSP] Found $issues issue(s). Consider updating DSP before committing." -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "[DSP] All staged files are consistent with DSP graph." -ForegroundColor Green
}
