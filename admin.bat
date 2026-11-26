@echo off
rem Comandos de administración con la misma base de datos que usa iniciar.bat
rem   admin.bat super "Tu Nombre"
rem   admin.bat codigo "Grupo de mi hermano"
rem   admin.bat enlace 1
rem   admin.bat demo
chcp 65001 >nul
cd /d "%~dp0"
if not defined QUINIELA_DB set "QUINIELA_DB=%LOCALAPPDATA%\QuiniPro\quiniela.db"
if not exist "%LOCALAPPDATA%\QuiniPro" mkdir "%LOCALAPPDATA%\QuiniPro"
python -m app.admin %*
