# AutoClip installer for Windows. Right-click this file > "Run with PowerShell".
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Write-Host "1/5 Installing tools (Python, ffmpeg, yt-dlp, Node.js, Git)..." -ForegroundColor Cyan
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements
winget install -e --id yt-dlp.yt-dlp --accept-source-agreements --accept-package-agreements
winget install -e --id OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements
winget install -e --id Git.Git --accept-source-agreements --accept-package-agreements
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")

Write-Host "2/5 Installing Claude Code..." -ForegroundColor Cyan
if (-not (Get-Command claude -ErrorAction SilentlyContinue)) { irm https://claude.ai/install.ps1 | iex }

Write-Host "3/5 Python packages for the clipping skill..." -ForegroundColor Cyan
py -3.12 -m pip install --upgrade pip faster-whisper opencv-python pillow numpy

Write-Host "4/5 Creating config.json with private phone topics..." -ForegroundColor Cyan
if (-not (Test-Path config.json)) {
  $cfg = Get-Content config.example.json -Raw | ConvertFrom-Json
  $rand = -join ((48..57) + (97..122) | Get-Random -Count 16 | ForEach-Object {[char]$_})
  $cfg.ntfy_topic = "autoclip-$rand"
  $cfg.ntfy_reply_topic = "autoclip-$rand-reply"
  $cfg | ConvertTo-Json | Set-Content config.json -Encoding UTF8
}
$c = Get-Content config.json -Raw | ConvertFrom-Json
Write-Host ""
Write-Host "5/5 DONE. In the ntfy phone app, subscribe to this topic:" -ForegroundColor Green
Write-Host "      $($c.ntfy_topic)" -ForegroundColor Yellow
Write-Host "Next: run 'claude' once and log in, then edit config.json + streamers.json (see GUIDE-TAMIL.md)."
