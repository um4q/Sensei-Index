# -*- coding: utf-8 -*-
"""Phase 15's own acceptance criterion: 'Undo/redo also log (as their own
actions) so history never shows a change that silently un-happened.'"""
import gui_app


def test_undo_logs_its_own_marker_action(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")

    calls = {"undo": 0, "redo": 0}
    mgr = gui_app.UndoManager()
    mgr.push("edit Tag - row 4", lambda: calls.__setitem__("undo", calls["undo"] + 1),
              lambda: calls.__setitem__("redo", calls["redo"] + 1))

    mgr.undo()
    entries = [e for e in da.read_activity_log() if e["action"] == "undo"]
    assert len(entries) == 1
    assert entries[0]["source"] == "undo"
    assert "edit Tag - row 4" in entries[0]["note"]


def test_redo_logs_its_own_marker_action(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    mgr = gui_app.UndoManager()
    mgr.push("edit Tag - row 4", lambda: None, lambda: None)
    mgr.undo()
    mgr.redo()

    entries = [e for e in da.read_activity_log() if e["action"] == "redo"]
    assert len(entries) == 1
    assert "edit Tag - row 4" in entries[0]["note"]


def test_undo_of_a_real_save_row_logs_both_the_field_edit_and_the_undo_marker(isolated_app_dir):
    """The underlying data change (save_row's own 'edit' event, showing
    the field going back to its old value) AND the undo marker both
    appear - history never shows a silently-un-happened change."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"service": "SVC A"})
    old_values = da.read_full_row(29103, "transmitter", row)

    da.save_row(29103, "transmitter", row, {"service": "SVC B"})

    mgr = gui_app.UndoManager()

    def do_undo():
        da.save_row(29103, "transmitter", row, {"service": old_values["service"]})

    mgr.push("edit Service - row 4", do_undo, lambda: None)
    mgr.undo()

    # The undo marker itself carries no row/series (UndoManager doesn't
    # know the closure's data context) - it's in the UNFILTERED log.
    assert any(e["action"] == "undo" for e in da.read_activity_log())

    # The undo's own save_row() call produced its own row-scoped,
    # field-level edit event - the actual data change is never silent.
    row_entries = da.read_activity_log(series=29103, equip_key="transmitter", row=row)
    edit_events = [e for e in row_entries if e["action"] == "edit"]
    assert any(e["fields"].get("service", {}).get("new") == "SVC A" for e in edit_events)


def test_no_undo_no_log_entry(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    mgr = gui_app.UndoManager()
    result = mgr.undo()  # nothing to undo
    assert result is None
    assert da.read_activity_log() == []
