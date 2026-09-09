# -*- coding: utf-8 -*-
"""Phase 13.1 - index_row_matches_chip(). Pure function, no widgets."""
import data_access as da
import gui_app


def _entry(installed=False, submitted=False, accepted=False, values=None):
    values = values or {}
    status = {"installed": installed, "submitted": submitted, "accepted": accepted}
    progress = da.compute_progress("transmitter", values, status)
    return {"installed": installed, "submitted": submitted, "accepted": accepted,
            "progress": progress}


def test_all_matches_everything():
    for entry in (_entry(), _entry(installed=True), _entry(accepted=True)):
        assert gui_app.index_row_matches_chip(entry, "all") is True


def test_not_started_matches_a_freshly_created_row():
    """compute_progress()'s 'created' milestone is always done for any
    row that exists, so percent is NEVER literally 0 - 'not started' has
    to mean 'nothing past Created', not percent==0."""
    fresh = _entry()
    assert fresh["progress"]["percent"] > 0  # confirms the premise above
    assert gui_app.index_row_matches_chip(fresh, "not_started") is True

    with_serial = _entry(values={"serial_number": "SN-1"})
    assert gui_app.index_row_matches_chip(with_serial, "not_started") is False

    installed_only = _entry(installed=True)
    assert gui_app.index_row_matches_chip(installed_only, "not_started") is False


def test_missing_serial():
    no_serial = _entry()
    assert gui_app.index_row_matches_chip(no_serial, "missing_serial") is True
    has_serial = _entry(values={"serial_number": "SN-1"})
    assert gui_app.index_row_matches_chip(has_serial, "missing_serial") is False


def test_installed_chip():
    assert gui_app.index_row_matches_chip(_entry(installed=True), "installed") is True
    assert gui_app.index_row_matches_chip(_entry(installed=False), "installed") is False


def test_ready_to_submit_requires_full_inspection_and_not_submitted():
    values = {"serial_number": "SN-1"}
    values.update({f"vi_{i}": "X" for i in range(1, 13)})
    values.update({f"proc_{i}": "Pass" for i in range(2, 15)})

    ready = _entry(installed=True, submitted=False, values=values)
    assert gui_app.index_row_matches_chip(ready, "ready_submit") is True

    already_submitted = _entry(installed=True, submitted=True, values=values)
    assert gui_app.index_row_matches_chip(already_submitted, "ready_submit") is False

    not_installed_yet = _entry(installed=False, submitted=False, values=values)
    assert gui_app.index_row_matches_chip(not_installed_yet, "ready_submit") is False

    incomplete_inspection = dict(values)
    del incomplete_inspection["vi_12"]
    partial = _entry(installed=True, submitted=False, values=incomplete_inspection)
    assert gui_app.index_row_matches_chip(partial, "ready_submit") is False


def test_submitted_and_accepted_chips():
    assert gui_app.index_row_matches_chip(_entry(submitted=True), "submitted") is True
    assert gui_app.index_row_matches_chip(_entry(submitted=False), "submitted") is False
    assert gui_app.index_row_matches_chip(_entry(accepted=True), "accepted") is True
    assert gui_app.index_row_matches_chip(_entry(accepted=False), "accepted") is False


def test_valve_kind_works_too():
    values = {"valve_serial": "VS-1"}
    entry = _entry(values=values)
    entry["progress"] = da.compute_progress(
        "valve", values, {"installed": False, "submitted": False, "accepted": False})
    assert gui_app.index_row_matches_chip(entry, "missing_serial") is False
