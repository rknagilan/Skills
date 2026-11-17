# Installs 3 free GTA 6 / stream clipping apps on Windows:
#   1. Cutawan     (desktop app, MIT)            https://github.com/JeremySNR/cutawan
#   2. SupoClip    (web app in Docker, AGPL-3.0) https://github.com/FujiwaraChoki/supoclip
#   3. Clips Kitty (desktop app)                 https://colingpt9-clips-studio.static.hf.space/
# Run in PowerShell:
#   irm https://raw.githubusercontent.com/rknagilan/skills/ccr-21cbc605-g8n41d/install-clipping-apps-windows.ps1 | iex
$ErrorActionPreference = "Continue"
$ProgressPreference = "SilentlyContinue"   # the progress bar makes downloads very slow in Windows PowerShell
$Apps = Join-Path $env:USERPROFILE "ClippingApps"
New-Item -ItemType Directory -Force -Path $Apps | Out-Null

# ---------- 1. Cutawan ----------
Write-Host "1/3 Cutawan: downloading the latest Windows installer..." -ForegroundColor Yellow
try {
  $rel = Invoke-RestMethod "https://api.github.com/repos/JeremySNR/cutawan/releases/latest" -Headers @{ "User-Agent" = "installer" }
  $asset = $rel.assets | Where-Object { $_.name -like "*.exe" } | Select-Object -First 1
  if ($asset) {
    $exe = Join-Path $Apps $asset.name
    Invoke-WebRequest $asset.browser_download_url -OutFile $exe
    Write-Host "   Running $($asset.name) ($($rel.tag_name))..." -ForegroundColor Cyan
    Start-Process $exe -Wait
    Write-Host "   Cutawan installed." -ForegroundColor Green
  } else {
    Write-Host "   No .exe in the latest release. Open: https://github.com/JeremySNR/cutawan/releases" -ForegroundColor DarkYellow
  }
} catch { Write-Host "   Cutawan failed: $_  -> download by hand: https://github.com/JeremySNR/cutawan/releases" -ForegroundColor Red }

# ---------- 2. SupoClip ----------
Write-Host "2/3 SupoClip: needs Docker Desktop + API keys" -ForegroundColor Yellow
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
  $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Write-Host "   Installing Docker Desktop (restart the PC after this)..." -ForegroundColor Cyan
  winget install -e --id Docker.DockerDesktop --accept-source-agreements --accept-package-agreements
}
$sc = Join-Path $Apps "supoclip"
if (-not (Test-Path $sc)) { git clone -q --depth 1 https://github.com/FujiwaraChoki/supoclip.git $sc }
Write-Host "   SupoClip downloaded to $sc" -ForegroundColor Green
Write-Host "   To start it: put your AssemblyAI key + one AI key (Google/OpenAI/Anthropic) in the .env file" -ForegroundColor Green
Write-Host "   (see README.md in that folder), then run:  cd $sc ; docker compose up -d" -ForegroundColor Green

# ---------- 3. Clips Kitty ----------
Write-Host "3/3 Clips Kitty: opening the download page (Windows / Microsoft Store)..." -ForegroundColor Yellow
Start-Process "https://colingpt9-clips-studio.static.hf.space/"
Write-Host "   Click the Windows download or Microsoft Store button on that page." -ForegroundColor Green

Write-Host ""
Write-Host "DONE. Apps folder: $Apps" -ForegroundColor Green
