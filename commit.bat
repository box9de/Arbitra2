@echo off
git add .
git commit -m "%~1"
git push
echo.
echo ✅ Коммит выполнен и отправлен на GitHub
pause