@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo  Subtitle Pipeline - One-Click Setup
echo ========================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
if errorlevel 1 (
    echo.
    echo [error] setup failed
    pause
    exit /b 1
)

echo.
echo [ok] setup complete
pause
