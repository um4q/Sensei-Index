# -*- coding: utf-8 -*-
"""Phase 13.3 - sticky per-user IndexPage view state, round-tripped
through TWO separate IndexPage instances (simulating close app / reopen)."""
import gui_app


def _seed(da, series_number, tags):
    for tag in tags:
        row = da.find_first_blank_row(series_number, "transmitter")
        da.save_row(series_number, "transmitter", row, {"tag": tag})


def test_chip_selection_persists_across_reopen(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0001"])
    da.set_status(29103, "transmitter", "29103-PIT-0001", installed=True)

    page1 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page1)
    page1.chips._select("installed")  # simulates a real chip click (fires on_change)
    assert page1.chips.active_id == "installed"

    page2 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page2)
    assert page2.chips.active_id == "installed"


def test_sort_persists_across_reopen(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0002", "29103-PIT-0001"])

    page1 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page1)
    tag_col = page1.columns.index("tag")
    page1.table.sortByColumn(tag_col, gui_app.Qt.DescendingOrder)

    page2 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page2)
    header = page2.table.horizontalHeader()
    assert header.sortIndicatorSection() == tag_col
    assert header.sortIndicatorOrder() == gui_app.Qt.DescendingOrder
    assert page2.table.item(0, tag_col).text() == "29103-PIT-0002"  # descending -> higher first


def test_column_width_persists_across_reopen(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0001"])

    page1 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page1)
    date_field = page1.etype["date_fields"][0]
    date_col = page1.columns.index(date_field)
    page1.table.setColumnWidth(date_col, 222)

    page2 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page2)
    assert page2.table.columnWidth(date_col) == 222


def test_sort_chip_and_widths_all_persist_together(qtbot, isolated_app_dir, fake_main_window):
    """13's own acceptance criterion, verbatim: 'Close app, reopen: sort,
    widths, and chips restored per page.'"""
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0002", "29103-PIT-0001"])
    da.set_status(29103, "transmitter", "29103-PIT-0001", accepted=True)
    da.set_status(29103, "transmitter", "29103-PIT-0002", accepted=True)

    page1 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page1)
    page1.chips._select("accepted")
    tag_col = page1.columns.index("tag")
    page1.table.sortByColumn(tag_col, gui_app.Qt.DescendingOrder)
    date_field = page1.etype["date_fields"][0]
    date_col = page1.columns.index(date_field)
    page1.table.setColumnWidth(date_col, 200)

    page2 = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page2)
    assert page2.chips.active_id == "accepted"
    header = page2.table.horizontalHeader()
    assert header.sortIndicatorSection() == tag_col
    assert header.sortIndicatorOrder() == gui_app.Qt.DescendingOrder
    assert page2.table.columnWidth(date_col) == 200


def test_view_state_is_per_page_not_global(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0001"])
    row = da.find_first_blank_row(100, "transmitter")
    da.save_row(100, "transmitter", row, {"tag": "100-PIT-0001"})

    page_a = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page_a)
    page_a.chips._select("not_started")

    page_b = gui_app.IndexPage(fake_main_window, 100, "transmitter")
    qtbot.addWidget(page_b)
    assert page_b.chips.active_id == "all"  # unaffected by series 29103's saved chip


def test_default_state_used_when_nothing_saved_yet(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0001"])
    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    assert page.chips.active_id == "all"
    header = page.table.horizontalHeader()
    assert header.sortIndicatorSection() == 0
    assert header.sortIndicatorOrder() == gui_app.Qt.AscendingOrder


def test_restoring_does_not_immediately_resave_and_clobber_state(qtbot, isolated_app_dir, fake_main_window):
    """The _restoring_view_state guard: opening a page with saved state
    must not itself trigger a save. Proven with column_widths specifically
    (not sort_field/order, which restore sets correctly either way): if
    the guard were broken, sortByColumn()'s signal during restore would
    fire _save_view_state and overwrite the deliberately-empty {}
    column_widths below with the table's real (freshly restored, nonzero)
    widths."""
    tmp_path, da = isolated_app_dir
    _seed(da, 29103, ["29103-PIT-0001"])
    da.set_page_view_state(29103, "transmitter", chip="all", sort_field="tag",
                            sort_order="desc", column_widths={})

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    state = da.get_page_view_state(29103, "transmitter")
    assert state["column_widths"] == {}
    assert state["sort_field"] == "tag"
    assert state["sort_order"] == "desc"
