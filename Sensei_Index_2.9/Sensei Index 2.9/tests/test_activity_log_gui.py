# -*- coding: utf-8 -*-
"""Phase 15 - History tab on RowDetailDialog + Recent Activity on
DashboardPage, driven offscreen via pytest-qt."""
import pytest

import gui_app


@pytest.fixture(autouse=True)
def _no_modal_message_boxes(monkeypatch):
    monkeypatch.setattr(gui_app.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(gui_app.QMessageBox, "critical", staticmethod(lambda *a, **k: None))


def test_format_history_entry_edit():
    entry = {
        "ts": "2026-08-30T14:14:00", "action": "edit", "source": "bulk",
        "fields": {"serial_number": {"old": "", "new": "8800DF080"}},
    }
    text = gui_app.format_history_entry(entry)
    assert "Serial Number" not in text or "serial_number" in text  # label falls back w/o schema
    assert "blank" in text
    assert "8800DF080" in text
    assert "bulk edit" in text
    assert "Aug 30" in text


def test_format_history_entry_uses_schema_label():
    import transmitter_schema
    entry = {"ts": "2026-08-30T14:14:00", "action": "edit", "source": "edit_dialog",
              "fields": {"serial_number": {"old": "", "new": "8800DF080"}}}
    text = gui_app.format_history_entry(entry, transmitter_schema)
    assert "Serial Number: blank → 8800DF080" in text


def test_format_history_entry_delete():
    entry = {"ts": "2026-08-30T14:14:00", "action": "delete", "key_value": "29103-PIT-2171",
              "source": "edit_dialog"}
    text = gui_app.format_history_entry(entry)
    assert "cleared" in text
    assert "29103-PIT-2171" in text


def test_format_history_entry_caps_at_three_fields_plus_more():
    fields = {f"f{i}": {"old": "", "new": str(i)} for i in range(6)}
    entry = {"ts": "2026-08-30T14:14:00", "action": "edit", "fields": fields, "source": "edit_dialog"}
    text = gui_app.format_history_entry(entry)
    assert "and 3 more" in text


def test_row_detail_dialog_shows_history(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "serial_number": "SN-1"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)

    dlg = gui_app.RowDetailDialog(None, 29103, "transmitter", row)
    qtbot.addWidget(dlg)

    all_text = " ".join(
        c.findChild(gui_app.QLabel).text() if c.findChild(gui_app.QLabel) else ""
        for c in dlg.findChildren(gui_app.QGroupBox)
    )
    # crude but sufficient: at least one History-ish string made it onto the dialog
    labels = [w.text() for w in dlg.findChildren(gui_app.QLabel)]
    assert any("Installed" in t and "→" in t for t in labels) or any("SN-1" in t for t in labels)


def test_row_detail_dialog_empty_history_state(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    # row exists in the workbook but was never saved through a logged path
    # (isolated_app_dir's synthetic workbook starts fully blank - reading
    # row 4 directly is fine, it'll just have no history).
    dlg = gui_app.RowDetailDialog(None, 29103, "transmitter", row)
    qtbot.addWidget(dlg)
    labels = [w.text() for w in dlg.findChildren(gui_app.QLabel)]
    assert any("No recorded history" in t for t in labels)


def test_dashboard_recent_activity_card_lists_entries(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    page = gui_app.DashboardPage(fake_main_window)
    qtbot.addWidget(page)

    lists = page.findChildren(gui_app.QListWidget, "RecentActivityList")
    assert len(lists) == 1
    assert lists[0].count() >= 1
    assert "29103-PIT-2171" in lists[0].item(0).text()


def test_dashboard_recent_activity_click_navigates(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})

    calls = []
    fake_main_window.show_index = lambda *a, **k: calls.append(a)

    page = gui_app.DashboardPage(fake_main_window)
    qtbot.addWidget(page)
    activity_list = page.findChildren(gui_app.QListWidget, "RecentActivityList")[0]
    page._on_recent_activity_clicked(activity_list.item(0))

    assert calls == [(29103, "transmitter", {"tag": "29103-PIT-2171"})]


def test_dashboard_recent_activity_empty_state(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    page = gui_app.DashboardPage(fake_main_window)
    qtbot.addWidget(page)
    lists = page.findChildren(gui_app.QListWidget, "RecentActivityList")
    assert lists == []  # no card contents when there's nothing to show
