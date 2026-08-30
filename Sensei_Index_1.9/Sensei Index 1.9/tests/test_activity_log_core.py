# -*- coding: utf-8 -*-
"""Phase 15 - activity_log.jsonl: log_activity / read_activity_log /
rotation. (The choke-point hooks themselves - save_row etc. - are
covered in test_activity_log_hooks.py.)"""
import json


def test_log_and_read_round_trip(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4,
                     key_value="29103-PIT-2171",
                     fields={"serial_number": {"old": "", "new": "SN-1"}}, source="edit_dialog")
    entries = da.read_activity_log()
    assert len(entries) == 1
    assert entries[0]["action"] == "edit"
    assert entries[0]["fields"]["serial_number"] == {"old": "", "new": "SN-1"}


def test_read_activity_log_is_newest_first(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A",
                     ts="2026-08-30T10:00:00")
    da.log_activity("edit", series=29103, equip_key="transmitter", row=5, key_value="B",
                     ts="2026-08-30T11:00:00")
    entries = da.read_activity_log()
    assert [e["key_value"] for e in entries] == ["B", "A"]


def test_read_activity_log_filters_by_row(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A")
    da.log_activity("edit", series=29103, equip_key="transmitter", row=5, key_value="B")
    entries = da.read_activity_log(series=29103, equip_key="transmitter", row=4)
    assert len(entries) == 1
    assert entries[0]["key_value"] == "A"


def test_read_activity_log_respects_limit(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    for i in range(15):
        da.log_activity("edit", series=29103, equip_key="transmitter", row=i, key_value=str(i))
    entries = da.read_activity_log(limit=10)
    assert len(entries) == 10


def test_missing_log_file_returns_empty_not_crash(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert not da.ACTIVITY_LOG_PATH.exists()
    assert da.read_activity_log() == []


def test_corrupt_line_is_skipped_not_fatal(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A")
    with open(da.ACTIVITY_LOG_PATH, "a", encoding="utf-8") as fh:
        fh.write("{not valid json\n")
        fh.write("\n")  # blank line too
    da.log_activity("edit", series=29103, equip_key="transmitter", row=5, key_value="B")

    entries = da.read_activity_log()
    assert len(entries) == 2  # the corrupt/blank lines were skipped, not fatal


def test_hand_deleted_log_file_does_not_break_logging(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A")
    da.ACTIVITY_LOG_PATH.unlink()
    da.log_activity("edit", series=29103, equip_key="transmitter", row=5, key_value="B")
    entries = da.read_activity_log()
    assert len(entries) == 1
    assert entries[0]["key_value"] == "B"


def test_fields_are_truncated(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    huge = "X" * 5000
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A",
                     fields={"remarks": {"old": "", "new": huge}})
    entries = da.read_activity_log()
    assert len(entries[0]["fields"]["remarks"]["new"]) <= da.ACTIVITY_LOG_FIELD_TRUNCATE + 1


def test_shared_ts_across_a_batch(isolated_app_dir):
    """A bulk action touching N rows shares one ts across all N events -
    15's own documented convention."""
    tmp_path, da = isolated_app_dir
    shared_ts = "2026-08-30T12:00:00"
    for i in range(3):
        da.log_activity("edit", series=29103, equip_key="transmitter", row=i,
                         key_value=str(i), source="bulk", ts=shared_ts)
    entries = da.read_activity_log()
    assert len(entries) == 3
    assert all(e["ts"] == shared_ts for e in entries)
    assert all(e["source"] == "bulk" for e in entries)


def test_rotation_keeps_exactly_one_prior_generation(isolated_app_dir, monkeypatch):
    tmp_path, da = isolated_app_dir
    monkeypatch.setattr(da, "ACTIVITY_LOG_ROTATE_BYTES", 200)  # force rotation quickly
    for i in range(30):
        da.log_activity("edit", series=29103, equip_key="transmitter", row=i,
                         key_value=f"29103-PIT-{i:04d}", fields={"remarks": {"old": "", "new": "x" * 20}})
    assert da.ACTIVITY_LOG_PATH.exists()
    rotated = tmp_path / "activity_log.1.jsonl"
    assert rotated.exists()  # rotation actually happened
    # never more than one prior generation
    assert not (tmp_path / "activity_log.2.jsonl").exists()


def test_logging_never_raises_on_write_failure(isolated_app_dir, monkeypatch, capsys):
    tmp_path, da = isolated_app_dir

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", boom)
    da.log_activity("edit", series=29103, equip_key="transmitter", row=4, key_value="A")  # must not raise
    captured = capsys.readouterr()
    assert "WARNING" in captured.out
