# -*- coding: utf-8 -*-
"""Phase 12.1 - compute_progress(). Pure function: no workbook, no
sidecars, no fixtures needed beyond hand-built dicts (per the spec's own
acceptance criterion)."""
import data_access as da

NO_STATUS = {"installed": False, "submitted": False, "accepted": False}
FULL_STATUS = {"installed": True, "submitted": True, "accepted": True}


def _milestone(result, mid):
    return next(m for m in result["milestones"] if m["id"] == mid)


# --------------------------------------------------------------- transmitter
def test_transmitter_just_created_only_created_is_done():
    result = da.compute_progress("transmitter", {}, {})
    assert _milestone(result, "created")["done"] is True
    for mid in ("serial_captured", "installed", "inspection_complete", "submitted", "accepted"):
        assert _milestone(result, mid)["done"] is False
    assert result["percent"] == round(100 / 6)
    assert result["next"] == "serial_captured"


def test_transmitter_serial_captured_when_serial_number_filled():
    result = da.compute_progress("transmitter", {"serial_number": "SN-123"}, {})
    assert _milestone(result, "serial_captured")["done"] is True
    assert result["next"] == "installed"


def test_transmitter_serial_blank_or_whitespace_not_captured():
    for blank in ("", "   ", None):
        result = da.compute_progress("transmitter", {"serial_number": blank}, {})
        assert _milestone(result, "serial_captured")["done"] is False


def test_transmitter_inspection_requires_every_vi_and_proc_field():
    values = {f"vi_{i}": "X" for i in range(1, 13)}
    values.update({f"proc_{i}": "Pass" for i in range(2, 15)})
    result = da.compute_progress("transmitter", values, {})
    assert _milestone(result, "inspection_complete")["done"] is True

    # missing exactly one field (vi_12) -> not complete
    incomplete = dict(values)
    incomplete["vi_12"] = ""
    result = da.compute_progress("transmitter", incomplete, {})
    assert _milestone(result, "inspection_complete")["done"] is False


def test_transmitter_inspection_complete_ignores_proc_1_vdc():
    """proc_1_vdc is a voltage measurement, not a pass/fail item - the spec
    explicitly scopes 'inspection complete' to vi_1..vi_12 + proc_2..proc_14."""
    values = {f"vi_{i}": "X" for i in range(1, 13)}
    values.update({f"proc_{i}": "Pass" for i in range(2, 15)})
    values["proc_1_vdc"] = ""  # left blank
    result = da.compute_progress("transmitter", values, {})
    assert _milestone(result, "inspection_complete")["done"] is True


def test_transmitter_fully_done_is_100_percent_with_no_next():
    values = {"serial_number": "SN-1"}
    values.update({f"vi_{i}": "X" for i in range(1, 13)})
    values.update({f"proc_{i}": "Pass" for i in range(2, 15)})
    result = da.compute_progress("transmitter", values, FULL_STATUS)
    assert result["percent"] == 100
    assert result["next"] is None
    assert all(m["done"] for m in result["milestones"])


def test_toggling_installed_status_changes_percent_alone():
    values = {"serial_number": "SN-1"}
    before = da.compute_progress("transmitter", values, {"installed": False})
    after = da.compute_progress("transmitter", values, {"installed": True})
    assert after["percent"] > before["percent"]
    assert _milestone(after, "installed")["done"] is True
    assert _milestone(before, "installed")["done"] is False


# ---------------------------------------------------------------------- valve
def test_valve_just_created_only_created_is_done():
    result = da.compute_progress("valve", {}, {})
    assert _milestone(result, "created")["done"] is True
    assert _milestone(result, "serial_captured")["done"] is False
    assert result["next"] == "serial_captured"


def test_valve_serial_captured_needs_the_valve_serial_itself():
    result = da.compute_progress("valve", {"valve_serial": "VS-1"}, {})
    assert _milestone(result, "serial_captured")["done"] is True


def test_valve_component_serial_only_required_when_its_model_is_set():
    # positioner_model filled but positioner_serial blank -> gated, not done
    values = {"valve_serial": "VS-1", "positioner_model": "POS-9000"}
    result = da.compute_progress("valve", values, {})
    assert _milestone(result, "serial_captured")["done"] is False

    # fill in the gated serial -> now complete
    values["positioner_serial"] = "PS-1"
    result = da.compute_progress("valve", values, {})
    assert _milestone(result, "serial_captured")["done"] is True


def test_valve_component_without_a_model_is_not_penalized():
    # no solenoid/actuator/position_limit model anywhere on this valve -
    # their serials being blank must NOT block serial_captured.
    values = {"valve_serial": "VS-1"}
    result = da.compute_progress("valve", values, {})
    assert _milestone(result, "serial_captured")["done"] is True


def test_valve_inspection_requires_every_fv_field():
    values = {f"fv_{i}": "JD" for i in range(1, 9)}
    result = da.compute_progress("valve", values, {})
    assert _milestone(result, "inspection_complete")["done"] is True

    values["fv_8"] = ""
    result = da.compute_progress("valve", values, {})
    assert _milestone(result, "inspection_complete")["done"] is False


# ------------------------------------------------------------------- general
def test_milestone_order_is_fixed():
    result = da.compute_progress("transmitter", {}, {})
    ids = [m["id"] for m in result["milestones"]]
    assert ids == ["created", "serial_captured", "installed",
                    "inspection_complete", "submitted", "accepted"]


def test_weights_are_a_plain_dict_reweighting_changes_percent(monkeypatch):
    """Spec assumption 12.4: 'if the client weighs milestones differently
    ... it's a one-dict change'. Prove PROGRESS_WEIGHTS is actually load-
    bearing, not just documentation."""
    values = {"serial_number": "SN-1"}  # created + serial_captured done, 2 of 6
    equal = da.compute_progress("transmitter", values, {})

    heavy = dict(da.PROGRESS_WEIGHTS["transmitter"])
    heavy["accepted"] = 100  # accepted now dominates the total
    monkeypatch.setitem(da.PROGRESS_WEIGHTS, "transmitter", heavy)
    reweighted = da.compute_progress("transmitter", values, {})

    assert reweighted["percent"] < equal["percent"]  # same 2 milestones, much bigger denominator


def test_compute_progress_is_pure_no_io(monkeypatch):
    """Never touches the workbook or a sidecar - patch every I/O entry
    point data_access has to a hard failure and confirm it still works."""
    def boom(*a, **k):
        raise AssertionError("compute_progress must not touch disk")

    monkeypatch.setattr(da, "_get_cached_workbook", boom)
    monkeypatch.setattr(da, "_load_status_store", boom)
    monkeypatch.setattr(da, "load_config", boom)

    result = da.compute_progress("transmitter", {"serial_number": "SN-1"}, {"installed": True})
    assert result["percent"] > 0
