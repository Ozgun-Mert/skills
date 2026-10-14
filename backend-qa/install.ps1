# Installs this skill as /qa-backend for every project:
#   %USERPROFILE%\.claude\skills\qa-backend\
# Re-run after editing files in this repo (the repo is the source of truth).
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE ".claude\skills\qa-backend"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($item in @("SKILL.md", "references", "scripts", "templates")) {
    Copy-Item -Path (Join-Path $src $item) -Destination $dst -Recurse -Force
}
Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Keep the human-named copy in sync with SKILL.md
Copy-Item (Join-Path $src "SKILL.md") (Join-Path $src "qa-backend.md") -Force
Write-Host "Installed /qa-backend -> $dst (scripts use the Python standard library only; worker needs Claude Code >= 2.1.259)"
