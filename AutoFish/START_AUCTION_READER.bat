@echo off
setlocal
title AuctionReader
cd /d "%~dp0"
python --version >nul 2>nul
if errorlevel 1 (
    echo Python isn't installed - see README.txt ^(same as AutoFish^).
    pause
    exit /b 1
)
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
python -c "import openpyxl" >nul 2>nul
if errorlevel 1 (
    echo   Installing openpyxl...
    python -m pip install --user --quiet openpyxl
    if errorlevel 1 set INSTALL_FAILED=1
)
if "%INSTALL_FAILED%"=="1" (
    echo Couldn't install the required packages. Check your internet connection.
    pause
    exit /b 1
)
echo Starting AuctionReader...
echo  - Open the auction board in Roblox ^(Browse tab^), then press START or F7.
echo  - Don't touch the mouse while it scans.
python auction_reader.py
if errorlevel 1 (
    echo AuctionReader closed with an error - see above.
    pause
)
