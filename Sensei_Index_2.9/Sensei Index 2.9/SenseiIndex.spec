# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sensei Index 2.95 - builds the whole app (gui_app.py
and every local module it pulls in - data_access.py, electrical_data_access.py,
datasheet_reader.py, theme.py, and all ~60 per-form schema/field_map/
field_positions/export_*.py/build_*.py modules) into ONE executable.

WHAT STAYS EXTERNAL, ON PURPOSE
--------------------------------------
Nothing under this repo's data files - the .xlsx workbooks, the .json
config files, the PDF templates, or the assets/ folder - is bundled INTO
the exe. gui_app.py/data_access.py/electrical_data_access.py already
resolve all of those relative to sys.executable's own folder once frozen
(see data_access.py's own HERE comment for why __file__ can't be used
for this once frozen - it points inside a temp extraction folder that's
deleted when the app closes). So the built exe is meant to be dropped
into this same folder, sitting right next to those files, exactly like
gui_app.py itself does today - NOT to carry its own copy of the
workbook/templates baked in, which would silently orphan every edit the
moment the app closes.

The one exception is the .ico file, which IS baked in below (via
`icon=`) - that's a build-time-only embed into the .exe's own PE header
(what Explorer/the taskbar show for the .exe file itself), completely
separate from assets/oathplatehelm.ico still being read at RUNTIME for
the in-app splash/sidebar logo (that one stays external, same as every
other asset).

BUILD (must run on Windows - PyInstaller does not cross-compile):
    pip install -r requirements.txt pyinstaller
    pyinstaller SenseiIndex.spec

Output: dist/Sensei Index 2.95.exe - copy that one file into the
InstINDEX folder (next to Equipment_Inspection_Tracker.xlsx, the PDF
templates, assets/, etc.), replacing gui_app.py/START_INSTINDEX.bat/every
other loose .py file as the way to launch the app.
"""
from pathlib import Path

block_cipher = None

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_qt', '_pytest'],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Sensei Index 2.95',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path('assets') / 'oathplatehelm.ico'),
)
