@echo off
chcp 65001 >nul
cd /d "%~dp0"
schtasks /create /tn "BrawlClipper" /tr "\"%~dp0run_silent.bat\"" /sc daily /st 12:00 /f
echo Каждый день в 12:00 будет запускаться нарезка, если компьютер включён.
pause
