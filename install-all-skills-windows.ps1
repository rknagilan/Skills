# Installs ALL skills from this repo on your Windows PC, for every project (~\.claude\skills).
# Run in PowerShell:
#   irm https://raw.githubusercontent.com/rknagilan/skills/ccr-21cbc605-g8n41d/install-all-skills-windows.ps1 | iex
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Branch = "ccr-21cbc605-g8n41d"
$Repo   = "https://github.com/rknagilan/skills.git"
$Home2  = Join-Path $env:USERPROFILE "AutoClip"
$Target = Join-Path $env:USERPROFILE ".claude\skills"

function Need($cmd, $id) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Write-Host "Installing $cmd ..." -ForegroundColor Cyan
    winget install -e --id $id --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
  }
}

Write-Host "Step 1/4: Git and Node.js" -ForegroundColor Yellow
Need git  Git.Git
Need node OpenJS.NodeJS.LTS

Write-Host "Step 2/4: Download the skills repo to $Home2" -ForegroundColor Yellow
if (Test-Path (Join-Path $Home2 ".git")) {
  git -C $Home2 fetch -q origin $Branch
  git -C $Home2 checkout -q $Branch
  git -C $Home2 pull -q origin $Branch
} else {
  git clone -q -b $Branch $Repo $Home2
}

Write-Host "Step 3/4: Copy skills to $Target" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$src = Join-Path $Home2 ".claude\skills"
Get-ChildItem $src -Directory | ForEach-Object {
  Copy-Item $_.FullName -Destination $Target -Recurse -Force
}

Write-Host "Step 4/4: Extra skills (upload-post, twitch-clips)" -ForegroundColor Yellow
Push-Location $env:USERPROFILE
try { npx -y skills add Upload-Post/upload-post-skill --agent claude-code -g -y } catch { Write-Host "upload-post: install later with: npx skills add Upload-Post/upload-post-skill -g" -ForegroundColor DarkYellow }
Pop-Location
$tmp = Join-Path $env:TEMP ("tc-" + [guid]::NewGuid())
git clone -q --depth 1 https://github.com/NikitaPPP017/twitch-clips.git $tmp
Copy-Item (Join-Path $tmp ".claude\skills\twitch-clips") -Destination $Target -Recurse -Force

$n = (Get-ChildItem $Target -Directory).Count
Write-Host ""
Write-Host "DONE! $n skills installed in $Target" -ForegroundColor Green
Write-Host "Open a NEW PowerShell, type 'claude', then '/skills' to see them." -ForegroundColor Green
Write-Host "AutoClip files are in $Home2\autoclip (read GUIDE-TAMIL.md)." -ForegroundColor Green
