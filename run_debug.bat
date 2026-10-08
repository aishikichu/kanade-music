@echo off
title Kanade [Debug Console]
cd /d "%~dp0"

echo Launching Kanade with debug output...
".venv\Scripts\python.exe" main.py
pause
