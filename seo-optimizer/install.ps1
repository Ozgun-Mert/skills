# Installs this skill as /optimize-seo for every project:
#   %USERPROFILE%\.claude\skills\optimize-seo\
# Re-run after editing files in this repo (the repo is the source of truth).
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE ".claude\skills\optimize-seo"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($item in @("SKILL.md", "scripts", "references")) {
    Copy-Item -Path (Join-Path $src $item) -Destination $dst -Recurse -Force
}
Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Keep the human-named copy in sync with SKILL.md
Copy-Item (Join-Path $src "SKILL.md") (Join-Path $src "seo-optimizer.md") -Force
Write-Host "Installed /optimize-seo -> $dst (scripts use the Python standard library only)"
