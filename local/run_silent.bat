@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist yt-dlp.exe (yt-dlp.exe -U) else (py -m pip install -U -q yt-dlp)
py clipper.py > last_run.txt 2>&1
