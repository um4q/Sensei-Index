@echo off
setlocal
title AuctionBot
cd /d "%~dp0"
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
%PY% -c "import openpyxl" >nul 2>nul
if errorlevel 1 (
    echo   Installing openpyxl...
    %PY% -m pip install --user --quiet openpyxl
    if errorlevel 1 set INSTALL_FAILED=1
)
REM Windows' own text reader, called directly (optional: falls back to PowerShell)
%PY% -c "import winrt.windows.media.ocr" >nul 2>nul
if errorlevel 1 (
    echo   Installing the Windows text-reader bridge ^(optional^)...
    %PY% -m pip install --user --quiet winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections
)
if "%INSTALL_FAILED%"=="1" (
    echo Couldn't install the required packages. Check your internet connection.
    pause
    exit /b 1
)
echo Starting AuctionBot...
echo  - Open the auction board in Roblox ^(Browse tab^), then press START or F8.
echo  - Don't touch the mouse while it scans.
%PY% auction_bot.py
if errorlevel 1 (
    echo AuctionBot closed with an error - see above.
    pause
)
