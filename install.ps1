#Requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateSet('cursor', 'claude', 'codex', 'all')]
    [string[]]$Agent = @('all'),

    [switch]$Global,

    [string]$Branch = 'main'
)

$ErrorActionPreference = 'Stop'
$DSP_REPO = 'k-kolomeitsev/data-structure-protocol'
$DSP_SKILL_PATH = 'skills/data-structure-protocol'

function Get-TargetPath {
    param([string]$AgentName)

    if ($Global) {
        switch ($AgentName) {
            'cursor' { return Join-Path $HOME '.cursor/skills/data-structure-protocol' }
            'claude' { return Join-Path $HOME '.claude/skills/data-structure-protocol' }
            'codex'  { return Join-Path $HOME '.codex/skills/data-structure-protocol' }
        }
    } else {
        switch ($AgentName) {
            'cursor' { return '.cursor/skills/data-structure-protocol' }
            'claude' { return '.claude/skills/data-structure-protocol' }
            'codex'  { return '.codex/skills/data-structure-protocol' }
        }
    }
}

function Install-ForAgent {
    param([string]$AgentName)

    $target = Get-TargetPath $AgentName
    Write-Host "=> Installing DSP skill for $AgentName => $target"

    New-Item -ItemType Directory -Force -Path $target | Out-Null

    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) "dsp-install-$([guid]::NewGuid().ToString('N').Substring(0,8))"
    $zipPath = "$tmp.zip"

    try {
        Invoke-WebRequest -Uri "https://github.com/$DSP_REPO/archive/$Branch.zip" `
            -OutFile $zipPath -UseBasicParsing

        Expand-Archive -Path $zipPath -DestinationPath $tmp -Force

        $extractedRoot = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
        $sourcePath = Join-Path $extractedRoot.FullName $DSP_SKILL_PATH

        if (-not (Test-Path $sourcePath)) {
            throw "Skill folder not found at $sourcePath"
        }

        Copy-Item -Path "$sourcePath\*" -Destination $target -Recurse -Force
        Write-Host "[OK] DSP skill installed for $AgentName" -ForegroundColor Green
    }
    finally {
        if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    }
}

Write-Host ""
Write-Host "DSP Skill Installer" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan
Write-Host ""

$resolvedAgents = if ($Agent -contains 'all') { @('cursor', 'claude', 'codex') } else { $Agent }

foreach ($a in $resolvedAgents) {
    Install-ForAgent $a
}

Write-Host ""
Write-Host "Done! Restart your agent/IDE to pick up the new skill." -ForegroundColor Green
Write-Host ""
