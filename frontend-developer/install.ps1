# Installs this skill as /develop-frontend for every project:
#   %USERPROFILE%\.claude\skills\develop-frontend\
# Re-run after editing files in this repo (the repo is the source of truth).
# Also installs Playwright + Chromium (the user/front review loop takes screenshots with it).
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE ".claude\skills\develop-frontend"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($item in @("SKILL.md", "design", "references", "scripts", "templates", "requirements.txt")) {
    Copy-Item -Path (Join-Path $src $item) -Destination $dst -Recurse -Force
}
Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Keep the human-named copy in sync with SKILL.md
Copy-Item (Join-Path $src "SKILL.md") (Join-Path $src "develop-frontend.md") -Force
python -m pip install -q -r (Join-Path $src "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Warning "pip install failed; run: python -m pip install playwright" }
python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { Write-Warning "Chromium download failed; run: python -m playwright install chromium" }
Write-Host "Installed /develop-frontend -> $dst (screenshots need Playwright + Chromium)"
