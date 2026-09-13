@echo off
setlocal enabledelayedexpansion
title InstINDEX - Electrical Forms Real-Source Rebuild - Update Patch

echo ============================================================
echo  InstINDEX - Electrical Forms Real-Source Rebuild - Update Patch
echo ============================================================
echo.

set "PATCH_DIR=%~dp0"
set "TARGET_DIR=%PATCH_DIR%.."
set "FILES_DIR=%PATCH_DIR%_patch_files"
set "BACKUP_DIR=%TARGET_DIR%\_backup_before_electrical_templates_patch"

if not exist "%TARGET_DIR%\gui_app.py" (
    echo ERROR: Couldn't find gui_app.py one folder up from this patch.
    echo.
    echo Make sure this whole "InstINDEX_Electrical_Templates_Patch" folder
    echo is sitting INSIDE your InstINDEX installation folder - the same
    echo one that already has gui_app.py, data_access.py,
    echo START_INSTINDEX.bat, etc. in it - before running this.
    echo.
    pause
    exit /b 1
)

if not exist "%FILES_DIR%\electrical_data_access.py" (
    echo ERROR: Patch files are missing ^(_patch_files\electrical_data_access.py
    echo not found^). This patch folder looks incomplete - try re-downloading
    echo and re-extracting it, keeping the folder structure intact ^(the
    echo _patch_files subfolder, including its own assets subfolder, has to
    echo come along with APPLY_UPDATE.bat^).
    echo.
    pause
    exit /b 1
)

if exist "%TARGET_DIR%\assets\transformer_test_source.pdf" (
    echo It looks like this patch may already be applied - your assets
    echo folder already has transformer_test_source.pdf.
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
echo   - The 3 rebuilt PDF templates:
echo       Transformer_Test_Record_TEMPLATE.pdf
echo       Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
echo       General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
echo   - 13 supporting Python files (the schema/field-map/build/export
echo     files for those 3 forms, plus electrical_data_access.py)
echo   - assets\transformer_test_source.pdf        (new file)
echo   - assets\small_power_cable_source.pdf        (new file)
echo   - assets\general_equip_install_source.pdf    (new file)
echo   - WHATS_NEW_THIS_UPDATE.txt                  (updated)
echo.
echo It will also REMOVE 4 files these 3 forms no longer use:
echo   - small_power_cable_field_positions.py
echo   - assets\transformer_test_background.jpg
echo   - assets\small_power_cable_background.jpg
echo   - assets\general_equip_install_background.jpg
echo (everything removed is backed up first - see below).
echo.
echo Everything this patch touches will be backed up first, to:
echo   %BACKUP_DIR%
echo.
echo No workbook, no JSON files, no other forms, and nothing else in your
echo installation is touched by this patch.
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
if not exist "%BACKUP_DIR%\assets" mkdir "%BACKUP_DIR%\assets"

for %%F in (
    build_general_equip_install_template.py
    build_small_power_cable_template.py
    build_transformer_test_template.py
    electrical_data_access.py
    export_general_equip_install_to_pdf.py
    export_small_power_cable_to_pdf.py
    export_transformer_test_to_pdf.py
    general_equip_install_field_map.py
    general_equip_install_field_positions.py
    general_equip_install_schema.py
    small_power_cable_field_map.py
    small_power_cable_schema.py
    transformer_test_field_positions.py
    General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
    Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
    Transformer_Test_Record_TEMPLATE.pdf
    WHATS_NEW_THIS_UPDATE.txt
    small_power_cable_field_positions.py
) do (
    if exist "%TARGET_DIR%\%%F" copy /Y "%TARGET_DIR%\%%F" "%BACKUP_DIR%\%%F" >nul
)
for %%F in (
    transformer_test_background.jpg
    small_power_cable_background.jpg
    general_equip_install_background.jpg
) do (
    if exist "%TARGET_DIR%\assets\%%F" copy /Y "%TARGET_DIR%\assets\%%F" "%BACKUP_DIR%\assets\%%F" >nul
)
echo Backed up everything this patch is about to touch.

for %%F in (
    build_general_equip_install_template.py
    build_small_power_cable_template.py
    build_transformer_test_template.py
    electrical_data_access.py
    export_general_equip_install_to_pdf.py
    export_small_power_cable_to_pdf.py
    export_transformer_test_to_pdf.py
    general_equip_install_field_map.py
    general_equip_install_field_positions.py
    general_equip_install_schema.py
    small_power_cable_field_map.py
    small_power_cable_schema.py
    transformer_test_field_positions.py
    General_Electrical_Equipment_Installation_and_Test_Report_TEMPLATE.pdf
    Small_Power_and_Control_Cable_Inspection_and_Test_Record_TEMPLATE.pdf
    Transformer_Test_Record_TEMPLATE.pdf
    WHATS_NEW_THIS_UPDATE.txt
) do (
    copy /Y "%FILES_DIR%\%%F" "%TARGET_DIR%\%%F" >nul
    if errorlevel 1 (
        echo ERROR: Couldn't write %%F. Your originals are safe and unchanged
        echo in %BACKUP_DIR% - restore from there manually if this copy left
        echo things in a half-updated state.
        echo.
        pause
        exit /b 1
    )
)
if not exist "%TARGET_DIR%\assets" mkdir "%TARGET_DIR%\assets"
copy /Y "%FILES_DIR%\assets\transformer_test_source.pdf" "%TARGET_DIR%\assets\transformer_test_source.pdf" >nul
copy /Y "%FILES_DIR%\assets\small_power_cable_source.pdf" "%TARGET_DIR%\assets\small_power_cable_source.pdf" >nul
copy /Y "%FILES_DIR%\assets\general_equip_install_source.pdf" "%TARGET_DIR%\assets\general_equip_install_source.pdf" >nul

if exist "%TARGET_DIR%\small_power_cable_field_positions.py" del /F /Q "%TARGET_DIR%\small_power_cable_field_positions.py" >nul
if exist "%TARGET_DIR%\assets\transformer_test_background.jpg" del /F /Q "%TARGET_DIR%\assets\transformer_test_background.jpg" >nul
if exist "%TARGET_DIR%\assets\small_power_cable_background.jpg" del /F /Q "%TARGET_DIR%\assets\small_power_cable_background.jpg" >nul
if exist "%TARGET_DIR%\assets\general_equip_install_background.jpg" del /F /Q "%TARGET_DIR%\assets\general_equip_install_background.jpg" >nul

echo.
echo ============================================================
echo  Done - applied successfully.
echo ============================================================
echo.
echo What's new: Transformer Test Record, Small Power and Control Cable
echo ITR, and General Electrical Equipment Installation ^& Test Report are
echo now rebuilt from your real official source documents instead of a
echo hand-filled scan - see WHATS_NEW_THIS_UPDATE.txt for the details
echo (including the General Electrical Equipment Installation form now
echo exporting as 2 pages, not 1 - a pagination quirk from the source, not
echo a content change).
echo.
echo Just start InstINDEX the normal way (START_INSTINDEX.bat) - nothing
echo else about running it changed.
echo.
echo If anything looks wrong after this, everything this patch touched is
echo saved at:
echo   %BACKUP_DIR%
echo Copy those files back over their originals (in the InstINDEX folder,
echo one level up from this patch folder - the 3 background .jpg files go
echo back inside its assets subfolder) to undo this patch.
echo.
pause
