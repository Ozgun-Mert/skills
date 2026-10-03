# Installs this skill as /analyze-stock for every project:
#   %USERPROFILE%\.claude\skills\analyze-stock\
# Re-run after editing files in this repo (the repo is the source of truth).
$ErrorActionPreference = "Stop"
$src = $PSScriptRoot
$dst = Join-Path $env:USERPROFILE ".claude\skills\analyze-stock"
New-Item -ItemType Directory -Force $dst | Out-Null
foreach ($item in @("SKILL.md", "requirements.txt", "scripts", "references", "templates")) {
    Copy-Item -Path (Join-Path $src $item) -Destination $dst -Recurse -Force
}
Get-ChildItem -Path $dst -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
# Keep the human-named copy in sync with SKILL.md
Copy-Item (Join-Path $src "SKILL.md") (Join-Path $src "stock-analyzer.md") -Force
python -m pip install -q -r (Join-Path $dst "requirements.txt")
Write-Host "Installed /analyze-stock -> $dst"
