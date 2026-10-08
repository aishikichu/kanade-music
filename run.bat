@echo off
title Kanade - Hi-Res Lossless Downloader
cd /d "%~dp0"

echo =======================================================
echo   Kanade 奏: Hi-Res Lossless Downloader ^& Studio Tagger
echo =======================================================
echo Launching native desktop application...
echo.

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\pythonw.exe" main.py
) else (
    echo [ERROR] Virtual environment not found. Running with system python...
    start "" pythonw main.py
)

exit
