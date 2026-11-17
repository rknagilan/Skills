@echo off
rem MontClipper launcher for Windows Terminal, PowerShell or Command Prompt.
set "H=%MONTCLIPPER_HOME%"
if "%H%"=="" set "H=%USERPROFILE%\MontClipper"
set "MONTCLIPPER_HOME=%H%"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
"%H%\tools-audio\Scripts\python.exe" "%~dp0mc.py" %*
