# -*- coding: utf-8 -*-
"""
Root pytest conftest for the Access Edition - same two jobs, same
ordering requirement, as "Sensei Index 2.9"'s own conftest.py (see that
file's own docstring for the full reasoning):

1. Force the offscreen Qt platform plugin before PySide6.QtWidgets is
   imported anywhere, so the test suite (and CI) never needs a real
   display - this is what lets tests/test_domain_modules_integration.py
   actually construct MainWindow and every dialog class, and run
   access_gui_app.py's own _run_startup_with_splash(), without a
   windowing system.
2. Put this directory (where access_gui_app.py / access_data_access.py
   / access_schema.py live) on sys.path - this app has no package
   structure either, so pytest's own rootdir insertion (tests/ only,
   no __init__.py there) isn't enough on its own.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))
