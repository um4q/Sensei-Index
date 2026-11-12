@echo off
setlocal enabledelayedexpansion
title AutoFish
cd /d "%~dp0"

echo ============================================
echo   AutoFish - Setup and Launch
echo ============================================
echo.

REM --- 1. Make sure Python is installed ------------------------------------
python --version >nul 2>nul
if errorlevel 1 (
    echo Python isn't installed on this computer yet.
    echo.
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download and run the installer
    echo   3. On the FIRST screen, tick "Add python.exe to PATH"
    echo   4. Once that finishes, double-click this file again
    echo.
    pause
    exit /b 1
)

REM --- 2. Install missing packages (only the first time) --------------------
set INSTALL_FAILED=0

python -c "import numpy" >nul 2>nul
if errorlevel 1 (
    echo   Installing numpy...
    python -m pip install --user --quiet numpy
    if errorlevel 1 set INSTALL_FAILED=1
)
python -c "import mss" >nul 2>nul
if errorlevel 1 (
    echo   Installing mss...
    python -m pip install --user --quiet mss
    if errorlevel 1 set INSTALL_FAILED=1
)

if "%INSTALL_FAILED%"=="1" (
    echo.
    echo Couldn't install the required packages ^(numpy, mss^).
    echo Check your internet connection and run this file again.
    echo.
    pause
    exit /b 1
)

echo Starting AutoFish...
echo  - Stand at the water with your fishing rod out
echo  - Press START ^(or F6 while in Roblox^). F6 again stops it.
echo.

python autofish.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo   AutoFish closed with an error - see above.
    echo ============================================
    pause
)
