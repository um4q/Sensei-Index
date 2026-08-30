# -*- coding: utf-8 -*-
"""Phase 11.3 - create-from-master: master_item_to_row_values() and
create_rows_from_master_items()."""
import pytest


def _ml_item(tag, kind, mapped_series=29103, **overrides):
    item = {
        "tag_raw": tag, "tag": tag, "area": tag.split("-")[0], "tag_type": tag.split("-")[1],
        "service": "SVC", "type_desc": "", "kind": kind, "pid": "PID-1", "line_number": "LN-1",
        "module_id": "", "ewp": "", "model": "MODEL-1", "manufacturer": "ACME",
        "install_details": "", "remarks": "", "ml_received": False, "ml_installed": False,
        "source_sheet": "Sheet1", "mapped_series": mapped_series,
    }
    item.update(overrides)
    return item


def test_transmitter_field_mapping(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    item = _ml_item("29103-PIT-2171", "transmitter")
    values = da.master_item_to_row_values(item, "transmitter")
    assert values == {
        "tag": "29103-PIT-2171", "service": "SVC", "pid_number": "PID-1",
        "line_number": "LN-1", "make": "ACME", "model": "MODEL-1",
    }


def test_valve_field_mapping_has_no_service_or_manufacturer_target(isolated_app_dir):
    """Valve schema has no generic service/manufacturer field - those two
    are silently omitted, not stuffed somewhere they don't belong."""
    tmp_path, da = isolated_app_dir
    item = _ml_item("29103-XV-0100", "valve")
    values = da.master_item_to_row_values(item, "valve")
    assert values == {
        "equip_number": "29103-XV-0100", "pid_number": "PID-1",
        "line_number": "LN-1", "valve_model": "MODEL-1",
    }
    assert "service" not in values
    assert "manufacturer" not in values


def test_blank_master_fields_are_omitted(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    item = _ml_item("29103-PIT-2171", "transmitter", pid="", line_number="", manufacturer="")
    values = da.master_item_to_row_values(item, "transmitter")
    assert "pid_number" not in values
    assert "line_number" not in values
    assert "make" not in values


def test_default_qa_rep_name_prefills_when_set(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_setting("default_qa_rep_name", "J. Smith")
    values = da.master_item_to_row_values(_ml_item("29103-PIT-2171", "transmitter"), "transmitter")
    assert values["yanda_qa_name"] == "J. Smith"

    valve_values = da.master_item_to_row_values(_ml_item("29103-XV-0100", "valve"), "valve")
    assert valve_values["qc_rep_name"] == "J. Smith"


def test_default_qa_rep_name_absent_when_unset(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    values = da.master_item_to_row_values(_ml_item("29103-PIT-2171", "transmitter"), "transmitter")
    assert "yanda_qa_name" not in values


def test_create_rows_writes_prefilled_rows_and_returns_refs(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    items = [
        ("transmitter", _ml_item("29103-PIT-2171", "transmitter")),
        ("valve", _ml_item("29103-XV-0100", "valve")),
    ]
    created = da.create_rows_from_master_items(items)
    assert len(created) == 2

    rows = da.read_index_rows(29103, "transmitter")
    assert any(r["tag"] == "29103-PIT-2171" for r in rows)
    valve_rows = da.read_index_rows(29103, "valve")
    assert any(r["equip_number"] == "29103-XV-0100" for r in valve_rows)


def test_create_rows_same_sheet_uses_distinct_rows(isolated_app_dir):
    """Regression guard: two items landing on the SAME sheet in one batch
    must not collide on the same 'first blank row'."""
    tmp_path, da = isolated_app_dir
    items = [
        ("transmitter", _ml_item("29103-PIT-2171", "transmitter")),
        ("transmitter", _ml_item("29103-PIT-2172", "transmitter")),
        ("transmitter", _ml_item("29103-PIT-2173", "transmitter")),
    ]
    created = da.create_rows_from_master_items(items)
    row_nums = [c["row"] for c in created]
    assert len(set(row_nums)) == 3  # all distinct

    tags = {r["tag"] for r in da.read_index_rows(29103, "transmitter")}
    assert tags == {"29103-PIT-2171", "29103-PIT-2172", "29103-PIT-2173"}


def test_create_rows_is_one_workbook_save_for_the_whole_batch(isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    save_calls = []
    original_save = da._save_workbook_and_refresh_cache

    def counting_save(wb):
        save_calls.append(1)
        return original_save(wb)

    monkeypatch.setattr(da, "_save_workbook_and_refresh_cache", counting_save)
    items = [
        ("transmitter", _ml_item("29103-PIT-2171", "transmitter")),
        ("valve", _ml_item("29103-XV-0100", "valve")),
        ("transmitter", _ml_item("29103-PIT-2172", "transmitter")),
    ]
    da.create_rows_from_master_items(items)
    assert len(save_calls) == 1


def test_create_rows_all_or_nothing_when_a_series_is_unmapped(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    items = [
        ("transmitter", _ml_item("29103-PIT-2171", "transmitter", mapped_series=29103)),
        ("transmitter", _ml_item("29103-PIT-2172", "transmitter", mapped_series=None)),  # unmapped
    ]
    with pytest.raises(ValueError):
        da.create_rows_from_master_items(items)

    # nothing from the batch was written - all or nothing
    tags = {r["tag"] for r in da.read_index_rows(29103, "transmitter")}
    assert "29103-PIT-2171" not in tags


def test_create_rows_rejects_unregistered_series(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    items = [("transmitter", _ml_item("29103-PIT-2171", "transmitter", mapped_series=999999))]
    with pytest.raises(ValueError):
        da.create_rows_from_master_items(items)
