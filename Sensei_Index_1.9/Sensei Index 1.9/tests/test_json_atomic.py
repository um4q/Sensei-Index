# -*- coding: utf-8 -*-
"""Phase 16.3 - atomic JSON writes + corrupt-sidecar recovery."""
import json

import pytest


def test_write_json_atomic_round_trips(tmp_path, isolated_app_dir):
    _, da = isolated_app_dir
    path = tmp_path / "thing.json"
    da.write_json_atomic(path, {"a": 1, "b": [1, 2, 3]})
    assert json.loads(path.read_text(encoding="utf-8")) == {"a": 1, "b": [1, 2, 3]}


def test_write_json_atomic_leaves_no_temp_file_behind(tmp_path, isolated_app_dir):
    _, da = isolated_app_dir
    path = tmp_path / "thing.json"
    da.write_json_atomic(path, {"a": 1})
    leftovers = list(tmp_path.glob(".thing.json.tmp*"))
    assert leftovers == []


def test_write_json_atomic_never_leaves_a_truncated_file(tmp_path, isolated_app_dir, monkeypatch):
    """Simulates a crash mid-write (os.replace never happens): the
    original file must be untouched and no stray temp file left over."""
    _, da = isolated_app_dir
    path = tmp_path / "thing.json"
    da.write_json_atomic(path, {"version": 1})

    def boom(*a, **k):
        raise OSError("simulated crash")

    monkeypatch.setattr(da.os, "replace", boom)
    with pytest.raises(OSError):
        da.write_json_atomic(path, {"version": 2})

    # old file survives untouched - never a half-written v2
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 1}
    assert list(tmp_path.glob(".thing.json.tmp*")) == []


def test_read_json_with_recovery_missing_file_returns_default_silently(tmp_path, isolated_app_dir):
    _, da = isolated_app_dir
    da.STARTUP_WARNINGS.clear()
    result = da.read_json_with_recovery(tmp_path / "nope.json", lambda: {"series": []})
    assert result == {"series": []}
    assert da.STARTUP_WARNINGS == []


def test_read_json_with_recovery_corrupt_file_resets_and_warns(tmp_path, isolated_app_dir):
    _, da = isolated_app_dir
    da.STARTUP_WARNINGS.clear()
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json at all", encoding="utf-8")

    result = da.read_json_with_recovery(path, dict)

    assert result == {}
    assert not path.exists()  # renamed away, not left in place
    corrupt_copies = list(tmp_path.glob("corrupt.json.corrupt.*"))
    assert len(corrupt_copies) == 1
    assert corrupt_copies[0].read_text(encoding="utf-8") == "{not valid json at all"
    assert len(da.STARTUP_WARNINGS) == 1
    assert "corrupt.json" in da.STARTUP_WARNINGS[0]


def test_corrupt_series_registry_degrades_to_empty_not_a_crash(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.STARTUP_WARNINGS.clear()
    da.CONFIG_PATH.write_text("}{ garbage", encoding="utf-8")

    assert da.list_series() == []  # no crash
    assert any("series_registry.json" in w for w in da.STARTUP_WARNINGS)


def test_missing_series_registry_is_not_a_crash(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.CONFIG_PATH.unlink()
    assert da.list_series() == []
