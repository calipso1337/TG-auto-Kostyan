@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Устанавливаю yt-dlp...
py -m pip install -U yt-dlp
if errorlevel 1 (
  echo pypi.org недоступен, скачиваю официальный yt-dlp.exe с GitHub...
  powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe -OutFile yt-dlp.exe"
)
echo Устанавливаю Deno (нужен yt-dlp для YouTube)...
winget install --id DenoLand.Deno -e --accept-source-agreements --accept-package-agreements
echo Устанавливаю ffmpeg...
winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
echo.
echo Готово. Закрой это окно, заполни config.txt и запускай run.bat
pause
