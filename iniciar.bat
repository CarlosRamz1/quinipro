@echo off
rem QuiniPro en tu laptop: instala lo necesario, arranca el robot y la app, y abre el navegador.
chcp 65001 >nul
cd /d "%~dp0"
rem La base de datos vive fuera de OneDrive (SQLite y OneDrive no se llevan bien).
if not defined QUINIELA_DB set "QUINIELA_DB=%LOCALAPPDATA%\QuiniPro\quiniela.db"
if not exist "%LOCALAPPDATA%\QuiniPro" mkdir "%LOCALAPPDATA%\QuiniPro"
python -m pip install -q -r requirements.txt
start "QuiniPro - robot de datos" cmd /k python -m robot.main
timeout /t 2 >nul
start "" http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
