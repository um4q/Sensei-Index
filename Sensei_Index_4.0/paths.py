# -*- coding: utf-8 -*-
"""
The one place that knows where "here" is - the folder holding the
workbook, the JSON stores, the PDF templates, and (once frozen) the exe
itself. Every other module imports HERE from here instead of computing
its own, so there's exactly one frozen-vs-script check in the whole app.

When PyInstaller freezes this app, __file__ points inside a temporary
extraction folder (or the onedir bundle's internal folder) that's either
wiped on exit or not writable/not meant to hold user data - using it
would silently lose every edit, setting, and signature the moment the
exe exits, or reach into the read-only bundle where the data files
weren't even placed. sys.executable's folder is the actual, persistent
install location (or the plain script's folder, when not frozen, which
is why the frozen check comes first).
"""
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent

ASSETS_DIR = HERE / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
