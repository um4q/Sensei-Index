# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sensei Index 4.0.

Builds a --onedir bundle: SenseiIndex.exe plus a sibling _internal/ folder
holding the frozen Python runtime, PySide6, and every other dependency as
compiled/archived bytecode - not as loose, readable .py files. That's what
makes "no visible source code" true once this is installed.

Only bootstrap.py and everything it imports goes in here. The workbook,
JSON stores, PDF templates, master list, and assets/ (fonts, icon, images)
are deliberately NOT bundled - paths.py resolves them relative to
sys.executable's folder once frozen, so they have to stay next to the exe
as plain, visible files. installer.iss is what actually puts them there;
this spec only builds the app binary itself.

Build with (from this packaging/ folder, on Windows, with the app's four
dependencies + pyinstaller installed):
    pyinstaller sensei_index.spec --noconfirm
Output lands in packaging/dist/SenseiIndex/.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# This file lives in Sensei_Index_4.0/packaging/; the app source is one
# directory up. SPECPATH is a PyInstaller-injected global, not a normal
# Python name - it only exists while a .spec file is being exec'd.
APP_DIR = Path(SPECPATH).resolve().parent  # noqa: F821

ENTRY_POINT = APP_DIR / "bootstrap.py"
ICON_PATH = APP_DIR / "assets" / "oathplatehelm.ico"

APP_MODULES = [
    "bootstrap", "data_access", "datasheet_reader", "documents_dialog",
    "export_to_pdf", "export_valve_to_pdf", "gui_app", "index_view",
    "paths", "splash_screen", "theme", "transmitter_field_map",
    "transmitter_schema", "valve_field_map", "valve_schema",
]

# collect_all() rather than relying on PyInstaller's built-in hooks alone:
# reportlab in particular loads some of its standard-font metrics as data
# rather than through a plain `import`, which static analysis can miss.
# Belt-and-suspenders here costs a few extra MB in _internal/, which is
# a much better trade than an installer that fails on someone else's
# Windows machine with no way for us to attach a debugger to it.
#
# PySide6 is deliberately NOT in this list, unlike the other three - a
# local dry run (pyinstaller can freeze for the host platform even though
# it can't cross-compile to Windows, so this is checkable from Linux)
# showed collect_all('PySide6') balloons the build past 800 MB by pulling
# in WebEngine (195 MB - a whole embedded Chromium; this app has no
# browser view), Multimedia/Quick3D/QML (this app is plain QtWidgets,
# no QML anywhere), and every SQL driver and Wayland compositor plugin.
# PyInstaller's own PySide6 hook (it ships one specifically because this
# combination is so common) already detects which Qt modules gui_app.py
# and splash_screen.py actually import and bundles their real runtime
# needs, the windows platform plugin included - that hook is what's
# relied on here instead.
datas, binaries, hiddenimports = [], [], []
for pkg in ("openpyxl", "pypdf", "reportlab"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden
hiddenimports += APP_MODULES

a = Analysis(  # noqa: F821
    [str(ENTRY_POINT)],
    pathex=[str(APP_DIR)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure, a.zipped_data)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SenseiIndex",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON_PATH),
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SenseiIndex",
)
