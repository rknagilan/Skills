@echo off
cd /d "%~dp0"
:loop
py -3.12 autoclip.py
echo AutoClip stopped. Restarting in 30 seconds... (close this window to stop)
timeout /t 30 /nobreak >nul
goto loop
