@echo off
setlocal enabledelayedexpansion
title AutoFish
cd /d "%~dp0"

echo ============================================
echo   AutoFish - Setup and Launch
echo ============================================
echo.

REM --- find Python: "python", then the "py" launcher, then the usual folders ---
set "PY="
python -c "import sys" >nul 2>nul && set "PY=python"
if not defined PY ( py -3 -c "import sys" >nul 2>nul && set "PY=py -3" )
if not defined PY (
    for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
)
if not defined PY (
    for /d %%D in ("%ProgramFiles%\Python3*") do if exist "%%D\python.exe" set "PY="%%D\python.exe""
)
if not defined PY (
    echo Couldn't find Python on this computer.
    echo.
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download and run the installer
    echo   3. On the FIRST screen, tick "Add python.exe to PATH"
    echo   4. Once that finishes, double-click this file again
    echo.
    pause
    exit /b 1
)
echo Using Python: %PY%

set INSTALL_FAILED=0

%PY% -c "import numpy" >nul 2>nul
if errorlevel 1 (
    echo   Installing numpy...
    %PY% -m pip install --user --quiet numpy
    if errorlevel 1 set INSTALL_FAILED=1
)
%PY% -c "import mss" >nul 2>nul
if errorlevel 1 (
    echo   Installing mss...
    %PY% -m pip install --user --quiet mss
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

%PY% autofish.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo   AutoFish closed with an error - see above.
    echo ============================================
    pause
)
