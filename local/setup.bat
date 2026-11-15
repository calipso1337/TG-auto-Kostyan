@echo off
chcp 65001 >nul
echo Устанавливаю yt-dlp и ffmpeg...
py -m pip install -U yt-dlp
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
echo.
echo Готово. Закрой это окно, заполни config.txt и запускай run.bat
pause
