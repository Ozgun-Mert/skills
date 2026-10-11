# Installs this skill as /make-no-mistakes for every project:
#   %USERPROFILE%\.claude\skills\make-no-mistakes\
# Re-run after editing files in this repo (the repo is the source of truth).
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE ".claude\skills\make-no-mistakes"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($item in @("SKILL.md", "references", "scripts", "templates")) {
    Copy-Item -Path (Join-Path $src $item) -Destination $dst -Recurse -Force
}
Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Keep the human-named copy in sync with SKILL.md
Copy-Item (Join-Path $src "SKILL.md") (Join-Path $src "make-no-mistakes.md") -Force
Write-Host "Installed /make-no-mistakes -> $dst (scripts use the Python standard library only; needs Claude Code >= 2.1.259)"
