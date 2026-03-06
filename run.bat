@echo off
setlocal
chcp 65001 >nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

if "%~1"=="" (
  echo Usage: run.bat ^<video^> [extra args]
  echo Example: run.bat source.mp4 --no-burn
  exit /b 1
)

set VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe
if exist "%VENV_PY%" (
  "%VENV_PY%" auto_subtitle.py %*
) else (
  py -3 auto_subtitle.py %*
)
