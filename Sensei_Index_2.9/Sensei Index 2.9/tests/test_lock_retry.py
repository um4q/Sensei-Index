# -*- coding: utf-8 -*-
"""Phase 16.2 - run_with_lock_retry() and its wiring into the 3 primary
save paths (IndexPage inline-cell edit, IndexPage bulk edit, EditDialog)."""
import pytest

import gui_app


def test_succeeds_on_first_try_no_dialog(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: pytest.fail("should not be called")))
    result = gui_app.run_with_lock_retry(None, lambda: None)
    assert result is True


def test_retries_until_success(monkeypatch):
    calls = {"n": 0}

    def action():
        calls["n"] += 1
        if calls["n"] < 3:
            raise gui_app.da.WorkbookLockedError("locked")

    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Retry))
    result = gui_app.run_with_lock_retry(None, action)
    assert result is True
    assert calls["n"] == 3


def test_cancel_stops_retrying(monkeypatch):
    calls = {"n": 0}

    def action():
        calls["n"] += 1
        raise gui_app.da.WorkbookLockedError("locked")

    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Cancel))
    result = gui_app.run_with_lock_retry(None, action)
    assert result is False
    assert calls["n"] == 1  # never retried after Cancel


def test_non_lock_error_shows_critical_not_retry_dialog(monkeypatch):
    critical_calls = []
    question_calls = []
    monkeypatch.setattr(gui_app.QMessageBox, "critical",
                         staticmethod(lambda *a, **k: critical_calls.append(a)))
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: question_calls.append(a)))

    def action():
        raise ValueError("something else entirely")

    result = gui_app.run_with_lock_retry(None, action)
    assert result is False
    assert len(critical_calls) == 1
    assert question_calls == []  # never showed the lock-specific dialog


def test_index_page_inline_edit_retries_on_lock(qtbot, isolated_app_dir, fake_main_window, monkeypatch):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    calls = {"n": 0}
    real_save_row = da.save_row

    def flaky_save_row(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise da.WorkbookLockedError("The workbook is open in Excel. Close it there, then click Retry.")
        return real_save_row(*a, **k)

    monkeypatch.setattr(da, "save_row", flaky_save_row)
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Retry))

    page._commit_single_cell_edit(row, "system_number", "STEAM")

    assert calls["n"] == 2  # failed once, retried, succeeded
    saved = da.read_full_row(29103, "transmitter", row)
    assert saved["system_number"] == "STEAM"


def test_edit_dialog_save_retries_on_lock(qtbot, isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")

    calls = {"n": 0}
    real_save_row = da.save_row

    def flaky_save_row(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise da.WorkbookLockedError("locked")
        return real_save_row(*a, **k)

    monkeypatch.setattr(da, "save_row", flaky_save_row)
    monkeypatch.setattr(gui_app.QMessageBox, "question",
                         staticmethod(lambda *a, **k: gui_app.QMessageBox.Retry))
    monkeypatch.setattr(gui_app.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    dlg = gui_app.EditDialog(None, 29103, "transmitter", row, is_new=True)
    qtbot.addWidget(dlg)
    dlg.widgets["tag"].setText("29103-PIT-2171")
    dlg.save()

    assert calls["n"] == 2
    assert dlg.result() == gui_app.QDialog.Accepted
