# -*- coding: utf-8 -*-
"""Phase 13.3 - ui_state.json sticky per-page view state."""


def test_get_page_view_state_empty_when_nothing_saved(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert da.get_page_view_state(29103, "transmitter") == {}


def test_set_and_get_page_view_state_round_trips(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_page_view_state(29103, "transmitter", chip="installed", sort_field="tag", sort_order="asc")
    state = da.get_page_view_state(29103, "transmitter")
    assert state == {"chip": "installed", "sort_field": "tag", "sort_order": "asc"}


def test_set_page_view_state_merges_not_replaces(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_page_view_state(29103, "transmitter", chip="installed")
    da.set_page_view_state(29103, "transmitter", sort_field="tag")
    state = da.get_page_view_state(29103, "transmitter")
    assert state == {"chip": "installed", "sort_field": "tag"}


def test_page_view_state_keyed_independently_per_series_and_kind(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_page_view_state(29103, "transmitter", chip="installed")
    da.set_page_view_state(29103, "valve", chip="accepted")
    da.set_page_view_state(100, "transmitter", chip="submitted")

    assert da.get_page_view_state(29103, "transmitter")["chip"] == "installed"
    assert da.get_page_view_state(29103, "valve")["chip"] == "accepted"
    assert da.get_page_view_state(100, "transmitter")["chip"] == "submitted"


def test_ui_state_survives_missing_file(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    assert not da.UI_STATE_PATH.exists()
    assert da.load_ui_state() == {}
    assert da.get_page_view_state(29103, "transmitter") == {}


def test_ui_state_is_atomic_write(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    da.set_page_view_state(29103, "transmitter", chip="all")
    assert da.UI_STATE_PATH.exists()
    assert list(tmp_path.glob(".ui_state.json.tmp*")) == []
