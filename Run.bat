@echo off
title RoboCopy Manager
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RoboCopy.ps1"
if %ERRORLEVEL% neq 0 (
    echo.
    echo Pressione qualquer tecla para fechar...
    pause >nul
)
