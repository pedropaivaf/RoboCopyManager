@echo off
title RoboCopy Manager
cd /d "%~dp0"
if exist "%~dp0dist\RoboCopyManager.exe" (
    start "" "%~dp0dist\RoboCopyManager.exe"
    exit /b
)
if exist "%~dp0RoboCopyManager.exe" (
    start "" "%~dp0RoboCopyManager.exe"
    exit /b
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0RoboCopy.ps1"
