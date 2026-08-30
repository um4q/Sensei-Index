# -*- coding: utf-8 -*-
"""Phase 17 - the 'Export Progress Report' button on Dashboard and
Coverage, driven offscreen via pytest-qt."""
import pytest

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.da, "open_file", lambda *a, **k: None)  # no OS file-explorer in CI


def test_export_progress_report_flow_writes_report(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_progress_report_flow(widget)

    reports = list(da.REPORTS_DIR.glob("Progress_Report_*.xlsx"))
    assert len(reports) == 1


def test_dashboard_has_export_button_that_works(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    page = gui_app.DashboardPage(fake_main_window)
    qtbot.addWidget(page)
    buttons = [b for b in page.findChildren(gui_app.QPushButton) if b.text() == "Export Progress Report"]
    assert len(buttons) == 1
    buttons[0].click()

    assert list(da.REPORTS_DIR.glob("Progress_Report_*.xlsx"))


def test_coverage_has_export_button_that_works(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    page = gui_app.CoveragePage(fake_main_window)
    qtbot.addWidget(page)
    buttons = [b for b in page.findChildren(gui_app.QPushButton) if b.text() == "Export Progress Report"]
    assert len(buttons) == 1
    buttons[0].click()

    assert list(da.REPORTS_DIR.glob("Progress_Report_*.xlsx"))


def test_export_error_shows_critical_not_a_crash(qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    critical_calls = []
    monkeypatch.setattr(gui_app.QMessageBox, "critical",
                         staticmethod(lambda *a, **k: critical_calls.append(a)))
    monkeypatch.setattr(da, "export_progress_report",
                         lambda: (_ for _ in ()).throw(OSError("disk full")))

    widget = gui_app.QWidget()
    qtbot.addWidget(widget)
    gui_app.export_progress_report_flow(widget)  # must not raise
    assert len(critical_calls) == 1
