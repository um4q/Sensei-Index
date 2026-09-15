# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for the Access Edition - builds access_gui_app.py (and
every local module it pulls in) into ONE executable. Sibling spec to
"Sensei Index 2.9"/SenseiIndex.spec - see that file's own docstring for
the shared "what stays external, on purpose" reasoning; this one only
differs where the two editions' own file layouts actually differ.

WHY pathex POINTS AT THE SIBLING "Sensei Index 2.9" FOLDER
------------------------------------------------------------------
access_data_access.py/access_electrical_data_access.py/access_gui_app.py
import a bunch of modules that live one folder over - data_access.py,
electrical_data_access.py, master_list_reader.py, datasheet_reader.py,
theme.py, and every *_schema.py/*_field_map.py/export_*_to_pdf.py file
(the exact same ones the Excel edition's own spec bundles from ITS own
directory). At RUNTIME those modules are found via a sys.path.insert()
access_data_access.py does itself before importing them (see that
module's own docstring) - but PyInstaller's Analysis step parses this
file's import graph STATICALLY, it doesn't execute access_data_access.py
to see that sys.path mutation happen. Without pathex naming that sibling
folder explicitly, PyInstaller simply wouldn't find `data_access.py` (or
any of the others) at build time and the exe would fail on the very
first `import access_data_access` line since import discovery only
matters at ANALYSIS time. The runtime sys.path.insert() call still
happens harmlessly once frozen (a no-op for anything already bundled
into the exe's own PYZ archive) - it just isn't what makes this build
actually work.

WHAT STAYS EXTERNAL, ON PURPOSE
--------------------------------------
Same as "Sensei Index 2.9"/SenseiIndex.spec: nothing data-related is
baked INTO the exe - SenseiIndex.accdb, and everything this edition
reads out of the sibling "Sensei Index 2.9" folder at runtime (the PDF
templates, assets/ - signature image, logos), stays external, resolved
relative to sys.executable's own folder once frozen (see access_data_
access.py's own HERE/EXCEL_EDITION_DIR for why). So the built exe is
meant to be dropped into the SAME "Sensei Index Access Edition" folder
it was built from, right next to SenseiIndex.accdb, with the sibling
"Sensei Index 2.9" folder (assets/ + the PDF templates) still present
one level up - exactly the two-folder layout this whole edition already
ships as (see README_ACCESS_EDITION.txt).

BUILD (must run on Windows - PyInstaller does not cross-compile):
    pip install -r requirements.txt pyinstaller
    pyinstaller SenseiIndexAccessEdition.spec

Output: dist/Sensei Index Access Edition.exe - copy that one file into
this same folder (next to SenseiIndex.accdb), replacing
`python access_gui_app.py` as the way to launch the app. The sibling
"Sensei Index 2.9" folder must stay present one level up either way.
"""
from pathlib import Path

block_cipher = None

EXCEL_EDITION_DIR = str(Path('..') / 'Sensei Index 2.9')

a = Analysis(
    ['access_gui_app.py'],
    pathex=[EXCEL_EDITION_DIR],
    binaries=[],
    datas=[],
    hiddenimports=['pyodbc'],
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
    name='Sensei Index Access Edition',
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
    icon=str(Path(EXCEL_EDITION_DIR) / 'assets' / 'oathplatehelm.ico'),
)
