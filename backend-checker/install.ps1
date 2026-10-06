# Installs every backend-checker skill (/check-backend-security, /check-backend-code-quality,
# /check-backend-health and any check added later under skills/) for every project:
#   %USERPROFILE%\.claude\skills\<skill-name>\  (SKILL.md + a copy of core/)
# Re-run after editing files in this repo (the repo is the source of truth).
# -Destination lets you stage the skills somewhere else (used by the evals).
param([string]$Destination = (Join-Path $env:USERPROFILE ".claude\skills"))
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$core = Join-Path $src "core"
New-Item -ItemType Directory -Force $Destination | Out-Null
foreach ($skill in Get-ChildItem -Path (Join-Path $src "skills") -Directory) {
    $dst = Join-Path $Destination $skill.Name
    if (Test-Path (Join-Path $dst "core")) { Remove-Item -Recurse -Force (Join-Path $dst "core") }
    New-Item -ItemType Directory -Force $dst | Out-Null
    Copy-Item -Path (Join-Path $skill.FullName "*") -Destination $dst -Recurse -Force
    Copy-Item -Path $core -Destination $dst -Recurse -Force
    Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
    Write-Host "Installed /$($skill.Name) -> $dst"
}
Write-Host "Done. Scripts use the Python standard library only. Start a new Claude Code session to pick up the commands."
