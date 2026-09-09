# -*- coding: utf-8 -*-
"""Phase 13.1 (filter chips) and 13.7 (empty state), wired into a real
IndexPage."""
import gui_app


def test_empty_series_shows_empty_state_not_bare_grid(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    page.show()

    assert page.empty_state.isVisible()
    assert not page.table.isVisible()


def test_nonempty_series_shows_table_not_empty_state(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    page.show()

    assert page.table.isVisible()
    assert not page.empty_state.isVisible()


def test_search_filtering_to_zero_does_not_trigger_empty_state(qtbot, isolated_app_dir, fake_main_window):
    """0-of-N-shown (a search/chip that matches nothing) is NOT the same
    as the series having zero rows - the table (with its 'nothing
    matched' count) stays, the empty state must not appear."""
    tmp_path, da = isolated_app_dir
    row_num = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", row_num, {"tag": "29103-PIT-2171"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    page.show()

    page.search_edit.setText("nothing matches this search string")
    assert page.table.isVisible()
    assert not page.empty_state.isVisible()
    assert page.table.rowCount() == 0
    assert page.count_label.text() == "0 of 1"


def test_chips_compose_with_search(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001"})
    da.set_status(29103, "transmitter", "29103-PIT-0001", installed=True)
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-FIT-0002"})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    page.chips.set_active("installed")
    page.apply_filter()
    assert page.table.rowCount() == 1
    assert page.table.item(0, page.columns.index("tag")).text() == "29103-PIT-0001"

    # composes with search: chip=installed AND search="FIT" -> nothing
    page.search_edit.setText("FIT")
    assert page.table.rowCount() == 0


def test_chips_and_dashboard_drill_down_filters_compose(qtbot, isolated_app_dir, fake_main_window):
    """13's own acceptance criterion: chips + search + dashboard drill-
    down filters compose (all three at once)."""
    tmp_path, da = isolated_app_dir
    r1 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r1, {"tag": "29103-PIT-0001", "system_number": "STEAM"})
    da.set_status(29103, "transmitter", "29103-PIT-0001", installed=True)
    r2 = da.find_first_blank_row(29103, "transmitter")
    da.save_row(29103, "transmitter", r2, {"tag": "29103-PIT-0002", "system_number": "GAS"})
    da.set_status(29103, "transmitter", "29103-PIT-0002", installed=True)

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter",
                              filters={"system_number": "STEAM"})
    qtbot.addWidget(page)
    page.chips.set_active("installed")
    page.apply_filter()

    assert page.table.rowCount() == 1
    assert page.table.item(0, page.columns.index("tag")).text() == "29103-PIT-0001"
    # the breadcrumb for the dashboard-drilldown filter is still shown
    assert page.filters == {"system_number": "STEAM"}


def test_chip_bar_defaults_to_all(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    assert page.chips.active_id == "all"
