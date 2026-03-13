@echo off
setlocal
chcp 65001 >nul

set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

set VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe
if exist "%VENV_PY%" (
  "%VENV_PY%" -m webapp
) else (
  py -3 -m webapp
)
