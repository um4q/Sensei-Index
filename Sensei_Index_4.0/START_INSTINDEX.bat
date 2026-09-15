::[Bat To Exe Converter]
::
::YAwzoRdxOk+EWAjk
::fBw5plQjdCyDJGyX8VAjFCJVQgCDf1eeCaIS5Of66/m7kUgTR+c2R6bV3rGWH7Fds3nXcJg+03MascUICQMYL1zyUg4numtWpViKNtOUowPgXk2B40c9VWx3iAM=
::YAwzuBVtJxjWCl3EqQJgSA==
::ZR4luwNxJguZRRnk
::Yhs/ulQjdF+5
::cxAkpRVqdFKZSDk=
::cBs/ulQjdF+5
::ZR41oxFsdFKZSDk=
::eBoioBt6dFKZSDk=
::cRo6pxp7LAbNWATEpCI=
::egkzugNsPRvcWATEpCI=
::dAsiuh18IRvcCxnZtBJQ
::cRYluBh/LU+EWAnk
::YxY4rhs+aU+JeA==
::cxY6rQJ7JhzQF1fEqQJQ
::ZQ05rAF9IBncCkqN+0xwdVs0
::ZQ05rAF9IAHYFVzEqQJQ
::eg0/rx1wNQPfEVWB+kM9LVsJDGQ=
::fBEirQZwNQPfEVWB+kM9LVsJDGQ=
::cRolqwZ3JBvQF1fEqQJQ
::dhA7uBVwLU+EWDk=
::YQ03rBFzNR3SWATElA==
::dhAmsQZ3MwfNWATElA==
::ZQ0/vhVqMQ3MEVWAtB9wSA==
::Zg8zqx1/OA3MEVWAtB9wSA==
::dhA7pRFwIByZRRnk
::Zh4grVQjdCyDJGyX8VAjFCJVQgCDf1eeCaIS5Of66/m7kUgTR+c2R6bV3rGWH7Fds3nXcJg+03MascUICQMYL1zyUjwxp31HvySsOcOZq0+wBBHH41M1ew==
::YB416Ek+Zm8=
::
::
::978f952a14a936cc963da21a135fa983
@echo off
setlocal enabledelayedexpansion
title Sensei Index 1.9
cd /d "%~dp0"

echo ============================================
echo   Sensei Index 1.9 - Setup and Launch
echo ============================================
echo Experimental build Programs a little scuffed
echo Only used for one-time edits and fast Index --> ITR document converts
echo and tracking too...
echo.

REM --- 0. Warn early if this folder needs admin rights to write to --------
REM Program Files (and Program Files (x86)) need elevation to write into -
REM and this app saves the workbook, settings, and series list right next
REM to itself on every single edit. Better to say so now than have every
REM save silently need "Run as administrator" later.
echo %CD% | findstr /i "Program Files" >nul
if not errorlevel 1 (
    echo WARNING: This folder is inside Program Files, which normally needs
    echo administrator rights to write to - and InstINDEX needs to save its
    echo own data ^(the workbook, settings, series list^) right next to
    echo itself every time you edit something.
    echo.
    echo Recommended: close this, move the whole InstINDEX folder to
    echo somewhere any account can write to without admin - for example:
    echo     C:\Users\Public\InstINDEX
    echo or just your Desktop or Documents - then run this file from there.
    echo.
    echo Continuing anyway in 5 seconds ^(Ctrl+C to stop^)...
    timeout /t 5 >nul
    echo.
)

REM --- 1. Make sure Python itself is installed ----------------------------
python --version >nul 2>nul
if errorlevel 1 (
    echo Python isn't installed on this computer yet - that's the one thing
    echo this file can't do for you automatically.
    echo.
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download and run the installer
    echo   3. On the FIRST screen, tick "Add python.exe to PATH" before
    echo      clicking Install - this step is easy to miss and required
    echo   4. Once that finishes, double-click this file again
    echo.
    pause
    exit /b 1
)

REM --- 2. Install any missing packages (skips ones already present) ------
REM --user installs into this Windows account's own package folder rather
REM than the shared, admin-protected one - so this never needs elevation,
REM even if Python itself was installed "for all users."
echo Checking required packages - First-time setup only, again it takes minute...
echo.

set INSTALL_FAILED=0

python -m pip show PySide6 >nul 2>nul
if errorlevel 1 (
    echo   Installing PySide6...
    python -m pip install --user --quiet PySide6
    if errorlevel 1 set INSTALL_FAILED=1
)
python -m pip show openpyxl >nul 2>nul
if errorlevel 1 (
    echo   Installing openpyxl...
    python -m pip install --user --quiet openpyxl
    if errorlevel 1 set INSTALL_FAILED=1
)
python -m pip show pypdf >nul 2>nul
if errorlevel 1 (
    echo   Installing pypdf...
    python -m pip install --user --quiet pypdf
    if errorlevel 1 set INSTALL_FAILED=1
)
python -m pip show reportlab >nul 2>nul
if errorlevel 1 (
    echo   Installing reportlab...
    python -m pip install --user --quiet reportlab
    if errorlevel 1 set INSTALL_FAILED=1
)

if "%INSTALL_FAILED%"=="1" (
    echo.
    echo ============================================
    echo   Couldn't install one or more required packages.
    echo ============================================
    echo This normally isn't an admin-rights problem - --user installs
    echo don't need elevation - it's more commonly no internet connection,
    echo or a company network blocking pip. Try running this file again,
    echo or ask IT whether pypi.org is reachable from this machine.
    echo.
    pause
    exit /b 1
)

echo.
echo Starting InstINDEX...
echo First launch takes a minute, please be patient... 
echo  -GIM MD/G0NCHO
echo.

python gui_app.py

if errorlevel 1 (
    echo.
    echo ============================================
    echo   Sensei Index crashed with an error - see above.
    echo ============================================
    pause
)
