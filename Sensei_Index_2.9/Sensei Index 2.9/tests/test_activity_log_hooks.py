# -*- coding: utf-8 -*-
"""Phase 15 - the activity log's choke-point hooks: save_row,
save_fields_bulk, set_status, bulk_set_status, delete_rows,
create_rows_from_master_items, import_master_list."""


def test_save_row_logs_only_changed_fields(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171", "service": "SVC A"})

    entries = da.read_activity_log(series=29103, equip_key="transmitter", row=row)
    assert len(entries) == 1
    assert entries[0]["action"] == "edit"
    assert entries[0]["key_value"] == "29103-PIT-2171"
    assert entries[0]["fields"]["tag"] == {"old": "", "new": "29103-PIT-2171"}
    assert entries[0]["fields"]["service"] == {"old": "", "new": "SVC A"}
    assert entries[0]["source"] == "edit_dialog"


def test_save_row_no_op_logs_nothing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})  # identical - no change
    entries = da.read_activity_log(series=29103, equip_key="transmitter", row=row)
    assert len(entries) == 1  # only the first save produced an event


def test_save_row_source_override(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"}, source="wizard")
    entries = da.read_activity_log(series=29103, equip_key="transmitter", row=row)
    assert entries[0]["source"] == "wizard"


def test_save_fields_bulk_logs_one_event_per_row_shared_ts(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001"})
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-PIT-0002"})

    da.save_fields_bulk(29103, "transmitter", [
        (r1, "system_number", "STEAM"), (r2, "system_number", "STEAM"),
    ])

    e1 = da.read_activity_log(series=29103, equip_key="transmitter", row=r1)[0]
    e2 = da.read_activity_log(series=29103, equip_key="transmitter", row=r2)[0]
    assert e1["fields"]["system_number"] == {"old": "", "new": "STEAM"}
    assert e2["fields"]["system_number"] == {"old": "", "new": "STEAM"}
    assert e1["ts"] == e2["ts"]  # one shared timestamp for the whole batch
    assert e1["source"] == "bulk"


def test_delete_rows_logs_one_delete_event_per_cleared_row(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001"})
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-PIT-0002"})

    da.delete_rows(29103, "transmitter", [r1, r2])

    e1 = da.read_activity_log(series=29103, equip_key="transmitter", row=r1)
    assert e1[0]["action"] == "delete"
    assert e1[0]["key_value"] == "29103-PIT-0001"


def test_delete_rows_blank_row_logs_nothing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    blank_row = da.find_first_blank_row(29103, "transmitter")
    da.delete_rows(29103, "transmitter", [blank_row])  # was already blank
    assert da.read_activity_log(series=29103, equip_key="transmitter", row=blank_row) == []


def test_set_status_logs_status_event(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)

    entries = [e for e in da.read_activity_log(series=29103, equip_key="transmitter")
               if e["action"] == "status"]
    assert len(entries) == 1
    # log_activity's _truncate_for_log stringifies every field value (same
    # human-readable-text convention as every other field in the log) -
    # booleans become "True"/"False", not JSON true/false.
    assert entries[0]["fields"]["installed"] == {"old": "False", "new": "True"}
    assert entries[0]["key_value"] == "29103-PIT-2171"


def test_set_status_no_op_logs_nothing(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=False)  # already False
    entries = [e for e in da.read_activity_log() if e["action"] == "status"]
    assert entries == []


def test_bulk_set_status_logs_one_event_per_changed_key(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    keys = [(29103, "transmitter", "29103-PIT-0001"), (29103, "transmitter", "29103-PIT-0002")]
    da.bulk_set_status(keys, accepted=True)

    entries = [e for e in da.read_activity_log() if e["action"] == "status"]
    assert len(entries) == 2
    assert {e["key_value"] for e in entries} == {"29103-PIT-0001", "29103-PIT-0002"}
    assert entries[0]["ts"] == entries[1]["ts"]
    assert all(e["source"] == "bulk" for e in entries)


def test_create_rows_from_master_items_logs_source_master_list(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    item = {
        "tag": "29103-PIT-2171", "kind": "transmitter", "mapped_series": 29103,
        "service": "SVC", "pid": "", "line_number": "", "model": "", "manufacturer": "",
    }
    created = da.create_rows_from_master_items([("transmitter", item)])
    row_num = created[0]["row"]

    entries = da.read_activity_log(series=29103, equip_key="transmitter", row=row_num)
    assert len(entries) == 1
    assert entries[0]["source"] == "master_list"
    assert entries[0]["fields"]["tag"]["new"] == "29103-PIT-2171"


def test_import_master_list_logs_one_summary_event(isolated_app_dir, tmp_path):
    tmp_path2, da = isolated_app_dir
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Tag Number", "Service", "Instrument Type Description"])
    ws.append(["29103-PIT-2171", "SVC", "PRESSURE INDICATING TRANSMITTER"])
    ml_path = tmp_path2 / "ml.xlsx"
    wb.save(ml_path)

    da.import_master_list(ml_path, {"Sheet1": 29103})

    entries = [e for e in da.read_activity_log() if e["action"] == "master_list_import"]
    assert len(entries) == 1
    assert "1 row" in entries[0]["note"]


def test_read_row_history_merges_status_events_by_key_value(isolated_app_dir):
    """set_status doesn't carry a row number - read_row_history() still
    surfaces those events for the row via key_value."""
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.set_status(29103, "transmitter", "29103-PIT-2171", installed=True)

    history = da.read_row_history(29103, "transmitter", row, key_value="29103-PIT-2171")
    actions = {e["action"] for e in history}
    assert actions == {"edit", "status"}


def test_read_row_history_is_newest_first(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    row = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row, {"tag": "29103-PIT-2171"})
    da.save_row(29103, "transmitter", row, {"service": "SVC A"})
    history = da.read_row_history(29103, "transmitter", row, key_value="29103-PIT-2171")
    assert history[0]["fields"].get("service", {}).get("new") == "SVC A"
