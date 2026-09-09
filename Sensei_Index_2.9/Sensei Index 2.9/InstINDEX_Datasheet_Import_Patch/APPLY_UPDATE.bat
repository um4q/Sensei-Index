@echo off
setlocal enabledelayedexpansion
title InstINDEX - Import Datasheet PDF - Update Patch

echo ============================================================
echo  InstINDEX - Import Datasheet PDF - Update Patch
echo ============================================================
echo.

set "PATCH_DIR=%~dp0"
set "TARGET_DIR=%PATCH_DIR%.."
set "FILES_DIR=%PATCH_DIR%_patch_files"
set "BACKUP_DIR=%TARGET_DIR%\_backup_before_datasheet_import_patch"

if not exist "%TARGET_DIR%\gui_app.py" (
    echo ERROR: Couldn't find gui_app.py one folder up from this patch.
    echo.
    echo Make sure this whole "InstINDEX_Datasheet_Import_Patch" folder is
    echo sitting INSIDE your InstINDEX installation folder - the same one
    echo that already has gui_app.py, data_access.py, START_INSTINDEX.bat,
    echo etc. in it - before running this.
    echo.
    pause
    exit /b 1
)

if not exist "%FILES_DIR%\gui_app.py" (
    echo ERROR: Patch files are missing ^(_patch_files\gui_app.py not found^).
    echo This patch folder looks incomplete - try re-downloading and
    echo re-extracting it, keeping the folder structure intact.
    echo.
    pause
    exit /b 1
)

findstr /C:"datasheet_reader" "%TARGET_DIR%\gui_app.py" >nul 2>&1
if %errorlevel%==0 (
    echo It looks like this patch may already be applied - gui_app.py
    echo already references datasheet_reader.
    echo.
    set /p CONFIRM_REAPPLY="Apply it again anyway? (Y/N): "
    if /i not "!CONFIRM_REAPPLY!"=="Y" (
        echo Cancelled - nothing was changed.
        echo.
        pause
        exit /b 0
    )
    echo.
)

echo This will update, inside:
echo   %TARGET_DIR%
echo.
echo   - gui_app.py                    (updated)
echo   - WHATS_NEW_THIS_UPDATE.txt     (updated)
echo   - datasheet_reader.py           (new file)
echo.
echo Your current gui_app.py and WHATS_NEW_THIS_UPDATE.txt will be backed
echo up first, to:
echo   %BACKUP_DIR%
echo.
echo No workbook, no JSON files, and nothing else in your installation is
echo touched by this patch.
echo.
set /p CONFIRM="Continue? (Y/N): "
if /i not "%CONFIRM%"=="Y" (
    echo Cancelled - nothing was changed.
    echo.
    pause
    exit /b 0
)
echo.

if not exist "%BACKUP_DIR%" mkdir "%BACKUP_DIR%"
copy /Y "%TARGET_DIR%\gui_app.py" "%BACKUP_DIR%\gui_app.py" >nul
if errorlevel 1 (
    echo ERROR: Couldn't back up gui_app.py - stopping without changing
    echo anything. Check that the InstINDEX folder isn't read-only and
    echo that the app isn't currently running, then try again.
    echo.
    pause
    exit /b 1
)
if exist "%TARGET_DIR%\WHATS_NEW_THIS_UPDATE.txt" (
    copy /Y "%TARGET_DIR%\WHATS_NEW_THIS_UPDATE.txt" "%BACKUP_DIR%\WHATS_NEW_THIS_UPDATE.txt" >nul
)
echo Backed up your current gui_app.py.

copy /Y "%FILES_DIR%\gui_app.py" "%TARGET_DIR%\gui_app.py" >nul
if errorlevel 1 (
    echo ERROR: Couldn't write the new gui_app.py. Your original is safe
    echo and unchanged - restore it manually from:
    echo   %BACKUP_DIR%\gui_app.py
    echo if this copy left things in a half-updated state.
    echo.
    pause
    exit /b 1
)
copy /Y "%FILES_DIR%\datasheet_reader.py" "%TARGET_DIR%\datasheet_reader.py" >nul
copy /Y "%FILES_DIR%\WHATS_NEW_THIS_UPDATE.txt" "%TARGET_DIR%\WHATS_NEW_THIS_UPDATE.txt" >nul

echo.
echo ============================================================
echo  Done - applied successfully.
echo ============================================================
echo.
echo What's new: a "Import Datasheet PDF..." button in the sidebar
echo (Ctrl+Shift+I) that pre-fills a new row from an engineering data
echo sheet PDF instead of retyping it. See WHATS_NEW_THIS_UPDATE.txt
echo for the details on what it can and can't read.
echo.
echo Just start InstINDEX the normal way (START_INSTINDEX.bat) - nothing
echo else about running it changed.
echo.
echo If anything looks wrong after this, your previous gui_app.py is
echo saved at:
echo   %BACKUP_DIR%\gui_app.py
echo Copy it back over gui_app.py (in the InstINDEX folder, one level up
echo from this patch folder) to undo this patch.
echo.
pause
