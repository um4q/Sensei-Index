# -*- coding: utf-8 -*-
"""Phase 13.5 - warn-don't-block validation helpers."""


def test_tag_shape_warning_none_for_well_formed_tags(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    for tag in ("29103-PIT-2171", "29103-FIT-0916", "9050-FI-922", "A-B-C"):
        assert da.tag_shape_warning(tag) is None


def test_tag_shape_warning_flags_malformed_tags(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    for tag in ("29103PIT2171", "29103-PIT", "29103-PIT-2171-EXTRA", "just text"):
        warning = da.tag_shape_warning(tag)
        assert warning is not None
        assert tag in warning or tag.strip() in warning


def test_tag_shape_warning_none_for_blank():
    import data_access as da
    assert da.tag_shape_warning("") is None
    assert da.tag_shape_warning(None) is None
    assert da.tag_shape_warning("   ") is None


def test_find_rows_with_duplicate_serial_transmitter(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001", "serial_number": "SN-100"})
    r2 = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", r2, {"tag": "100-PIT-0002", "serial_number": "sn-100"})  # case differs

    matches = da.find_rows_with_duplicate_serial("transmitter", "SN-100")
    assert len(matches) == 2
    tags = {m["key_value"] for m in matches}
    assert tags == {"29103-PIT-0001", "100-PIT-0002"}


def test_find_rows_with_duplicate_serial_excludes_the_row_being_saved(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001", "serial_number": "SN-100"})

    matches = da.find_rows_with_duplicate_serial(
        "transmitter", "SN-100", exclude_series_row=(29103, r1))
    assert matches == []


def test_find_rows_with_duplicate_serial_blank_never_matches(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001"})  # serial left blank
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-PIT-0002"})  # also blank

    assert da.find_rows_with_duplicate_serial("transmitter", "") == []
    assert da.find_rows_with_duplicate_serial("transmitter", "   ") == []


def test_find_rows_with_duplicate_serial_valve_uses_valve_serial(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", r1, {"equip_number": "29103-XV-0001", "valve_model": "M1",
                                      "valve_serial": "VS-1"})
    r2 = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", r2, {"equip_number": "29103-XV-0002", "valve_model": "M1",
                                      "valve_serial": "VS-1"})

    matches = da.find_rows_with_duplicate_serial("valve", "VS-1")
    assert len(matches) == 2


def test_find_rows_with_duplicate_serial_valve_component_serials_excluded(isolated_app_dir):
    """13.5's scope is the single primary identifying serial per kind -
    valve component serials (actuator/positioner/...) are excluded, they're
    frequently legitimately reused parts."""
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", r1, {"equip_number": "29103-XV-0001", "positioner_serial": "PS-1"})
    r2 = da.find_first_blank_row(29103, "valve")
    da.save_row(29103, "valve", r2, {"equip_number": "29103-XV-0002", "positioner_serial": "PS-1"})

    assert da.find_rows_with_duplicate_serial("valve", "PS-1") == []


def test_no_duplicate_when_only_one_row_has_that_serial(isolated_app_dir):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001", "serial_number": "SN-UNIQUE"})
    matches = da.find_rows_with_duplicate_serial(
        "transmitter", "SN-UNIQUE", exclude_series_row=(29103, r1))
    assert matches == []
