@echo off
cd /d "%~dp0"
call .venv\Scripts\activate.bat
powershell -NoExit -Command "Write-Host '(.venv) quarry-compliance — ready' -ForegroundColor Green"
