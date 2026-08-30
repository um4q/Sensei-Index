# -*- coding: utf-8 -*-
"""Phase 13.2 - frozen Row #/Tag columns via a shared-model overlay
QTableView."""
import gui_app


def _seed_rows(da, series_number, tags):
    for tag in tags:
        row = da.find_first_blank_row(series_number, "transmitter")
        da.save_row(series_number, "transmitter", row, {"tag": tag})


def test_frozen_table_shares_model_and_selection_model(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    assert page.frozen_table.model() is page.table.model()
    assert page.frozen_table.selectionModel() is page.table.selectionModel()


def test_frozen_table_hides_every_column_past_the_pinned_two(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    for col in range(page.table.columnCount()):
        hidden = page.frozen_table.isColumnHidden(col)
        assert hidden == (col >= page.FROZEN_COLUMN_COUNT), col


def test_frozen_table_mirrors_row_and_tag_content(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    tag_col = page.columns.index("tag")
    model = page.table.model()
    assert model.data(model.index(0, 0)) == page.table.item(0, 0).text()
    assert model.data(model.index(0, tag_col)) == "29103-PIT-0001"
    # frozen_table renders from the SAME model - no separate read needed,
    # but confirm it's actually showing that data (not blank/stale).
    assert page.frozen_table.model().data(page.frozen_table.model().index(0, tag_col)) == "29103-PIT-0001"


def test_selecting_a_row_in_main_table_reflects_in_frozen_table(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001", "29103-PIT-0002"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    page.table.selectRow(0)
    assert page.frozen_table.selectionModel().isRowSelected(0, page.frozen_table.rootIndex())


def test_resizing_a_pinned_column_syncs_to_frozen_table(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    tag_col = page.columns.index("tag")
    page.table.setColumnWidth(tag_col, 250)
    assert page.frozen_table.columnWidth(tag_col) == 250


def test_resizing_a_non_pinned_column_does_not_change_frozen_width(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    non_pinned_col = page.FROZEN_COLUMN_COUNT
    before = [page.frozen_table.columnWidth(c) for c in range(page.FROZEN_COLUMN_COUNT)]
    page.table.setColumnWidth(non_pinned_col, 200)
    after = [page.frozen_table.columnWidth(c) for c in range(page.FROZEN_COLUMN_COUNT)]
    assert before == after


def test_sorting_the_main_table_reorders_frozen_table_too(qtbot, isolated_app_dir, fake_main_window):
    """Both views share one model - sorting is inherently synced, no
    extra code needed. Confirm that's actually true."""
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0002", "29103-PIT-0001"])  # inserted out of order

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    tag_col = page.columns.index("tag")
    page.table.sortByColumn(tag_col, gui_app.Qt.AscendingOrder)

    main_first = page.table.item(0, tag_col).text()
    frozen_first = page.frozen_table.model().data(page.frozen_table.model().index(0, tag_col))
    assert main_first == frozen_first == "29103-PIT-0001"


def test_frozen_table_geometry_matches_pinned_columns_total_width(qtbot, isolated_app_dir, fake_main_window):
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])

    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)

    expected_width = sum(page.table.columnWidth(c) for c in range(page.FROZEN_COLUMN_COUNT))
    assert page.frozen_table.width() == expected_width


def test_frozen_table_is_not_directly_editable(qtbot, isolated_app_dir, fake_main_window):
    """Editing happens through the main table only - avoids duplicating
    the DateEditDelegate / tag-shape-warning wiring onto a second view."""
    tmp_path, da = isolated_app_dir
    _seed_rows(da, 29103, ["29103-PIT-0001"])
    page = gui_app.IndexPage(fake_main_window, 29103, "transmitter")
    qtbot.addWidget(page)
    assert page.frozen_table.editTriggers() == gui_app.QAbstractItemView.NoEditTriggers
