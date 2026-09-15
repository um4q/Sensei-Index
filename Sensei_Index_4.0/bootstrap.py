# -*- coding: utf-8 -*-
"""
Sensei Index 3.0 launcher.

    pythonw bootstrap.py

This is the real entry point (START_SENSEI_INDEX.bat calls it with
pythonw, not python, so no console window ever appears - plate 5a's build
note: "the launcher starts pythonw.exe so no console appears at all").

The splash screen goes up FIRST, before the heavy imports (openpyxl,
pypdf, reportlab, every PySide6 widget gui_app.py pulls in) - that's the
whole point of checking "required packages present" as step 1: if one is
missing, this shows a plain-language error on screen instead of the
traceback-in-a-black-window it used to be. gui_app itself is only
imported once that check has already passed.
"""
import importlib.util
import sys
import time
from pathlib import Path

from PySide6.QtWidgets import QApplication

from splash_screen import SplashScreen

HERE = Path(__file__).resolve().parent
REQUIRED_PACKAGES = ["PySide6", "openpyxl", "pypdf", "reportlab"]


def _check_packages():
    missing = [pkg for pkg in REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
    if missing:
        return False, (
            f"Missing: {', '.join(missing)}. Close this, then run "
            f"START_SENSEI_INDEX.bat again - it installs these automatically."
        )
    return True, None


def _check_writable():
    probe = HERE / ".write_test"
    try:
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True, None
    except OSError:
        return False, (
            f"Can't write to '{HERE}'. Move this whole folder somewhere that "
            "doesn't need administrator rights - your Desktop, Documents, or "
            "C:\\Users\\Public\\InstINDEX - then try again."
        )


def _timed(splash, index, fn):
    splash.set_step(index, "active")
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as exc:  # noqa: BLE001 - surfaced on screen, not a bare traceback
        ok, detail = False, str(exc)
    elapsed = time.time() - t0
    if ok:
        splash.set_step(index, "done", elapsed=elapsed)
    else:
        splash.set_step(index, "error", detail=detail, elapsed=elapsed)
    return ok


def main():
    app = QApplication(sys.argv)
    splash = SplashScreen()
    splash.show()
    app.processEvents()

    if not _timed(splash, 0, _check_packages):
        sys.exit(app.exec())
    if not _timed(splash, 1, _check_writable):
        sys.exit(app.exec())

    splash.set_step(2, "active")
    t0 = time.time()
    try:
        import gui_app  # noqa: PLC0415 - deliberately deferred, see module docstring
        gui_app.da.list_series()  # forces the workbook to actually load
    except Exception as exc:  # noqa: BLE001
        splash.set_step(2, "error", detail=str(exc), elapsed=time.time() - t0)
        sys.exit(app.exec())
    splash.set_step(2, "done", elapsed=time.time() - t0)

    splash.set_step(3, "active")
    t0 = time.time()
    try:
        theme_name = gui_app.da.get_setting("theme") or "light"
        gui_app.apply_app_theme(app, theme_name)
        win = gui_app.MainWindow()
    except Exception as exc:  # noqa: BLE001
        splash.set_step(3, "error", detail=str(exc), elapsed=time.time() - t0)
        sys.exit(app.exec())
    splash.set_step(3, "done", elapsed=time.time() - t0)

    splash.close()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
