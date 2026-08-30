# -*- coding: utf-8 -*-
"""Phase 18 - the 'Export Cleaned Copy' button on the Dashboard, driven
offscreen via pytest-qt."""
import pytest

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.da, "open_file", lambda *a, **k: None)  # no OS file-explorer in CI


def test_export_cleaned_workbook_flow_writes_file(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171"})

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_cleaned_workbook_flow(widget)

    outputs = list(da.CLEANED_DIR.glob("Equipment_Inspection_Tracker_CLEANED_*.xlsx"))
    assert len(outputs) == 1


def test_dashboard_has_export_cleaned_button_that_works(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-pit-2171"})

    page = gui_app.DashboardPage(fake_main_window)
    qtbot.addWidget(page)
    buttons = [b for b in page.findChildren(gui_app.QPushButton) if b.text() == "Export Cleaned Copy"]
    assert len(buttons) == 1
    buttons[0].click()

    assert list(da.CLEANED_DIR.glob("Equipment_Inspection_Tracker_CLEANED_*.xlsx"))


def test_export_error_shows_critical_not_a_crash(qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    critical_calls = []
    monkeypatch.setattr(gui_app.QMessageBox, "critical",
                         staticmethod(lambda *a, **k: critical_calls.append(a)))
    monkeypatch.setattr(da, "export_cleaned_workbook",
                         lambda: (_ for _ in ()).throw(OSError("disk full")))

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_cleaned_workbook_flow(widget)  # must not raise
    assert len(critical_calls) == 1
