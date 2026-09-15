@echo off
setlocal

cd /d "%~dp0"

where pythonw >nul 2>nul
if errorlevel 1 (
    echo Python isn't installed, or isn't on PATH.
    echo Install it from https://www.python.org/downloads/ and check
    echo "Add python.exe to PATH" during setup, then run this again.
    pause
    exit /b 1
)

python -c "import PySide6" >nul 2>nul
if errorlevel 1 (
    echo First run - installing required packages, one moment...
    python -m pip install --user --quiet PySide6 openpyxl pypdf reportlab
)

start "" pythonw "%~dp0bootstrap.py"
