# -*- coding: utf-8 -*-
"""
InstINDEX - a PySide6 front end for Equipment_Inspection_Tracker.xlsx.

    python gui_app.py

One window, sidebar navigation, no cascading popup windows for browsing -
Dashboard and every Series/Equipment-Type/System combination are just tree
items in a permanent sidebar. Add New, Edit, Settings, Signatures, and
Export remain focused dialogs, since those are one-off tasks rather than
places you navigate to and stay.
"""
import sys
import os
import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QSize, QItemSelectionModel, QDate
from PySide6.QtGui import QFont, QColor, QKeySequence, QShortcut, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QFormLayout, QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit,
    QScrollArea, QFrame, QTreeWidget, QTreeWidgetItem, QStackedWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QMessageBox,
    QInputDialog, QFileDialog, QCheckBox, QRadioButton, QButtonGroup,
    QGroupBox, QSizePolicy, QAbstractItemView, QSpacerItem, QAbstractScrollArea,
    QMenu, QStatusBar, QDateEdit,
)

import data_access as da
import datasheet_reader
from theme import LIGHT_QSS, DARK_QSS


APP_TITLE = "Sensei Index"


# =============================================================================
# Undo / Redo
#
# A small, generic command stack. Every reversible action in the app (a
# status checkbox flip, an Edit save, a row removal, an Add New) pushes one
# UndoAction here instead of mutating data directly and forgetting about it.
# Ctrl+Z pops and calls .undo(), Ctrl+Shift+Z calls .redo() on whatever was
# just undone. Kept intentionally simple (in-memory, cleared on app exit,
# capped at MAX_DEPTH) rather than a full transaction log - this is meant to
# undo "I didn't mean to click that" a moment ago, not to be a permanent
# audit trail (Excel's own edit history / the workbook itself is that).
# =============================================================================
class UndoAction:
    def __init__(self, description, undo_fn, redo_fn):
        self.description = description
        self.undo_fn = undo_fn
        self.redo_fn = redo_fn


class UndoManager:
    MAX_DEPTH = 50

    def __init__(self):
        self._undo_stack = []
        self._redo_stack = []

    def push(self, description, undo_fn, redo_fn):
        """Call this AFTER an action already happened, with undo_fn/redo_fn
        being zero-argument callables that reverse / redo it. Doing
        anything new always clears the redo stack - once you've made a
        fresh change, "redo" the old branch no longer makes sense."""
        self._undo_stack.append(UndoAction(description, undo_fn, redo_fn))
        if len(self._undo_stack) > self.MAX_DEPTH:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def undo(self):
        if not self._undo_stack:
            return None
        action = self._undo_stack.pop()
        action.undo_fn()
        self._redo_stack.append(action)
        return action.description

    def redo(self):
        if not self._redo_stack:
            return None
        action = self._redo_stack.pop()
        action.redo_fn()
        self._undo_stack.append(action)
        return action.description

    def clear(self):
        self._undo_stack.clear()
        self._redo_stack.clear()


# Small reusable widgets
class StatCard(QFrame):
    """One dashboard card: a big total, a subtitle, and a by-system
    breakdown list underneath - the Main Menu's answer to 'you only show
    the total.'"""

    def __init__(self, title, total, breakdown, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)

        num = QLabel(str(total))
        num.setObjectName("StatNumber")
        layout.addWidget(num, alignment=Qt.AlignHCenter)

        sub = QLabel(title)
        sub.setObjectName("StatLabel")
        layout.addWidget(sub, alignment=Qt.AlignHCenter)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: palette(mid);")
        layout.addWidget(line)

        by_system_label = QLabel("BY SYSTEM")
        by_system_label.setObjectName("SectionLabel")
        layout.addWidget(by_system_label)

        if not breakdown:
            none_label = QLabel("No data yet")
            none_label.setObjectName("StatLabel")
            layout.addWidget(none_label)
        for system, count in breakdown.items():
            row = QHBoxLayout()
            name = QLabel(system)
            name.setObjectName("StatLabel")
            val = QLabel(str(count))
            val.setStyleSheet("font-weight: 700;")
            row.addWidget(name)
            row.addStretch()
            row.addWidget(val)
            layout.addLayout(row)

        layout.addStretch()


class SeriesStatCard(QFrame):
    """One Dashboard 'BY SERIES' card: a series' display name, then a
    small Transmitters/Valves table with a Total column and an
    Installed/Submitted/Accepted breakdown column each - answers "how many
    transmitters and valves for THIS series, and how far along are they"
    without having to open the series and count by hand."""

    def __init__(self, series_number, summary, progress_summary=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        title = QLabel(da.series_display_label(series_number))
        title.setObjectName("SectionLabel")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(4)
        headers = ["", "Total", "Installed", "Submitted", "Accepted"]
        for c, h in enumerate(headers):
            lbl = QLabel(h)
            lbl.setObjectName("FieldLabel")
            lbl.setStyleSheet("font-weight: 700;")
            grid.addWidget(lbl, 0, c)

        row = 1
        progress_summary = progress_summary or {}
        for equip_key, etype in da.EQUIPMENT_TYPES.items():
            stats = summary.get(equip_key)
            name = QLabel(f"{etype['label']}s")
            grid.addWidget(name, row, 0)
            if stats is None:
                none_lbl = QLabel("\u2013")
                none_lbl.setObjectName("FieldLabel")
                grid.addWidget(none_lbl, row, 1, 1, 4)
                row += 1
                continue

            values = [stats["total"], stats["installed"], stats["submitted"], stats["accepted"]]
            for c, v in enumerate(values, start=1):
                val_lbl = QLabel(str(v))
                val_lbl.setStyleSheet("font-weight: 700;")
                grid.addWidget(val_lbl, row, c)
            row += 1

            # Phase 12.2 - additive: the existing Installed/Submitted/
            # Accepted numbers above are untouched; this is one more line
            # underneath, not a replacement.
            prog = progress_summary.get(equip_key)
            if prog:
                prog_row = QWidget()
                prog_layout = QHBoxLayout(prog_row)
                prog_layout.setContentsMargins(0, 0, 0, 0)
                prog_layout.setSpacing(8)
                pct_lbl = QLabel(f"{prog['avg_percent']}% avg")
                pct_lbl.setObjectName("FieldLabel")
                pct_lbl.setMinimumWidth(56)
                prog_layout.addWidget(pct_lbl)
                prog_layout.addWidget(
                    build_progress_segmented_bar(prog["at_0"], prog["partial"], prog["at_100"]),
                    stretch=1)
                grid.addWidget(prog_row, row, 0, 1, 5)
                row += 1

        layout.addLayout(grid)
        layout.addStretch()


def make_field_widget(field, initial_value):
    """Builds the right input widget for one schema field. Shared by
    EditDialog and the Populating Wizard's entry page, so a schema field
    always looks and behaves the same wherever it's edited."""
    if field["ftype"] == "choice":
        combo = QComboBox()
        combo.addItems(field["choices"])
        if initial_value in field["choices"]:
            combo.setCurrentText(initial_value)
        else:
            combo.setCurrentIndex(-1)
        return combo
    if field["ftype"] == "multiline":
        text = QTextEdit()
        text.setPlainText(initial_value)
        text.setFixedHeight(64)
        return text
    edit = QLineEdit()
    edit.setText(initial_value)
    return edit


def read_field_widget(widget):
    if isinstance(widget, QComboBox):
        return widget.currentText() if widget.currentIndex() >= 0 else ""
    if isinstance(widget, QTextEdit):
        return widget.toPlainText()
    return widget.text()


def make_button(text, object_name=None, width=None):
    btn = QPushButton(text)
    if object_name:
        btn.setObjectName(object_name)
    if width:
        btn.setMinimumWidth(width)
    return btn


class FilterChipBar(QWidget):
    """A row of mutually-exclusive toggle 'chips'. One reusable widget for
    every filter row in the app - Coverage (Phase 11) is the first user,
    IndexPage (Phase 13) reuses it rather than growing a second, slightly
    different filter-row implementation."""

    def __init__(self, options, on_change=None, parent=None):
        """options: [(id, base_label), ...], in display order. on_change,
        if given, is called with the newly active id every time the
        selection changes (not at construction)."""
        super().__init__(parent)
        self._on_change = on_change
        self._base_labels = dict(options)
        self._buttons = {}
        self.active_id = options[0][0] if options else None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for opt_id, label in options:
            btn = make_button(label, "FilterChip")
            btn.setCheckable(True)
            btn.setChecked(opt_id == self.active_id)
            btn.clicked.connect(lambda _checked, oid=opt_id: self._select(oid))
            self._group.addButton(btn)
            self._buttons[opt_id] = btn
            layout.addWidget(btn)
        layout.addStretch()

    def _select(self, opt_id):
        if opt_id == self.active_id:
            return
        self.active_id = opt_id
        if self._on_change:
            self._on_change(opt_id)

    def set_active(self, opt_id):
        """Programmatic selection (e.g. restoring a saved view) - does NOT
        fire on_change, matching QComboBox/QTreeWidget convention for
        silent state restoration."""
        if opt_id not in self._buttons:
            return
        self.active_id = opt_id
        self._buttons[opt_id].setChecked(True)

    def set_counts(self, counts):
        """counts: {id: int}. Appends ' (n)' to each chip whose id is
        present; leaves chips not in counts showing their bare label."""
        for opt_id, btn in self._buttons.items():
            base = self._base_labels[opt_id]
            if opt_id in counts:
                btn.setText(f"{base} ({counts[opt_id]})")
            else:
                btn.setText(base)


def _accepted_row_color():
    """Background for the Row # cell once Accepted is checked - picked per
    active theme so it still reads as 'success green' rather than
    clashing."""
    theme = da.get_setting("theme") or "light"
    return QColor("#2e6b48") if theme == "dark" else QColor("#8fd9a4")


def _submitted_row_color():
    """Background for the Row # cell once Submitted is checked (and
    Accepted is NOT) - amber/yellow, one rung below the green of
    Accepted, so a glance down the Row column alone tells you the
    installed -> submitted -> accepted stage of every piece of equipment."""
    theme = da.get_setting("theme") or "light"
    return QColor("#6b551f") if theme == "dark" else QColor("#f5dd8f")


def row_status_color(entry):
    """The single row-status color rule used everywhere a Row # cell is
    painted: Accepted wins over Submitted, Submitted colors it if Accepted
    isn't set yet, and a plain not-yet-submitted row gets no color override
    at all (falls back to the table's normal/alternating background)."""
    if entry.get("accepted"):
        return _accepted_row_color()
    if entry.get("submitted"):
        return _submitted_row_color()
    return None


def build_progress_segmented_bar(at_0, partial, at_100, height=8):
    """Phase 12.2 - a thin three-segment bar (not started / partial /
    100%) sized proportionally to the counts given, reusing the same
    theme-aware not-started/in-progress/complete tones as row_status_color
    so a glance at the Dashboard reads consistently with the Index grid's
    Row # coloring. Falls back to one neutral full-width segment when
    there's nothing to show (a series with zero rows)."""
    theme = da.get_setting("theme") or "light"
    neutral = "#3a3f55" if theme == "dark" else "#dde0e8"
    partial_color = _submitted_row_color().name()
    complete_color = _accepted_row_color().name()

    bar = QWidget()
    bar.setFixedHeight(height)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(1)

    segments = [(at_0, neutral), (partial, partial_color), (at_100, complete_color)]
    total = at_0 + partial + at_100
    if total == 0:
        segments = [(1, neutral)]
    for count, color in segments:
        if count <= 0:
            continue
        seg = QFrame()
        seg.setStyleSheet(f"background: {color}; border-radius: 2px;")
        layout.addWidget(seg, stretch=count)
    return bar


# =============================================================================
# Shared Rename/Remove Series flows - used from both the sidebar's
# right-click menu on a series and Settings > Manage Series, so the two
# entry points can never drift into different confirmation wording or
# safety behavior.
# =============================================================================
def rename_series_flow(parent_widget, series_number):
    current = da.get_series_name(series_number)
    text, ok = QInputDialog.getText(
        parent_widget, f"Rename \"{da.series_display_label(series_number)}\"",
        "Display name (leave blank to just show the number):", text=current)
    if not ok:
        return
    try:
        da.set_series_name(series_number, text)
    except Exception as exc:
        QMessageBox.critical(parent_widget, "Couldn't rename series", str(exc))


def remove_series_flow(parent_widget, series_number):
    label = da.series_display_label(series_number)
    warned = QMessageBox.warning(
        parent_widget, "Remove series",
        f'Remove "{label}"?\n\n'
        "This un-registers it from the app immediately - it won't show up "
        "in the sidebar, dashboard, or anywhere else. Its Transmitter and "
        "Valve Log sheets are archived (renamed and hidden) in the "
        "workbook rather than deleted, so the data itself isn't destroyed "
        "and a human can still recover it by hand in Excel (right-click "
        "any sheet tab \u2192 Unhide) if this was a mistake.",
        QMessageBox.Ok | QMessageBox.Cancel, QMessageBox.Cancel)
    if warned != QMessageBox.Ok:
        return
    confirm_text, ok = QInputDialog.getText(
        parent_widget, "Confirm removal", f'Type "{series_number}" to confirm:')
    if not ok:
        return
    if confirm_text.strip() != str(series_number):
        QMessageBox.information(parent_widget, "Cancelled",
                                 "Series was not removed - confirmation text didn't match.")
        return
    try:
        da.remove_series(series_number)
    except Exception as exc:
        QMessageBox.critical(parent_widget, "Couldn't remove series", str(exc))


# =============================================================================
# Main window: sidebar + stacked content
# =============================================================================
class MainWindow(QMainWindow):
    NAV_ROLE = Qt.UserRole

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        self.resize(1560, 820)
        self.undo_stack = UndoManager()

        central = QWidget()
        central.setAttribute(Qt.WA_StyledBackground, True)
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_sidebar())

        content_wrap = QWidget()
        content_wrap.setAttribute(Qt.WA_StyledBackground, True)
        content_wrap.setObjectName("ContentArea")
        content_layout = QVBoxLayout(content_wrap)
        content_layout.setContentsMargins(28, 24, 28, 24)
        self.stack = QStackedWidget()
        content_layout.addWidget(self.stack)
        root.addWidget(content_wrap, stretch=1)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready", 3000)

        self.dashboard_page = None
        self.current_dynamic_page = None
        self._rebuild_sidebar_tree()
        self.show_dashboard()
        self._install_shortcuts()

    # -------------------------------------------------------------- keybinds
    def _install_shortcuts(self):
        """App-wide utility keybinds. All are QShortcut(parent=self) with the
        default WindowShortcut context, so they fire whenever this window
        (or any of its child widgets) has focus - including from inside the
        Index table - but never steal keys from a modal dialog that's
        currently on top (Edit, Settings, the Wizard, ...), since those are
        separate top-level widgets. Every one of these is also listed, in
        plain language, in Instructions -> Keyboard Shortcuts."""
        def bind(sequence, handler):
            sc = QShortcut(QKeySequence(sequence), self)
            sc.setContext(Qt.WindowShortcut)
            sc.activated.connect(handler)
            return sc

        self._shortcuts = [
            bind("Ctrl+Z", self.undo_action),
            bind("Ctrl+Shift+Z", self.redo_action),
            bind("Ctrl+Y", self.redo_action),
            bind("Ctrl+N", self._shortcut_add_new),
            bind("Ctrl+E", self._shortcut_edit_selected),
            bind("Ctrl+F", self._shortcut_focus_search),
            bind("Ctrl+Shift+E", self._shortcut_open_export),
            bind("Ctrl+Shift+D", self._shortcut_mass_edit_dates),
            bind("Delete", self._shortcut_remove_selected),
            bind("F5", self._shortcut_refresh),
            bind("Ctrl+,", self.open_settings),
            bind("Ctrl+Shift+W", self.open_populating_wizard),
            bind("Ctrl+Shift+I", self.open_datasheet_import),
        ]

    def _active_index_page(self):
        page = self.current_dynamic_page
        return page if isinstance(page, IndexPage) else None

    def _shortcut_add_new(self):
        page = self._active_index_page()
        if page:
            page.add_new()

    def _shortcut_edit_selected(self):
        page = self._active_index_page()
        if page:
            page.edit_selected()

    def _shortcut_focus_search(self):
        page = self._active_index_page()
        if page:
            page.search_edit.setFocus()
            page.search_edit.selectAll()

    def _shortcut_remove_selected(self):
        page = self._active_index_page()
        if page and not page.search_edit.hasFocus():
            page.remove_selected()

    def _shortcut_refresh(self):
        page = self._active_index_page()
        if page:
            page.reload()
            self.statusBar().showMessage("Refreshed", 2000)
        else:
            self.refresh_sidebar_and_dashboard()

    def _shortcut_open_export(self):
        page = self._active_index_page()
        if page:
            page.open_export()

    def _shortcut_mass_edit_dates(self):
        page = self._active_index_page()
        if page:
            page.open_mass_edit_dates()

    def undo_action(self):
        desc = self.undo_stack.undo()
        if desc:
            self.statusBar().showMessage(f"Undid: {desc}", 4000)
        else:
            self.statusBar().showMessage("Nothing to undo", 2000)

    def redo_action(self):
        desc = self.undo_stack.redo()
        if desc:
            self.statusBar().showMessage(f"Redid: {desc}", 4000)
        else:
            self.statusBar().showMessage("Nothing to redo", 2000)

    # ---------------------------------------------------------------- sidebar
   
    def _build_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(290)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header_row = QHBoxLayout()
        header_row.setContentsMargins(30, 12, 16, 0)  # match whatever padding your sidebar already uses
     
        header_row.setSpacing(0)

        logo_label = QLabel()
        logo_label.setObjectName("SidebarLogo")
        self._set_logo_pixmap(logo_label)
        header_row.addWidget(logo_label)


        title = QLabel("Sensei Index 1.9")
        title.setObjectName("SidebarTitle")
        header_row.addWidget(title)
        header_row.addStretch()

        layout.addLayout(header_row)
        subtitle = QLabel("K1B Equipment Tracker")
        subtitle.setObjectName("SidebarSubtitle")
        layout.addWidget(subtitle)

        self.tree = QTreeWidget()
        self.tree.setObjectName("SidebarTree")
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(12)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_tree_context_menu)
        layout.addWidget(self.tree, stretch=1)

        add_series_btn = make_button("+ Add New Series", "SidebarFooterButton")
        add_series_btn.clicked.connect(self.add_series)
        layout.addWidget(add_series_btn)

        wizard_btn = make_button("\U0001F9D9  Populating Wizard", "SidebarFooterButton")
        wizard_btn.setToolTip("Bulk-enter a batch of similar equipment "
                               "(Ctrl+Shift+W)")
        wizard_btn.clicked.connect(self.open_populating_wizard)
        layout.addWidget(wizard_btn)

        datasheet_btn = make_button("\U0001F4C4  Import Datasheet PDF...", "SidebarFooterButton")
        datasheet_btn.setToolTip("Pre-fill a new row from an engineering data "
                                  "sheet PDF instead of retyping it (Ctrl+Shift+I)")
        datasheet_btn.clicked.connect(self.open_datasheet_import)
        layout.addWidget(datasheet_btn)

        master_list_btn = make_button("\U0001F4CB  Master List...", "SidebarFooterButton")
        master_list_btn.setToolTip("Import the client's Instrumentation Master List "
                                    "for coverage tracking (Coverage, in the sidebar)")
        master_list_btn.clicked.connect(self.open_master_list_import)
        layout.addWidget(master_list_btn)

        drive_btn = make_button("\u2601  Connect to Drive", "SidebarFooterButton")
        drive_btn.setToolTip("Cloud backup / sync - not built yet")
        drive_btn.clicked.connect(self.connect_to_drive)
        layout.addWidget(drive_btn)

        settings_btn = make_button("\u2699  Settings", "SidebarFooterButton")
        settings_btn.setToolTip("Theme, default export options, series, "
                                 "signatures (Ctrl+,)")
        settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(settings_btn)

        instructions_btn = make_button("\u2139  Instructions", "SidebarFooterButton")
        instructions_btn.setToolTip("What every button and shortcut does")
        instructions_btn.clicked.connect(self.show_instructions)
        layout.addWidget(instructions_btn)
        layout.addSpacing(8)

        return sidebar
    
 

    def _rebuild_sidebar_tree(self):
        self.tree.clear()

        dash_item = QTreeWidgetItem(["\u2302  Dashboard"])
        dash_item.setData(0, self.NAV_ROLE, ("dashboard",))
        self.tree.addTopLevelItem(dash_item)

        coverage_item = QTreeWidgetItem(["\u2611  Coverage"])
        coverage_item.setData(0, self.NAV_ROLE, ("coverage",))
        self.tree.addTopLevelItem(coverage_item)

        for series_number in da.list_series():
            series_item = QTreeWidgetItem([da.series_display_label(series_number)])
            series_item.setData(0, self.NAV_ROLE, ("series", series_number))
            self.tree.addTopLevelItem(series_item)

            for equip_key, etype in da.EQUIPMENT_TYPES.items():
                try:
                    count, by_system = da.series_type_summary(
                        series_number, equip_key, etype["group_fields"][0])
                except KeyError:
                    continue
                type_item = QTreeWidgetItem([f"{etype['label']}s  ({count})"])
                type_item.setData(0, self.NAV_ROLE, ("index", series_number, equip_key, None))
                series_item.addChild(type_item)

                if by_system:
                    sys_parent = QTreeWidgetItem(["By System"])
                    sys_parent.setData(0, self.NAV_ROLE, None)
                    type_item.addChild(sys_parent)
                    for system_value, n in by_system.items():
                        leaf_text = f"{system_value}  ({n})"
                        leaf = QTreeWidgetItem([leaf_text])
                        leaf.setToolTip(0, leaf_text)
                        leaf.setData(0, self.NAV_ROLE,
                                     ("index", series_number, equip_key,
                                      {etype["group_fields"][0]: system_value}))
                        sys_parent.addChild(leaf)
            series_item.setExpanded(True)

        dash_item.setSelected(True)

    def _on_tree_item_clicked(self, item, _column):
        nav = item.data(0, self.NAV_ROLE)
        if nav is None:
            item.setExpanded(not item.isExpanded())
            return
        if nav[0] == "dashboard":
            self.show_dashboard()
        elif nav[0] == "coverage":
            self.show_coverage()
        elif nav[0] == "series":
            item.setExpanded(not item.isExpanded())
        elif nav[0] == "index":
            _, series_number, equip_key, filters = nav
            self.show_index(series_number, equip_key, filters)

    def _on_tree_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if item is None:
            return
        nav = item.data(0, self.NAV_ROLE)
        if not (nav and nav[0] == "series"):
            return  # only series tabs get a context menu (not Dashboard, types, or systems)
        series_number = nav[1]

        menu = QMenu(self)
        rename_action = menu.addAction("Rename...")
        remove_action = menu.addAction("Remove...")
        chosen = menu.exec(self.tree.viewport().mapToGlobal(pos))
        if chosen == rename_action:
            rename_series_flow(self, series_number)
            self.refresh_sidebar_and_dashboard()
        elif chosen == remove_action:
            remove_series_flow(self, series_number)
            self.refresh_sidebar_and_dashboard()

    def refresh_sidebar_and_dashboard(self):
        """Call after anything that changes counts (save, add/remove/rename
        series, deleting rows, ...)."""
        self._rebuild_sidebar_tree()
        current = self.current_dynamic_page
        if isinstance(current, IndexPage) and current.series_number not in da.list_series():
            # The series being viewed just got removed out from under it
            # (via Settings, which stays reachable from the sidebar no
            # matter what's on screen) - don't leave a dead page showing.
            self.show_dashboard()
            return
        if self.stack.currentWidget() is self.dashboard_page or self.dashboard_page is None:
            self.show_dashboard()

    def refresh_current_view(self):
        """Called after an undo/redo so whatever's currently on screen
        reflects it. Deliberately looks up 'whatever Index page is showing
        RIGHT NOW' rather than having the undo/redo closures capture the
        page that was showing at the time of the original action - that
        page may have since been navigated away from and deleted, and
        calling a method on a deleted Qt widget raises. The underlying
        data is already updated either way; this only makes sure a
        currently-visible table doesn't show stale checkboxes."""
        page = self._active_index_page()
        if page is not None:
            page.reload()
        self.refresh_sidebar_and_dashboard()

    def _set_logo_pixmap(self, label):
        theme = da.get_setting("theme") or "light"
        filename = "oathplatehelm.png" if theme == "dark" else "oathplatehelm2.png"
        pixmap = QPixmap(str(da.ASSETS_DIR / filename))
        if not pixmap.isNull():
            label.setPixmap(pixmap.scaledToHeight(42, Qt.SmoothTransformation))

    # ------------------------------------------------------------- navigation
    def _set_dynamic_page(self, widget):
        if self.current_dynamic_page is not None:
            self.stack.removeWidget(self.current_dynamic_page)
            self.current_dynamic_page.deleteLater()
        self.stack.addWidget(widget)
        self.stack.setCurrentWidget(widget)
        self.current_dynamic_page = widget

    def show_dashboard(self):
        page = DashboardPage(self)
        self.dashboard_page = page
        self._set_dynamic_page(page)

    def show_coverage(self):
        page = CoveragePage(self)
        self._set_dynamic_page(page)

    def show_index(self, series_number, equip_key, filters=None):
        page = IndexPage(self, series_number, equip_key, filters)
        self._set_dynamic_page(page)

    # --------------------------------------------------------------- actions
    def add_series(self):
        existing = da.list_series()
        suggestion = (max(existing) + 100) if existing else 100
        number, ok = QInputDialog.getInt(
            self, "Add New Series",
            f"New series number (e.g. {suggestion}) - used internally to name "
            f"the sheets; you'll give it a friendlier display name next:",
            suggestion, 1, 999999)
        if not ok:
            return
        name, ok = QInputDialog.getText(
            self, "Name it",
            "Display name (e.g. \"K1B Pad B\") - shown everywhere instead of "
            "the number. Leave blank to just show the number:")
        if not ok:
            name = ""
        try:
            da.add_series(number)
            if name.strip():
                da.set_series_name(number, name.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't add series", str(exc))
            return
        QMessageBox.information(
            self, "Series added",
            f"\"{da.series_display_label(number)}\" created with empty Transmitter + "
            f"Valve logs.\n\nWorth a quick check in Excel that the new sheet's dropdown "
            f"columns still work - automatic sheet copies can occasionally miss one.")
        self.refresh_sidebar_and_dashboard()

    def open_settings(self):
        dlg = SettingsDialog(self, on_series_change=self.refresh_sidebar_and_dashboard)
        dlg.exec()
        self.apply_theme()
        self.refresh_sidebar_and_dashboard()

    def connect_to_drive(self):
        """Placeholder entry point for a future cloud-backup/sync
        integration. Deliberately does nothing to any data - it only tells
        the person this isn't built yet, rather than staying silent (a
        button that visibly does nothing is worse than one that's honest
        about being unfinished)."""
        QMessageBox.information(
            self, "Connect to Drive",
            "W.I.P.\n\nCloud sync isn't built yet - this button is a placeholder "
            "for a future update. Your data stays exactly where it is today: "
            "the workbook and JSON files next to the app.")

    def open_populating_wizard(self):
        dlg = PopulatingWizardDialog(self, self)
        dlg.exec()
        self.refresh_sidebar_and_dashboard()

    def open_datasheet_import(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import from Datasheet PDF(s)", "", "PDF files (*.pdf)")
        if not paths:
            return
        try:
            records = datasheet_reader.read_datasheet_pdfs(paths)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't read that PDF", str(exc))
            return
        if not records:
            QMessageBox.information(
                self, "No datasheets recognized",
                "Didn't find anything recognizable in the file(s) you picked.\n\n"
                "This importer currently supports the CNOOC/Oilsands-style "
                "\"DS-\" data sheets: Control Valve, On/Off Valve, Temp Trans "
                "Element and TW, Vortex Flowmeter, Pressure Transmitter, and "
                "Guided Wave Radar Level Transmitter. Anything else needs to "
                "be entered by hand, same as always.")
            return
        dlg = DatasheetImportDialog(self, self, records)
        dlg.exec()
        self.refresh_sidebar_and_dashboard()
        self.refresh_current_view()

    def open_master_list_import(self):
        dlg = MasterListImportDialog(self, self)
        dlg.exec()
        self.refresh_sidebar_and_dashboard()
        page = self.current_dynamic_page
        if isinstance(page, CoveragePage):
            page.reload()

    def show_instructions(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Instructions")
        dlg.resize(640, 680)
        layout = QVBoxLayout(dlg)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(self._build_app_guide_html() + self._build_workbook_instructions_html())
        layout.addWidget(text)
        close_btn = make_button("Close", "Ghost")
        close_btn.clicked.connect(dlg.accept)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(close_btn)
        layout.addLayout(row)
        dlg.exec()

    @staticmethod
    def _build_app_guide_html():
        """A hardcoded, always-available reference to what every button and
        shortcut in the APP ITSELF does - independent of whatever's in the
        workbook's own Instructions sheet (which only ever covered the
        paperwork side: how the paper forms map to Excel columns)."""

        def h(text):
            return f"<p style='font-weight:700; font-size:14px; margin-top:16px;'>{text}</p>"

        def sub(text):
            return f"<p style='font-weight:700; margin-top:10px;'>{text}</p>"

        def row(label, desc):
            return f"<p style='margin:2px 0;'><b>{label}</b> \u2013 {desc}</p>"

        parts = [h("APP GUIDE \u2013 InstINDEX")]

        parts.append(sub("Sidebar"))
        parts.append(row("Dashboard", "Overall totals, by-system breakdown, and a "
                          "per-series Installed/Submitted/Accepted card for every series."))
        parts.append(row("Series entries (e.g. \u201c100\u201d)", "Expand to jump straight to "
                          "that series' Transmitter or Valve Index, or drill into one System."))
        parts.append(row("+ Add New Series", "Duplicates an existing series' empty Log sheets "
                          "under a new series number."))
        parts.append(row("Populating Wizard", "Bulk-enter a batch of similar equipment \u2013 "
                          "see below (Ctrl+Shift+W)."))
        parts.append(row("Connect to Drive", "Placeholder for a future cloud-sync feature \u2013 "
                          "not built yet, and says so."))
        parts.append(row("Settings", "Theme, default export options, manage series, "
                          "manage signatures, open the raw Excel file (Ctrl+,)."))
        parts.append(row("Instructions", "This dialog."))

        parts.append(sub("Index page toolbar"))
        parts.append(row("+ Add New", "Opens a blank entry form in the first free row (Ctrl+N)."))
        parts.append(row("Show More", "Read-only listing of EVERY field on the selected row, "
                          "not just the few columns the table has room for."))
        parts.append(row("View Details", "Builds an actual filled PDF preview of the selected row."))
        parts.append(row("Edit", "Opens the full form for the selected row (Ctrl+E, or "
                          "double-click a data cell)."))
        parts.append(row("Export...", "Turn one or more rows into PDFs (Ctrl+Shift+E) \u2013 "
                          "see Export dialog below."))
        parts.append(row("Select All", "Selects every row the current search is showing."))
        parts.append(row("Remove Selected", "Clears the selected row(s) (Delete key). "
                          "Undoable with Ctrl+Z."))
        parts.append(row("Mass Edit Dates...", "Set or clear a date field across many rows at "
                          "once (Ctrl+Shift+D) \u2013 see below."))
        parts.append(row("Refresh", "Reloads from the workbook on disk (F5) \u2013 use this "
                          "after editing the sheet directly in Excel."))

        parts.append(sub("Editing the grid like a spreadsheet"))
        parts.append("<p>Tag, System, Type, and every date column can be edited right in the "
                      "table \u2013 click a cell and just start typing (or press F2/Enter first "
                      "if you'd rather not overwrite what's there), then Enter or Tab to move on. "
                      "Double-clicking a cell still opens the full Edit form instead, same as "
                      "always, so nothing about that changed.</p>")
        parts.append("<p>For editing many rows at once, the same shortcuts Excel uses:</p>")
        for keys, desc in [
            ("Ctrl+C", "copy the focused cell's value"),
            ("Ctrl+V", "paste \u2013 with one row selected, pastes into just that cell; with "
                       "several rows selected, broadcasts the SAME copied value into that same "
                       "column on every one of them (the main mass-edit move). Pasting a real "
                       "multi-cell block \u2013 copied from Excel itself, say \u2013 walks it "
                       "across the visible editable columns and rows starting from wherever "
                       "you click"),
            ("Ctrl+D", "fill the top selected row's value in that column down through the rest "
                       "of the selection"),
            ("Backspace", "clear that column's value on every selected row"),
        ]:
            parts.append(f"<p style='margin:2px 0;'><b>{keys}</b> \u2013 {desc}</p>")
        parts.append("<p style='margin-top:6px;'>Tag/Equip # is exempt from all four mass-edit "
                      "shortcuts (it has to stay unique per row, so it's only ever edited one "
                      "cell at a time, with a duplicate check) \u2013 editing it in place also "
                      "carries that row's Installed/Submitted/Accepted/Export status over to "
                      "the new value automatically, so nothing appears to reset.</p>")

        parts.append(sub("Status checkboxes (Installed / Submitted / Accepted / Export)"))
        parts.append("<p>Each row has its own checkboxes right in the table \u2013 click one to "
                      "flip it immediately, no need to select the row first. <b>Installed</b>, "
                      "<b>Submitted</b>, and <b>Accepted</b> track the equipment's real-world "
                      "progress; <b>Export</b> is a separate \u201cqueue this row\u201d flag used "
                      "by the Export dialog's default mode. The <b>Row #</b> cell colors itself "
                      "automatically: plain once nothing's checked, <b>yellow</b> once Submitted, "
                      "<b>green</b> once Accepted (Accepted wins if both are checked).</p>")
        parts.append(row("Bulk Status \u25be", "Mark or unmark Installed/Submitted/Accepted, or "
                          "add/remove the Export queue flag, on every currently-selected row at once."))
        parts.append(row("Queue All Shown for Export", "Checks the Export box on every row the "
                          "current search/filter is showing \u2013 a fast way to build a batch."))
        parts.append(row("Clear Export Queue (Shown)", "Unchecks Export on every row currently shown."))

        parts.append(sub("Mass Edit Dates"))
        parts.append("<p>The guided way to set or clear a date field across many rows \u2013 pick "
                      "the field (Test Equipment Calibration Date, QA Rep Date, ...), pick a "
                      "scope (selected rows, or everything currently shown), then either set a "
                      "date or tick \u201cClear this date instead\u201d to blank it out. Same "
                      "underlying action as copy/paste in the grid, just with a form around it. "
                      "New rows always start with every date blank - this is never done "
                      "automatically.</p>")

        parts.append(sub("Export dialog"))
        parts.append("<p>Three ways to pick which rows get turned into PDFs, in order of how "
                      "the dialog defaults: <b>(1) Only rows checked in the Export column</b> "
                      "\u2013 the app-side queue described above, and the default; "
                      "<b>(2) Only rows flagged \u201cExport to PDF = Y\u201d in Excel</b> \u2013 "
                      "the sheet's own long-standing flag column, for anyone who still prefers "
                      "setting it there; <b>(3) Every row with a Tag/Equip # filled in</b>. "
                      "\u201cUncheck those rows' Export boxes once exported\u201d (mode 1 only) "
                      "empties the queue as it's used.</p>")
        parts.append("<p><b>Dates:</b> \u201cInclude today's date in each filename\u201d appends "
                      "it to every output file. Sign-off dates themselves - QA Rep Date / Client "
                      "Rep Date for transmitters, QC Rep Date for valves - are real columns now "
                      "for both equipment types; set those directly in the grid (or with Mass "
                      "Edit Dates) before exporting and they'll appear on the PDF the normal way, "
                      "no separate export-time option needed.</p>")

        parts.append(sub("Populating Wizard"))
        parts.append("<p>For bulk-entering a batch of similar equipment fast:</p>")
        parts.append(row("1. Setup", "Pick the Series and equipment type, then Area Code + Tag "
                          "Type + System \u2013 these combine with a Sequence you type per item "
                          "to build the Tag/Equip # (29103 + FIT + 1011 = 29103-FIT-1011)."))
        parts.append(row("2. Repetition", "Tick any field that should carry the SAME value into "
                          "every entry this session (Make, Test Equipment, sign-off name, ...). "
                          "Leave a field unticked and it resets to blank after every save \u2013 "
                          "use that for anything that genuinely changes per item."))
        parts.append(row("3. Entering", "Type the Sequence, fill in whatever isn't repeating, "
                          "\u201cSave & Next\u201d writes the row and immediately opens a fresh "
                          "one with the repeating fields still filled in. Keeps going until you "
                          "click Stop."))
        parts.append(row("Edit Template", "Go back and change which fields repeat, mid-batch."))
        parts.append(row("Save as Draft & Close", "Stashes the whole batch \u2013 setup, "
                          "repeating values, and the entry you were mid-typing \u2013 as ONE "
                          "resumable draft. Reopening the Wizard offers to resume it. Saving "
                          "another draft later overwrites this one (it's a single slot, not a "
                          "library)."))

        parts.append(sub("Import Datasheet PDF"))
        parts.append("<p>Pre-fills a new row straight from an engineering data sheet PDF "
                      "instead of retyping it by hand \u2013 sidebar \u2192 \u201cImport "
                      "Datasheet PDF...\u201d, or Ctrl+Shift+I. Currently recognizes the "
                      "CNOOC/Oilsands-style \u201cDS-\u201d data sheets: Control Valve, "
                      "On/Off Valve, Temp Trans Element and TW, Vortex Flowmeter, Pressure "
                      "Transmitter, and Guided Wave Radar Level Transmitter \u2013 anything "
                      "else isn't recognized and needs to be entered by hand, same as "
                      "always.</p>")
        parts.append(row("Pick file(s)", "One PDF can hold several instruments (each spanning "
                          "its own two pages) \u2013 all of them get picked up and listed."))
        parts.append(row("Choose a series", "Defaults to whichever existing series' number "
                          "matches most of the detected tags' own area code, if one matches; "
                          "pick a different one, or add a new series first, if not."))
        parts.append(row("Review & Add Checked", "Opens each ticked record through the normal "
                          "Add New form, pre-filled \u2013 nothing is saved until that form's "
                          "own Save button is clicked, so every field gets a final look first. "
                          "Closing a form without saving just skips that one record."))
        parts.append("<p>Only fields the data sheet gives a direct, unambiguous answer for are "
                      "pre-filled \u2013 serial numbers, field test results, and sign-offs all "
                      "start blank, same as any new row, since none of that exists yet on a "
                      "pre-purchase data sheet. Signal Type, and Valve Type for valves, are "
                      "best-guesses rather than a direct read (the data sheet's own wording "
                      "doesn't map onto those pick-lists one-to-one) \u2013 worth a second look "
                      "before saving each one. A couple of very wide range values on the "
                      "Temperature Transmitter sheets specifically (Instrument Range, "
                      "Calibration Range) can come back blank rather than guessed at, if the "
                      "PDF's own text layer has scrambled them past reliably reading back.</p>")

        parts.append(sub("Keyboard Shortcuts"))
        shortcuts = [
            ("Ctrl+N", "Add New (on an Index page)"),
            ("Ctrl+E", "Edit the selected row"),
            ("Ctrl+F", "Jump to the Search box"),
            ("Delete", "Remove the selected row(s)"),
            ("Ctrl+C / Ctrl+V", "Copy / paste a cell (or mass-paste across selected rows)"),
            ("Ctrl+D", "Fill down the current column across selected rows"),
            ("Backspace", "Clear the current column across selected rows"),
            ("Ctrl+Shift+D", "Open Mass Edit Dates"),
            ("Ctrl+Shift+E", "Open the Export dialog"),
            ("F5", "Refresh from the workbook"),
            ("Ctrl+Z", "Undo the last change"),
            ("Ctrl+Shift+Z / Ctrl+Y", "Redo"),
            ("Ctrl+,", "Open Settings"),
            ("Ctrl+Shift+W", "Open the Populating Wizard"),
            ("Ctrl+Shift+I", "Open Import Datasheet PDF"),
        ]
        for keys, desc in shortcuts:
            parts.append(f"<p style='margin:2px 0;'><b>{keys}</b> \u2013 {desc}</p>")
        parts.append("<p style='margin-top:6px;'>Undo/Redo cover status checkbox changes, cell "
                      "edits (single or mass), Add New, Edit, and Remove Selected \u2013 each "
                      "one, going back up to 50 steps for this session. It doesn't cover typing "
                      "inside an open Edit form (Cancel there just discards unsaved changes "
                      "instead).</p>")

        parts.append("<hr style='margin-top:18px;'>")
        parts.append(h("WORKBOOK INSTRUCTIONS (from the Instructions sheet)"))
        return "".join(parts)

    @staticmethod
    def _build_workbook_instructions_html():
        lines = da.read_instructions()
        if not lines:
            return "<p>No Instructions sheet found in the workbook.</p>"
        html_parts = []
        for line in lines:
            if line.isupper() and len(line) > 3:
                html_parts.append(f"<p style='font-weight:700; margin-top:14px;'>{line}</p>")
            else:
                html_parts.append(f"<p>{line}</p>")
        return "".join(html_parts)

    def apply_theme(self):
        theme = da.get_setting("theme") or "light"
        app = QApplication.instance()
        title_build = self.findChild(QLabel, "SidebarTitle")
        logo_build = self.findChild(QLabel, "SidebarLogo")
        app.setStyleSheet(DARK_QSS if theme == "dark" else LIGHT_QSS)
        if title_build is not None:
            title_build.setStyleSheet("color: white;" if theme == "dark" else "color: black;")
        if logo_build is not None:
            self._set_logo_pixmap(logo_build)


# =============================================================================
# Dashboard page
# =============================================================================
class DashboardPage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        title = QLabel("K1B Equipment Inspection Tracker")
        title.setObjectName("PageTitle")
        layout.addWidget(title)
        subtitle = QLabel("Instrumentation QA/QC Tracker")
        subtitle.setObjectName("PageSubtitle")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(16)
        totals = da.count_all_by_type()
        for equip_key, etype in da.EQUIPMENT_TYPES.items():
            breakdown = da.count_by_system_all_series(equip_key)
            card = StatCard(f"{etype['label']}s logged", totals.get(equip_key, 0), breakdown)
            cards_row.addWidget(card)
        cards_row.addStretch()
        inner_layout.addLayout(cards_row)

        inner_layout.addWidget(self._build_tips_card())

        series_label = QLabel("SERIES")
        series_label.setObjectName("SectionLabel")
        inner_layout.addWidget(series_label, alignment=Qt.AlignLeft)

        series_row = QHBoxLayout()
        series_row.setSpacing(10)
        for series_number in da.list_series():
            btn = make_button(da.series_display_label(series_number), "Primary", width=140)
            btn.clicked.connect(lambda checked=False, n=series_number: self._open_first_type(n))
            series_row.addWidget(btn)
        series_row.addStretch()
        inner_layout.addLayout(series_row)

        by_series_label = QLabel("BY SERIES \u2013 INSTALLED / SUBMITTED / ACCEPTED")
        by_series_label.setObjectName("SectionLabel")
        inner_layout.addWidget(by_series_label, alignment=Qt.AlignLeft)

        by_series_row = QHBoxLayout()
        by_series_row.setSpacing(16)
        series_numbers = da.list_series()
        if not series_numbers:
            none_label = QLabel("No series yet - add one from the sidebar.")
            none_label.setObjectName("StatLabel")
            by_series_row.addWidget(none_label)
        for series_number in series_numbers:
            summary = da.series_full_summary(series_number)
            progress_summary = da.series_progress_summary(series_number)
            by_series_row.addWidget(SeriesStatCard(series_number, summary, progress_summary))
        by_series_row.addStretch()
        inner_layout.addLayout(by_series_row)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

    def _build_tips_card(self):
        card = QFrame()
        card.setObjectName("Card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 16, 20, 16)
        card_layout.setSpacing(8)

        label = QLabel("QUICK TIPS")
        label.setObjectName("SectionLabel")
        card_layout.addWidget(label)

        tip = QLabel(
            "The fastest way to log new equipment is typing straight into "
            "Excel - great for bulk entry, autofill, and copy/paste. This "
            "app's Add New / Edit forms are best for one-off edits, quick "
            "lookups, PDF exports, and status tracking.")
        tip.setObjectName("StatLabel")
        tip.setWordWrap(True)
        card_layout.addWidget(tip)

        row = QHBoxLayout()
        self.excel_sheets_btn = make_button("\U0001F4C4 Excel Sheets", "Primary")
        self.excel_sheets_btn.clicked.connect(self._show_excel_sheet_menu)
        row.addWidget(self.excel_sheets_btn)
        row.addStretch()
        card_layout.addLayout(row)

        return card

    def _show_excel_sheet_menu(self):
        """Excel Sheets button -> a Transmitter Log / Valve Log submenu per
        equipment type, each listing every registered series (by its
        display name) - pick one to jump Excel straight to that tab."""
        menu = QMenu(self)
        series_numbers = da.list_series()
        for equip_key, etype in da.EQUIPMENT_TYPES.items():
            submenu = menu.addMenu(f"{etype['label']} Log")
            added_any = False
            for series_number in series_numbers:
                try:
                    da.get_sheet_name(series_number, equip_key)
                except KeyError:
                    continue
                added_any = True
                action = submenu.addAction(da.series_display_label(series_number))
                action.triggered.connect(
                    lambda checked=False, sn=series_number, ek=equip_key: self._open_sheet(sn, ek))
            if not added_any:
                none_action = submenu.addAction("(none yet)")
                none_action.setEnabled(False)
        menu.exec(self.excel_sheets_btn.mapToGlobal(self.excel_sheets_btn.rect().bottomLeft()))

    def _open_sheet(self, series_number, equip_key):
        try:
            da.open_sheet(series_number, equip_key)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't open sheet", str(exc))

    def _open_first_type(self, series_number):
        first_key = next(iter(da.EQUIPMENT_TYPES))
        self.main_window.show_index(series_number, first_key, None)


# =============================================================================
# Coverage page - Sensei Index 2.1, Phase 11.
#
# Answers, per area and per equipment kind, which master-list instruments
# have a tracker row and which don't - and the reverse (orphans). Entirely
# read-only except "Add to tracker" (create-from-master), which is the
# same commit path as any other new row (no separate pending-edit layer
# exists in this app to route through instead).
# =============================================================================
COVERAGE_FLAG_LABELS = {
    "installed_mismatch": "Installed mismatch",
    "model_mismatch": "Model mismatch",
}


class CoveragePage(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.result = None
        self._selected_missing = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        header = QLabel("Coverage")
        header.setObjectName("PageTitle")
        outer.addWidget(header)
        subtitle = QLabel("What's tracked against the client's Instrumentation Master List, "
                           "and what isn't - matched, missing, orphaned, or flagged.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(subtitle)

        self.banner = QLabel()
        self.banner.setObjectName("Breadcrumb")
        self.banner.setWordWrap(True)
        self.banner.hide()
        outer.addWidget(self.banner)

        self.empty_state = self._build_empty_state()
        outer.addWidget(self.empty_state, stretch=1)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 8, 0, 0)

        chip_row = QHBoxLayout()
        self.chips = FilterChipBar(
            [("all", "All"), ("missing", "Missing"), ("orphans", "Orphans"), ("flags", "Flags")],
            on_change=lambda _id: self._render_tree())
        chip_row.addWidget(self.chips)
        chip_row.addStretch()
        self.add_selected_btn = make_button("Add Selected to Tracker", "Primary")
        self.add_selected_btn.setEnabled(False)
        self.add_selected_btn.clicked.connect(lambda: self._create_from_master(list(self._selected_missing)))
        chip_row.addWidget(self.add_selected_btn)
        content_layout.addLayout(chip_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        content_layout.addWidget(self.tree, stretch=1)

        outer.addWidget(self.content, stretch=1)

        self.reload()

    # ----------------------------------------------------------- empty state
    def _build_empty_state(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addStretch()
        label = QLabel(
            "No master list imported yet.\n\n"
            "Import the client's Instrumentation Master List to see coverage - "
            "what's tracked, what's missing, and what doesn't match.")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        layout.addWidget(label)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn = make_button("Import Master List...", "Primary")
        btn.clicked.connect(lambda: self.main_window.open_master_list_import())
        btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        layout.addStretch()
        return page

    # ---------------------------------------------------------------- reload
    def reload(self):
        self.result = da.reconcile_master_list()
        if self.result is None:
            self.content.hide()
            self.banner.hide()
            self.empty_state.show()
            return

        self.empty_state.hide()
        self.content.show()
        if da.master_list_needs_reimport():
            self.banner.setText(
                "⚠ The master list file on disk has changed since it was last imported. "
                "Use “Master List...” in the sidebar to re-import.")
            self.banner.show()
        else:
            self.banner.hide()
        self._render_tree()

    # ------------------------------------------------------------ rendering
    def _grouped_by_area(self):
        groups = {}

        def bucket(area, kind):
            return groups.setdefault(area or "(no area)", {}).setdefault(
                kind, {"matched": [], "missing": [], "orphans": []})

        for pair in self.result["matched"]:
            item = pair["master"]
            bucket(item["area"], item["kind"])["matched"].append(pair)
        for item in self.result["missing"]:
            bucket(item["area"], item["kind"])["missing"].append(item)
        for ref in self.result["orphans"]:
            area = da.parse_area_code(da.canonical_tag(ref["key_value"]))
            bucket(area, ref["equip_key"])["orphans"].append(ref)
        return groups

    def _leaves_for_bucket(self, bucket, active_chip):
        leaves = []
        if active_chip in ("all", "flags"):
            pairs = bucket["matched"] if active_chip == "all" else \
                [p for p in bucket["matched"] if p["flags"]]
            for pair in pairs:
                item = pair["master"]
                pct = pair["progress"]["percent"]
                flag_text = ""
                if pair["flags"]:
                    wording = ", ".join(COVERAGE_FLAG_LABELS.get(f, f) for f in pair["flags"])
                    flag_text = f"  ⚠ {wording}"
                leaves.append((f"✓ {item['tag']} — {item['service']} — {pct}%{flag_text}",
                                ("matched", pair)))
        if active_chip in ("all", "missing"):
            for item in bucket["missing"]:
                leaves.append((f"○ {item['tag']} — {item['service']} — 0% (not started)",
                                ("missing", item)))
        if active_chip in ("all", "orphans"):
            for ref in bucket["orphans"]:
                leaves.append((f"? {ref['key_value']} (not in master list)",
                                ("orphan", ref)))
        return leaves

    def _render_tree(self):
        self.tree.clear()
        active = self.chips.active_id
        groups = self._grouped_by_area()

        for area in sorted(groups.keys()):
            area_item = QTreeWidgetItem([area])
            self.tree.addTopLevelItem(area_item)
            any_children = False
            for equip_key, etype in da.EQUIPMENT_TYPES.items():
                bucket = groups[area].get(equip_key)
                if not bucket:
                    continue
                matched_n = len(bucket["matched"])
                missing_n = len(bucket["missing"])
                orphans_n = len(bucket["orphans"])
                flags_n = sum(1 for p in bucket["matched"] if p["flags"])
                label = (f"{etype['label']}s: {matched_n} matched · {missing_n} missing · "
                         f"{orphans_n} orphans · {flags_n} flags")
                kind_item = QTreeWidgetItem([label])
                area_item.addChild(kind_item)
                any_children = True

                for text, data in self._leaves_for_bucket(bucket, active):
                    leaf = QTreeWidgetItem([text])
                    leaf.setData(0, Qt.UserRole, data)
                    kind_item.addChild(leaf)
                kind_item.setExpanded(active != "all")
            area_item.setExpanded(any_children)

        if self.result["out_of_scope_count"]:
            oos_item = QTreeWidgetItem([f"Out of scope ({self.result['out_of_scope_count']})"])
            self.tree.addTopLevelItem(oos_item)
            for item in self.result["out_of_scope_items"]:
                text = f"{item['tag']} — {item['type_desc'] or item['service'] or '(no description)'}"
                leaf = QTreeWidgetItem([text])
                leaf.setData(0, Qt.UserRole, ("out_of_scope", item))
                oos_item.addChild(leaf)
            oos_item.setExpanded(False)

        self._on_selection_changed()

    # ------------------------------------------------------------- clicking
    def _on_item_clicked(self, item, _column):
        data = item.data(0, Qt.UserRole)
        if not data:
            item.setExpanded(not item.isExpanded())
            return
        kind, payload = data
        if kind == "matched":
            ref = payload["tracker"]
            key_field = da.EQUIPMENT_TYPES[ref["equip_key"]]["key_field"]
            self.main_window.show_index(ref["series"], ref["equip_key"],
                                         {key_field: ref["key_value"]})
        elif kind == "missing":
            self._create_from_master([payload])
        elif kind == "orphan":
            key_field = da.EQUIPMENT_TYPES[payload["equip_key"]]["key_field"]
            self.main_window.show_index(payload["series"], payload["equip_key"],
                                         {key_field: payload["key_value"]})
        # out_of_scope: informational only, nothing to jump to or create.

    def _on_selection_changed(self):
        self._selected_missing = [
            item.data(0, Qt.UserRole)[1] for item in self.tree.selectedItems()
            if item.data(0, Qt.UserRole) and item.data(0, Qt.UserRole)[0] == "missing"
        ]
        n = len(self._selected_missing)
        self.add_selected_btn.setEnabled(n > 0)
        self.add_selected_btn.setText(f"Add {n} Selected to Tracker" if n else "Add Selected to Tracker")

    # --------------------------------------------------- create-from-master
    def _create_from_master(self, items):
        if not items:
            return
        registered = set(da.list_series())
        unmapped = [it for it in items if it.get("mapped_series") not in registered]
        if unmapped:
            tags = ", ".join(it["tag"] for it in unmapped)
            QMessageBox.warning(
                self, "Can't add yet",
                f"These items' sheets aren't mapped to a series yet, so there's nowhere to "
                f"create them: {tags}\n\nRe-import the master list and map that sheet to a "
                f"series (Master List... in the sidebar), or add these by hand.")
            return

        lines = [f"About to create {len(items)} new row(s):"]
        for it in items:
            lines.append(f"  • {it['tag']} → {da.series_display_label(it['mapped_series'])} "
                          f"({da.EQUIPMENT_TYPES[it['kind']]['label']})")
        confirm = QMessageBox.question(
            self, "Add to tracker", "\n".join(lines),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
        if confirm != QMessageBox.Yes:
            return

        try:
            created = da.create_rows_from_master_items([(it["kind"], it) for it in items])
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't create rows", str(exc))
            return

        self._record_create_undo(created)
        self.main_window.refresh_sidebar_and_dashboard()
        self.reload()
        self.main_window.statusBar().showMessage(f"Added {len(created)} row(s) from the master list", 4000)

    def _record_create_undo(self, created):
        mw = self.main_window

        def do_undo():
            by_sheet = {}
            for c in created:
                by_sheet.setdefault((c["series"], c["equip_key"]), []).append(c["row"])
            for (series_number, equip_key), rows in by_sheet.items():
                da.delete_rows(series_number, equip_key, rows)
            mw.refresh_current_view()

        def do_redo():
            for c in created:
                da.save_row(c["series"], c["equip_key"], c["row"], c["values"])
            mw.refresh_current_view()

        mw.undo_stack.push(f"add {len(created)} row(s) from master list", do_undo, do_redo)


# =============================================================================
# Index page - searchable / sortable table for one series + equipment type
# =============================================================================
class NumericItem(QTableWidgetItem):
    """A table cell that sorts by an underlying number/bool instead of the
    displayed string, so 'Row' sorts 2, 10, 100 (not '10', '100', '2')."""

    def __init__(self, display_text, sort_value):
        super().__init__(display_text)
        self.sort_value = sort_value

    def __lt__(self, other):
        if isinstance(other, NumericItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class ExcelLikeTableWidget(QTableWidget):
    """The Index table, with a few Excel muscle-memory keybinds layered on
    top of normal cell editing:
        Ctrl+C      copy the focused cell's text
        Ctrl+V      paste - broadcasts a single copied value across every
                    selected row in that same column (the core "mass edit"
                    move), or walks a real multi-cell block across the
                    visible editable columns/rows if the clipboard holds one
        Ctrl+D      fill the top selected row's value in the focus column
                    down through the rest of the selection
        Backspace   clear the focus column across every selected row
    All four are IndexPage methods under the hood - this class only ever
    intercepts the keypress and hands it off, and only when the table
    itself has focus and isn't already mid-edit (so typing inside an open
    cell editor is never hijacked)."""

    def __init__(self, *args, index_page=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.index_page = index_page

    def keyPressEvent(self, event):
        page = self.index_page
        if page is not None and self.state() != QAbstractItemView.EditingState:
            if event.matches(QKeySequence.Copy):
                page.copy_current_cell()
                return
            if event.matches(QKeySequence.Paste):
                page.paste_to_selection()
                return
            if event.key() == Qt.Key_D and event.modifiers() == Qt.ControlModifier:
                page.fill_down_selection()
                return
            if event.key() == Qt.Key_Backspace:
                page.clear_selection_in_column()
                return
        super().keyPressEvent(event)


class IndexPage(QWidget):
    STATUS_FIELDS = ["installed", "submitted", "accepted", "export"]
    STATUS_LABELS = {"installed": "Installed", "submitted": "Submitted",
                      "accepted": "Accepted", "export": "Export"}
    STATUS_OBJECT_NAMES = {"submitted": "SubmittedCheck", "accepted": "AcceptedCheck",
                            "export": "ExportCheck"}

    def __init__(self, main_window, series_number, equip_key, filters=None):
        super().__init__()
        self.main_window = main_window
        self.series_number = series_number
        self.equip_key = equip_key
        self.filters = dict(filters or {})
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.all_rows = []
        self._entry_by_row = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel(f"{da.series_display_label(series_number)} \u2013 {self.etype['label']} Index")
        title.setObjectName("PageTitle")
        layout.addWidget(title)

        if self.filters:
            crumb_text = " \u203a ".join(f"{k}: {v}" for k, v in self.filters.items())
            crumb = QLabel(crumb_text)
            crumb.setObjectName("Breadcrumb")
            layout.addWidget(crumb)

        toolbar = QHBoxLayout()
        add_btn = make_button("+ Add New", "Primary")
        add_btn.setToolTip("Add a brand-new row (Ctrl+N)")
        add_btn.clicked.connect(self.add_new)
        more_btn = make_button("Show More", "Ghost")
        more_btn.setToolTip("See every field on the selected row, not just the "
                             "columns shown here")
        more_btn.clicked.connect(self.show_more)
        view_btn = make_button("View Details", "Ghost")
        view_btn.setToolTip("Build a filled PDF preview of the selected row")
        view_btn.clicked.connect(self.view_details)
        edit_btn = make_button("Edit", "Ghost")
        edit_btn.setToolTip("Edit the selected row (Ctrl+E)")
        edit_btn.clicked.connect(self.edit_selected)
        export_btn = make_button("Export...", "Ghost")
        export_btn.setToolTip("Turn rows into PDFs (Ctrl+Shift+E)")
        export_btn.clicked.connect(self.open_export)
        select_all_btn = make_button("Select All", "Ghost")
        select_all_btn.setToolTip("Select every row currently shown (not just "
                                   "the ones on screen without scrolling)")
        select_all_btn.clicked.connect(self.select_all_in_view)
        remove_btn = make_button("Remove Selected", "Danger")
        remove_btn.setToolTip("Clear the selected row(s) (Delete). Undoable with Ctrl+Z.")
        remove_btn.clicked.connect(self.remove_selected)
        dates_btn = make_button("Mass Edit Dates...", "Ghost")
        dates_btn.setToolTip("Set or clear a date field across many rows at once (Ctrl+Shift+D)")
        dates_btn.clicked.connect(self.open_mass_edit_dates)
        refresh_btn = make_button("Refresh", "Link")
        refresh_btn.setToolTip("Reload from the workbook (F5)")
        refresh_btn.clicked.connect(self.reload)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(more_btn)
        toolbar.addWidget(view_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(export_btn)
        toolbar.addWidget(select_all_btn)
        toolbar.addWidget(remove_btn)
        if self.etype.get("date_fields"):
            toolbar.addWidget(dates_btn)
        toolbar.addStretch()
        toolbar.addWidget(refresh_btn)
        layout.addLayout(toolbar)

        # ---- Status row: bulk actions + the Export queue helpers. Individual
        # rows are now marked directly with the checkboxes in the table
        # itself (see _build_status_widget) - DITCHED the old "select a row,
        # then click a separate Toggle button" flow entirely. What's left
        # here is only for working on MANY rows at once, which a checkbox
        # can't do by itself. ----
        status_row = QHBoxLayout()
        status_label = QLabel("Bulk actions:")
        status_label.setObjectName("FieldLabel")
        bulk_btn = make_button("Bulk Status \u25be", "Ghost")
        bulk_btn.setToolTip("Mark/unmark Installed, Submitted, or Accepted on "
                             "every currently-selected row at once")
        bulk_btn.setMenu(self._build_bulk_status_menu())
        queue_btn = make_button("Queue All Shown for Export", "Primary")
        queue_btn.setToolTip("Check the Export box on every row the current "
                              "search/filter is showing")
        queue_btn.clicked.connect(self.queue_all_shown_for_export)
        clear_queue_btn = make_button("Clear Export Queue (Shown)", "Ghost")
        clear_queue_btn.setToolTip("Uncheck the Export box on every row currently shown")
        clear_queue_btn.clicked.connect(self.clear_export_queue_shown)
        status_row.addWidget(status_label)
        status_row.addWidget(bulk_btn)
        status_row.addWidget(queue_btn)
        status_row.addWidget(clear_queue_btn)
        status_row.addStretch()
        layout.addLayout(status_row)

        search_row = QHBoxLayout()
        search_label = QLabel("Search")
        self.search_edit = QLineEdit()
        self.search_edit.setToolTip("Filters as you type (Ctrl+F to jump here)")
        self.search_edit.textChanged.connect(self.apply_filter)
        self.count_label = QLabel("")
        self.count_label.setObjectName("FieldLabel")
        search_row.addWidget(search_label)
        search_row.addWidget(self.search_edit, stretch=1)
        search_row.addWidget(self.count_label)
        layout.addLayout(search_row)

        self.columns = (["row"] + self.etype["summary_fields"] + list(self.etype.get("date_fields", []))
                         + list(self.STATUS_FIELDS))
        self.headers = (["Row"] + self.etype["summary_labels"] + list(self.etype.get("date_labels", []))
                         + [self.STATUS_LABELS[f] for f in self.STATUS_FIELDS])
        n_summary = len(self.etype["summary_fields"])
        n_dates = len(self.etype.get("date_fields", []))
        self._n_summary = n_summary
        self._n_dates = n_dates
        # Every plain-text column (Tag/System/Type + the date columns) is
        # directly editable right in the grid, Excel-style - {column_index:
        # field_id}. Row # and the status checkboxes are never in here.
        self._editable_columns = {i: fid for i, fid in enumerate(self.columns) if 1 <= i <= n_summary + n_dates}

        self.table = ExcelLikeTableWidget(0, len(self.columns), index_page=self)
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.EditKeyPressed | QAbstractItemView.AnyKeyPressed)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setMinimumSectionSize(90)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 1 + n_summary):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Stretch)
        for i in range(1 + n_summary, len(self.columns)):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Fixed)
            self.table.setColumnWidth(i, 118 if i < 1 + n_summary + n_dates else 92)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._on_row_double_clicked)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_table_context_menu)
        layout.addWidget(self.table, stretch=1)

        tip = QLabel("Tip: click a column header to sort, type to search, "
                     "Ctrl/Shift-click rows to select more than one. Tag, System, Type, "
                     "and date cells are editable right here - click one and type, or "
                     "Ctrl+C / Ctrl+V to copy a value onto every selected row, Ctrl+D to "
                     "fill down, Backspace to clear. Row # turns yellow once Submitted, "
                     "green once Accepted. Ctrl+Z undoes the last change.")
        tip.setObjectName("FieldLabel")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self.reload()
        self.table.sortByColumn(0, Qt.AscendingOrder)
        self.search_edit.setFocus()

    # ----------------------------------------------------------------- data
    def reload(self, reselect_row=None):
        try:
            self.all_rows = da.read_index_rows_filtered(self.series_number, self.equip_key, self.filters)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't read workbook", str(exc))
            self.all_rows = []
        self._entry_by_row = {e["row"]: e for e in self.all_rows}
        self.apply_filter()
        if reselect_row is not None:
            # Accepts either one row number (Edit/Add New) or a collection
            # of them (a bulk action on several selected rows at once) -
            # selectionModel().select() ADDS to the selection, so this
            # correctly re-highlights every match, not just the last one
            # found (table.selectRow() in a loop would only leave the final
            # match selected, since it replaces rather than adds).
            targets = {reselect_row} if isinstance(reselect_row, int) else set(reselect_row)
            sm = self.table.selectionModel()
            first_item = None
            for r in range(self.table.rowCount()):
                item = self.table.item(r, 0)
                if item and item.sort_value in targets:
                    sm.select(self.table.model().index(r, 0),
                              QItemSelectionModel.Select | QItemSelectionModel.Rows)
                    if first_item is None:
                        first_item = item
            if first_item is not None:
                self.table.scrollToItem(first_item)

    def apply_filter(self):
        query = self.search_edit.text().strip().lower()
        rows = self.all_rows
        if query:
            rows = [r for r in rows if query in
                    " ".join(str(r.get(f) or "") for f in self.etype["summary_fields"]).lower()]

        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        n_summary = self._n_summary
        n_dates = self._n_dates
        date_fields = self.etype.get("date_fields", [])
        for entry in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            row_num = entry["row"]
            key_value = entry.get(self.etype["key_field"], "")

            row_item = NumericItem(str(row_num), row_num)
            row_item.setFlags(row_item.flags() & ~Qt.ItemIsEditable)
            color = row_status_color(entry)
            if color is not None:
                row_item.setBackground(color)
            self.table.setItem(r, 0, row_item)

            for c, fid in enumerate(self.etype["summary_fields"], start=1):
                val = str(entry.get(fid) or "")
                self.table.setItem(r, c, QTableWidgetItem(val))

            for c, fid in enumerate(date_fields, start=1 + n_summary):
                val = str(entry.get(fid) or "")
                item = QTableWidgetItem(val)
                item.setToolTip("YYYY-MM-DD works best, but anything you type is kept as-is.")
                self.table.setItem(r, c, item)

            for i, field in enumerate(self.STATUS_FIELDS):
                col = 1 + n_summary + n_dates + i
                self.table.setItem(r, col, QTableWidgetItem(""))  # keeps row height/selection consistent
                widget = self._build_status_widget(row_num, key_value, field, bool(entry.get(field)))
                self.table.setCellWidget(r, col, widget)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

        total, shown = len(self.all_rows), len(rows)
        self.count_label.setText(f"{shown} of {total}" if shown != total
                                  else f"{total} record{'s' if total != 1 else ''}")

    def _build_status_widget(self, row_num, key_value, field, checked):
        box = QCheckBox()
        object_name = self.STATUS_OBJECT_NAMES.get(field)
        if object_name:
            box.setObjectName(object_name)
        box.setToolTip(f"{self.STATUS_LABELS[field]} \u2013 click to toggle for this row only")
        box.setChecked(checked)
        box.toggled.connect(
            lambda is_checked, rn=row_num, kv=key_value, f=field, b=box:
                self._on_status_checkbox_toggled(rn, kv, f, b, is_checked))
        wrapper = QWidget()
        wlayout = QHBoxLayout(wrapper)
        wlayout.setContentsMargins(0, 0, 0, 0)
        wlayout.setAlignment(Qt.AlignCenter)
        wlayout.addWidget(box)
        return wrapper

    def _on_status_checkbox_toggled(self, row_num, key_value, field, checkbox, checked):
        entry = self._entry_by_row.get(row_num)
        previous = bool(entry.get(field)) if entry else (not checked)
        if previous == checked:
            return
        try:
            da.set_status(self.series_number, self.equip_key, key_value, **{field: checked})
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save status", str(exc))
            checkbox.blockSignals(True)
            checkbox.setChecked(previous)
            checkbox.blockSignals(False)
            return
        if entry is not None:
            entry[field] = checked
        self._record_status_undo(key_value, field, previous, checked)
        self._refresh_row_color(row_num)
        self.main_window.statusBar().showMessage(
            f"{self.STATUS_LABELS[field]} {'checked' if checked else 'unchecked'} "
            f"\u2013 {key_value}", 2500)
        self.main_window.refresh_sidebar_and_dashboard()

    def _record_status_undo(self, key_value, field, previous, new_value):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key

        def do_undo():
            da.set_status(sn, ek, key_value, **{field: previous})
            mw.refresh_current_view()

        def do_redo():
            da.set_status(sn, ek, key_value, **{field: new_value})
            mw.refresh_current_view()

        mw.undo_stack.push(f"{self.STATUS_LABELS[field]} \u2013 {key_value}", do_undo, do_redo)

    def _table_row_for(self, row_num):
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item is not None and item.sort_value == row_num:
                return r
        return None

    def _refresh_row_color(self, row_num):
        r = self._table_row_for(row_num)
        if r is None:
            return
        item = self.table.item(r, 0)
        if item is None:
            return
        entry = self._entry_by_row.get(row_num)
        color = row_status_color(entry) if entry else None
        if color is not None:
            item.setBackground(color)
        else:
            item.setData(Qt.BackgroundRole, None)

    def _header_for(self, field):
        try:
            return self.headers[self.columns.index(field)]
        except ValueError:
            return field

    # ------------------------------------------------------- Excel-like grid
    # Direct in-cell editing (Tag/System/Type + every date column), plus
    # Ctrl+C / Ctrl+V / Ctrl+D / Backspace mass-edit muscle memory. A single
    # typed edit goes through _on_item_changed -> _commit_single_cell_edit
    # (one cell, one row, with proper Tag/Equip # uniqueness + status-key
    # migration). Paste/fill-down/clear/Mass Edit Dates all funnel through
    # _apply_cell_updates instead, which writes every affected cell in ONE
    # workbook save and ONE undo step, however many rows it spans.
    def _on_item_changed(self, item):
        col = item.column()
        if col not in self._editable_columns:
            return
        row_item = self.table.item(item.row(), 0)
        if row_item is None:
            return
        row_num = row_item.sort_value
        field = self._editable_columns[col]
        self._commit_single_cell_edit(row_num, field, item.text())

    def _commit_single_cell_edit(self, row_num, field, new_value):
        entry = self._entry_by_row.get(row_num)
        if entry is None:
            return
        old_value = str(entry.get(field) or "")
        new_value = str(new_value)
        if old_value == new_value:
            return

        key_field = self.etype["key_field"]
        if field == key_field:
            cleaned = new_value.strip()
            if not cleaned:
                QMessageBox.warning(
                    self, "Can't be blank",
                    f"{self._header_for(field)} can't be blank. Use Remove Selected "
                    "to clear this row entirely instead.")
                self._revert_cell_text(row_num, field, old_value)
                return
            dup_row = da.find_duplicate_row(self.series_number, self.equip_key, cleaned, exclude_row=row_num)
            if dup_row is not None:
                QMessageBox.warning(self, "Duplicate",
                                     f'"{cleaned}" is already used on row {dup_row}.')
                self._revert_cell_text(row_num, field, old_value)
                return
            new_value = cleaned

        try:
            da.save_row(self.series_number, self.equip_key, row_num, {field: new_value})
            if field == key_field:
                da.rename_status_key(self.series_number, self.equip_key, old_value, new_value)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save", str(exc))
            self._revert_cell_text(row_num, field, old_value)
            return

        entry[field] = new_value
        self._record_single_cell_edit_undo(row_num, field, old_value, new_value)
        self.main_window.statusBar().showMessage(
            f"Saved {self._header_for(field)} on row {row_num}", 2500)
        self.main_window.refresh_sidebar_and_dashboard()

        if field == key_field:
            # Every status checkbox's click handler on this row closed over
            # the OLD key value - rebuilding the row is far simpler (and
            # safer) than trying to rewire five live closures in place.
            self.reload(reselect_row=row_num)

    def _revert_cell_text(self, row_num, field, old_value):
        r = self._table_row_for(row_num)
        if r is None:
            return
        col = self.columns.index(field)
        item = self.table.item(r, col)
        if item is None:
            return
        self.table.blockSignals(True)
        item.setText(old_value)
        self.table.blockSignals(False)

    def _record_single_cell_edit_undo(self, row_num, field, old_value, new_value):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key
        key_field = self.etype["key_field"]

        def do_undo():
            da.save_row(sn, ek, row_num, {field: old_value})
            if field == key_field:
                da.rename_status_key(sn, ek, new_value, old_value)
            mw.refresh_current_view()

        def do_redo():
            da.save_row(sn, ek, row_num, {field: new_value})
            if field == key_field:
                da.rename_status_key(sn, ek, old_value, new_value)
            mw.refresh_current_view()

        mw.undo_stack.push(f"edit {self._header_for(field)} \u2013 row {row_num}", do_undo, do_redo)

    def _apply_cell_updates(self, updates):
        """updates: an iterable of (row_num, field, value) triples. Used by
        paste, fill-down, clear, and Mass Edit Dates - anything that can
        touch more than one cell at once. Writes everything in a single
        workbook save and records ONE undo step covering the whole batch."""
        before = []
        bulk_payload = []
        seen = set()
        for row_num, field, value in updates:
            if (row_num, field) in seen:
                continue  # last one wins if a batch mentions the same cell twice
            seen.add((row_num, field))
            entry = self._entry_by_row.get(row_num)
            old_value = str(entry.get(field) or "") if entry else ""
            value = str(value)
            if old_value == value:
                continue
            before.append((row_num, field, old_value, value))
            bulk_payload.append((row_num, field, value))
        if not bulk_payload:
            return

        try:
            da.save_fields_bulk(self.series_number, self.equip_key, bulk_payload)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save", str(exc))
            return

        self.table.blockSignals(True)
        for row_num, field, old_value, new_value in before:
            entry = self._entry_by_row.get(row_num)
            if entry is not None:
                entry[field] = new_value
            col = self.columns.index(field)
            rr = self._table_row_for(row_num)
            if rr is not None:
                item = self.table.item(rr, col)
                if item is not None:
                    item.setText(new_value)
        self.table.blockSignals(False)

        self._record_bulk_cell_edit_undo(before)
        n = len(bulk_payload)
        self.main_window.statusBar().showMessage(f"Updated {n} cell{'s' if n != 1 else ''}", 2500)
        self.main_window.refresh_sidebar_and_dashboard()

    def _record_bulk_cell_edit_undo(self, before):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key

        def do_undo():
            da.save_fields_bulk(sn, ek, [(row_num, field, old) for row_num, field, old, new in before])
            mw.refresh_current_view()

        def do_redo():
            da.save_fields_bulk(sn, ek, [(row_num, field, new) for row_num, field, old, new in before])
            mw.refresh_current_view()

        n = len(before)
        mw.undo_stack.push(f"edit {n} cell{'s' if n != 1 else ''}", do_undo, do_redo)

    def copy_current_cell(self):
        item = self.table.currentItem()
        col = self.table.currentColumn()
        if item is None or col not in self._editable_columns:
            return
        QApplication.clipboard().setText(item.text())
        self.main_window.statusBar().showMessage("Copied", 1500)

    def paste_to_selection(self):
        text = QApplication.clipboard().text()
        if not text:
            return
        col = self.table.currentColumn()
        if col not in self._editable_columns:
            QMessageBox.information(self, "Can't paste here",
                                     "That column isn't editable. Click a Tag, System, "
                                     "Type, or date cell first.")
            return
        field = self._editable_columns[col]
        key_field = self.etype["key_field"]
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        while lines and lines[-1] == "":
            lines.pop()
        if not lines:
            return

        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedIndexes()})
        if not selected_rows:
            selected_rows = [self.table.currentRow()]

        if len(lines) == 1 and "\t" not in lines[0]:
            # One value being pasted onto however many rows are selected -
            # broadcast it across all of them in the CURRENT column. This is
            # the main "mass edit" move: copy one date/value, select a batch
            # of rows, paste.
            value = lines[0]
            if field == key_field and len(selected_rows) > 1:
                QMessageBox.warning(self, "Can't do that",
                                     f"{self._header_for(field)} has to be unique per row - "
                                     "pasting the same value onto more than one row isn't allowed.")
                return
            updates = [(self.table.item(r, 0).sort_value, field, value) for r in selected_rows]
            self._apply_cell_updates(updates)
        else:
            # A real multi-cell block (e.g. copied from actual Excel) - walk
            # it across the visible editable columns starting at the current
            # column, and down through the table starting at the current row.
            editable_cols_sorted = sorted(self._editable_columns)
            start_pos = editable_cols_sorted.index(col)
            start_r = self.table.currentRow()
            updates = []
            for i, line in enumerate(lines):
                r = start_r + i
                if r >= self.table.rowCount():
                    break
                row_num = self.table.item(r, 0).sort_value
                for j, val in enumerate(line.split("\t")):
                    pos = start_pos + j
                    if pos >= len(editable_cols_sorted):
                        break
                    target_field = self._editable_columns[editable_cols_sorted[pos]]
                    if target_field == key_field and val.strip() == "":
                        continue  # never blank the key field via a block paste
                    updates.append((row_num, target_field, val))
            self._apply_cell_updates(updates)

    def fill_down_selection(self):
        col = self.table.currentColumn()
        if col not in self._editable_columns:
            return
        field = self._editable_columns[col]
        if field == self.etype["key_field"]:
            QMessageBox.warning(self, "Can't do that",
                                 f"{self._header_for(field)} has to be unique per row - "
                                 "fill down isn't allowed here.")
            return
        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedIndexes()})
        if len(selected_rows) < 2:
            return
        top_row_num = self.table.item(selected_rows[0], 0).sort_value
        value = str(self._entry_by_row.get(top_row_num, {}).get(field, ""))
        updates = [(self.table.item(r, 0).sort_value, field, value) for r in selected_rows[1:]]
        self._apply_cell_updates(updates)

    def clear_selection_in_column(self):
        col = self.table.currentColumn()
        if col not in self._editable_columns:
            return
        field = self._editable_columns[col]
        if field == self.etype["key_field"]:
            QMessageBox.warning(self, "Can't do that",
                                 f"{self._header_for(field)} can't be blanked this way - "
                                 "use Remove Selected to clear a whole row instead.")
            return
        selected_rows = sorted({idx.row() for idx in self.table.selectionModel().selectedIndexes()})
        updates = [(self.table.item(r, 0).sort_value, field, "") for r in selected_rows]
        self._apply_cell_updates(updates)

    def apply_mass_date(self, field, row_nums, value):
        """Used by Mass Edit Dates - sets (or, with value="", clears) one
        date field across an explicit list of row numbers, regardless of
        what's currently selected/shown in the table."""
        self._apply_cell_updates([(r, field, value) for r in row_nums])

    def open_mass_edit_dates(self):
        if not self.etype.get("date_fields"):
            return
        MassEditDatesDialog(self, self).exec()

    def visible_row_entries(self):
        shown_rows = {self.table.item(r, 0).sort_value for r in range(self.table.rowCount())}
        return [e for e in self.all_rows if e["row"] in shown_rows]

    def selected_row_num(self):
        """For actions that only make sense on exactly one row (Edit, View
        Details, Show More) - now that the table allows selecting several
        at once."""
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            QMessageBox.information(self, "Select a row", "Select a row first.")
            return None
        if len(sel) > 1:
            QMessageBox.information(self, "Select one row",
                                     "This action works on a single row - select just one.")
            return None
        item = self.table.item(sel[0].row(), 0)
        return item.sort_value

    def selected_row_nums(self):
        """For actions that work on any number of rows (Remove Selected,
        Bulk Status)."""
        sel = self.table.selectionModel().selectedRows()
        return [self.table.item(idx.row(), 0).sort_value for idx in sel]

    def _on_row_double_clicked(self, index):
        # Double-clicking directly on one of the status checkboxes would
        # otherwise ALSO fire Edit underneath it - only open Edit when the
        # double-click landed on a plain data column (Row #, a summary
        # field, or a date field - never a checkbox column).
        if index.column() >= 1 + self._n_summary + self._n_dates:
            return
        self.edit_selected()

    # --------------------------------------------------------------- actions
    def add_new(self):
        row_num = da.find_first_blank_row(self.series_number, self.equip_key)
        dlg = EditDialog(self, self.series_number, self.equip_key, row_num,
                          is_new=True, prefill=self.filters)
        if dlg.exec() == QDialog.Accepted:
            self._record_add_undo(row_num)
            self.reload(reselect_row=row_num)
            self.main_window.refresh_sidebar_and_dashboard()
            self.main_window.statusBar().showMessage(f"Added row {row_num}", 3000)

    def _record_add_undo(self, row_num):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key
        try:
            values = da.read_full_row(sn, ek, row_num)
        except Exception:
            values = None

        def do_undo():
            da.delete_rows(sn, ek, [row_num])
            mw.refresh_current_view()

        def do_redo():
            if values is not None:
                da.save_row(sn, ek, row_num, values)
            mw.refresh_current_view()

        mw.undo_stack.push(f"add row {row_num}", do_undo, do_redo)

    def edit_selected(self):
        row_num = self.selected_row_num()
        if row_num is None:
            return
        try:
            before_values = da.read_full_row(self.series_number, self.equip_key, row_num)
        except Exception:
            before_values = None
        dlg = EditDialog(self, self.series_number, self.equip_key, row_num, is_new=False)
        if dlg.exec() == QDialog.Accepted:
            try:
                after_values = da.read_full_row(self.series_number, self.equip_key, row_num)
            except Exception:
                after_values = None
            self._record_edit_undo(row_num, before_values, after_values)
            self.reload(reselect_row=row_num)
            self.main_window.refresh_sidebar_and_dashboard()
            self.main_window.statusBar().showMessage(f"Saved row {row_num}", 3000)

    def _record_edit_undo(self, row_num, before_values, after_values):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key

        def do_undo():
            if before_values is not None:
                da.save_row(sn, ek, row_num, before_values)
            mw.refresh_current_view()

        def do_redo():
            if after_values is not None:
                da.save_row(sn, ek, row_num, after_values)
            mw.refresh_current_view()

        mw.undo_stack.push(f"edit row {row_num}", do_undo, do_redo)

    def show_more(self):
        row_num = self.selected_row_num()
        if row_num is None:
            return
        dlg = RowDetailDialog(self, self.series_number, self.equip_key, row_num)
        if dlg.exec() == QDialog.Accepted and dlg.opened_edit:
            self.reload(reselect_row=row_num)
            self.main_window.refresh_sidebar_and_dashboard()

    def view_details(self):
        row_num = self.selected_row_num()
        if row_num is None:
            return
        try:
            pdf_path = da.generate_preview_pdf(self.series_number, self.equip_key, row_num)
            da.open_file(pdf_path)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't build preview", str(exc))

    def open_export(self):
        ExportDialog(self, self.series_number, self.equip_key, filters=self.filters).exec()
        self.reload()  # a "selected" export queue run may have cleared checkboxes

    # ---------------------------------------------------------- bulk status
    def _build_bulk_status_menu(self):
        menu = QMenu(self)
        for field in ("installed", "submitted", "accepted"):
            label = self.STATUS_LABELS[field]
            mark = menu.addAction(f"Mark Selected \u2013 {label}")
            mark.triggered.connect(lambda checked=False, f=field: self._bulk_set_status(f, True))
        menu.addSeparator()
        for field in ("installed", "submitted", "accepted"):
            label = self.STATUS_LABELS[field]
            unmark = menu.addAction(f"Unmark Selected \u2013 {label}")
            unmark.triggered.connect(lambda checked=False, f=field: self._bulk_set_status(f, False))
        menu.addSeparator()
        add_q = menu.addAction("Add Selected to Export Queue")
        add_q.triggered.connect(lambda checked=False: self._bulk_set_status("export", True))
        rm_q = menu.addAction("Remove Selected from Export Queue")
        rm_q.triggered.connect(lambda checked=False: self._bulk_set_status("export", False))
        return menu

    def _bulk_set_status(self, field, value):
        row_nums = self.selected_row_nums()
        if not row_nums:
            QMessageBox.information(self, "Select rows", "Select one or more rows first.")
            return
        entries = [self._entry_by_row[rn] for rn in row_nums if rn in self._entry_by_row]
        if not entries:
            return
        before = {e.get(self.etype["key_field"]): bool(e.get(field)) for e in entries}
        keys = [(self.series_number, self.equip_key, kv) for kv in before]
        try:
            da.bulk_set_status(keys, **{field: value})
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save status", str(exc))
            return
        self._record_bulk_status_undo(field, before, value)
        self.reload(reselect_row=row_nums)
        self.main_window.refresh_sidebar_and_dashboard()

    def _record_bulk_status_undo(self, field, before_map, new_value):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key

        def do_undo():
            for kv, prev in before_map.items():
                da.set_status(sn, ek, kv, **{field: prev})
            mw.refresh_current_view()

        def do_redo():
            keys = [(sn, ek, kv) for kv in before_map]
            da.bulk_set_status(keys, **{field: new_value})
            mw.refresh_current_view()

        n = len(before_map)
        label = self.STATUS_LABELS.get(field, field)
        mw.undo_stack.push(f"{label} on {n} row{'s' if n != 1 else ''}", do_undo, do_redo)

    def queue_all_shown_for_export(self):
        shown = self.visible_row_entries()
        if not shown:
            QMessageBox.information(self, "Nothing to queue",
                                     "Nothing shown to add to the export queue.")
            return
        before = {e.get(self.etype["key_field"]): bool(e.get("export")) for e in shown}
        keys = [(self.series_number, self.equip_key, kv) for kv in before]
        try:
            da.bulk_set_status(keys, export=True)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save status", str(exc))
            return
        self._record_bulk_status_undo("export", before, True)
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()
        self.main_window.statusBar().showMessage(f"Queued {len(before)} row(s) for export", 3000)

    def clear_export_queue_shown(self):
        shown = self.visible_row_entries()
        if not shown:
            return
        before = {e.get(self.etype["key_field"]): bool(e.get("export")) for e in shown}
        keys = [(self.series_number, self.equip_key, kv) for kv in before]
        try:
            da.bulk_set_status(keys, export=False)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save status", str(exc))
            return
        self._record_bulk_status_undo("export", before, False)
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()

    def select_all_in_view(self):
        """Selects every row currently in the table - i.e. everything the
        active search filter is showing, not necessarily every row in the
        sheet."""
        if self.table.rowCount() == 0:
            return
        self.table.selectAll()

    def remove_selected(self):
        row_nums = self.selected_row_nums()
        if not row_nums:
            QMessageBox.information(self, "Select rows", "Select one or more rows first.")
            return

        key_field = self.etype["summary_fields"][0]
        by_row = {e["row"]: e for e in self.all_rows}
        preview_keys = [str(by_row[rn].get(key_field) or f"row {rn}")
                         for rn in row_nums[:5] if rn in by_row]
        preview = ", ".join(preview_keys)
        if len(row_nums) > 5:
            preview += f", +{len(row_nums) - 5} more"

        reply = QMessageBox.question(
            self, "Remove rows",
            f"Remove {len(row_nums)} row(s)?\n\n{preview}\n\n"
            "This clears their data from the workbook. It doesn't touch any "
            "other row, and the row number(s) become free for the next 'Add "
            "New'. Press Ctrl+Z right after if this was a mistake.")
        if reply != QMessageBox.Yes:
            return

        # Capture full state (row values + status) for undo, before anything
        # is cleared - delete_rows() below also drops the status entries.
        snapshots = []
        for rn in row_nums:
            try:
                values = da.read_full_row(self.series_number, self.equip_key, rn)
            except Exception:
                values = None
            key_val = values.get(self.etype["key_field"]) if values else None
            status = da.get_status(self.series_number, self.equip_key, key_val) if key_val else None
            snapshots.append((rn, values, status))

        try:
            da.delete_rows(self.series_number, self.equip_key, row_nums)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't remove rows", str(exc))
            return

        self._record_remove_undo(snapshots)
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()

    def _record_remove_undo(self, snapshots):
        mw, sn, ek = self.main_window, self.series_number, self.equip_key
        key_field = da.EQUIPMENT_TYPES[ek]["key_field"]

        def do_undo():
            for rn, values, status in snapshots:
                if values is None:
                    continue
                da.save_row(sn, ek, rn, values)
                key_val = values.get(key_field)
                if key_val and status:
                    da.set_status(sn, ek, key_val, **status)
            mw.refresh_current_view()

        def do_redo():
            rns = [rn for rn, values, _ in snapshots if values is not None]
            if rns:
                da.delete_rows(sn, ek, rns)
            mw.refresh_current_view()

        n = len(snapshots)
        mw.undo_stack.push(f"remove {n} row{'s' if n != 1 else ''}", do_undo, do_redo)

    def _on_table_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is not None and not item.isSelected():
            # Right-clicking a row outside the current selection acts on
            # just that row - matches normal Explorer/Excel conventions.
            self.table.clearSelection()
            self.table.selectRow(item.row())

        menu = QMenu(self)
        show_more_action = menu.addAction("Show More")
        view_action = menu.addAction("View Details")
        edit_action = menu.addAction("Edit")
        menu.addSeparator()
        export_action = menu.addAction("Export...")
        add_queue_action = menu.addAction("Add Selected to Export Queue")
        rm_queue_action = menu.addAction("Remove Selected from Export Queue")
        menu.addSeparator()
        mark_installed = menu.addAction("Mark Selected \u2013 Installed")
        mark_submitted = menu.addAction("Mark Selected \u2013 Submitted")
        mark_accepted = menu.addAction("Mark Selected \u2013 Accepted")
        menu.addSeparator()
        select_all_action = menu.addAction("Select All")
        remove_action = menu.addAction("Remove Selected")

        if item is None:
            # Right-clicked empty space below the last row - only the
            # actions that don't depend on a selection make sense.
            for a in (show_more_action, view_action, edit_action, add_queue_action,
                      rm_queue_action, mark_installed, mark_submitted, mark_accepted,
                      remove_action):
                a.setEnabled(False)

        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen is None:
            return
        elif chosen == show_more_action:
            self.show_more()
        elif chosen == view_action:
            self.view_details()
        elif chosen == edit_action:
            self.edit_selected()
        elif chosen == export_action:
            self.open_export()
        elif chosen == add_queue_action:
            self._bulk_set_status("export", True)
        elif chosen == rm_queue_action:
            self._bulk_set_status("export", False)
        elif chosen == mark_installed:
            self._bulk_set_status("installed", True)
        elif chosen == mark_submitted:
            self._bulk_set_status("submitted", True)
        elif chosen == mark_accepted:
            self._bulk_set_status("accepted", True)
        elif chosen == select_all_action:
            self.select_all_in_view()
        elif chosen == remove_action:
            self.remove_selected()


# =============================================================================
# "Show More" - a fast, read-only view of every field on one row, not just
# the 3-4 summary columns the Index table has room for. No PDF is built (that
# is what View Details is for) - this just lists label: value for the whole
# schema, grouped into the same sections the Edit form uses, so it reads
# like a plain-language printout of the row.
# =============================================================================
class RowDetailDialog(QDialog):
    def __init__(self, parent, series_number, equip_key, row_num):
        super().__init__(parent)
        self.series_number = series_number
        self.equip_key = equip_key
        self.row_num = row_num
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.opened_edit = False
        self.setWindowTitle(f"{self.etype['label']} \u2013 Row {row_num} \u2013 Full Details")
        self.resize(700, 680)

        schema = self.etype["schema"]
        try:
            values = da.read_full_row(series_number, equip_key, row_num)
        except Exception as exc:
            values = {}
            QMessageBox.critical(self, "Couldn't read row", str(exc))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 14, 16, 12)
        inner_layout.setSpacing(12)

        titles = dict(schema.SECTION_TITLES)
        titles.setdefault("control", "Status")
        sections = list(dict.fromkeys(f["section"] for f in schema.LOG_COLUMNS))
        for section in sections:
            fields_here = [f for f in schema.LOG_COLUMNS if f["section"] == section
                            and f["id"] != "export_flag" and f["id"] != "yanda_qa_signature"]
            if not fields_here:
                continue
            box = QGroupBox(titles.get(section, section.title()))
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(6)
            grid.setColumnStretch(1, 1)
            for row, field in enumerate(fields_here):
                label = QLabel(field["label"])
                label.setObjectName("FieldLabel")
                label.setWordWrap(True)
                val_text = str(values.get(field["id"], "") or "\u2014")
                value = QLabel(val_text)
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                grid.addWidget(label, row, 0)
                grid.addWidget(value, row, 1)
            inner_layout.addWidget(box)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        footer = QFrame()
        footer.setObjectName("Card")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        edit_btn = make_button("Edit This Row...", "Primary")
        edit_btn.clicked.connect(self._open_edit)
        footer_layout.addWidget(edit_btn)
        footer_layout.addStretch()
        close_btn = make_button("Close", "Ghost")
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)
        outer.addWidget(footer)

    def _open_edit(self):
        dlg = EditDialog(self.parent(), self.series_number, self.equip_key,
                          self.row_num, is_new=False)
        if dlg.exec() == QDialog.Accepted:
            self.opened_edit = True
            self.accept()


# =============================================================================
# Mass Edit Dates - set (or clear) one date field across many rows at once.
# The guided, discoverable counterpart to the Index grid's Ctrl+C/Ctrl+V/
# Ctrl+D power-user shortcuts, for the same underlying operation.
# =============================================================================
class MassEditDatesDialog(QDialog):
    def __init__(self, parent, page):
        super().__init__(parent)
        self.page = page
        self.setWindowTitle("Mass Edit Dates")
        self.resize(440, 340)

        layout = QVBoxLayout(self)

        n_selected = len(page.selected_row_nums())
        n_shown = len(page.visible_row_entries())
        intro = QLabel("Set or clear a date field across many rows in one go.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        form.addWidget(QLabel("Date field"), 0, 0)
        self.field_combo = QComboBox()
        for fid, label in zip(page.etype.get("date_fields", []), page.etype.get("date_labels", [])):
            self.field_combo.addItem(label, fid)
        form.addWidget(self.field_combo, 0, 1)

        form.addWidget(QLabel("Apply to"), 1, 0)
        self.scope_combo = QComboBox()
        self.scope_combo.addItem(f"Selected rows only ({n_selected})", "selected")
        self.scope_combo.addItem(f"Every row currently shown ({n_shown})", "shown")
        if n_selected == 0:
            self.scope_combo.setCurrentIndex(1)
        form.addWidget(self.scope_combo, 1, 1)
        layout.addLayout(form)

        self.clear_check = QCheckBox("Clear this date instead of setting one (leave blank)")
        self.clear_check.toggled.connect(self._toggle_clear)
        layout.addWidget(self.clear_check)

        date_row = QHBoxLayout()
        date_row.addWidget(QLabel("Date"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        date_row.addWidget(self.date_edit)
        date_row.addStretch()
        layout.addLayout(date_row)

        note = QLabel("New rows always start with every date blank - this is the fast way to "
                       "fill (or clear) one in bulk once you actually know it, without opening "
                       "each row one at a time.")
        note.setObjectName("FieldLabel")
        note.setWordWrap(True)
        layout.addWidget(note)

        layout.addStretch()
        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        self.apply_btn = make_button("Apply", "Success")
        self.apply_btn.clicked.connect(self._apply)
        footer.addWidget(cancel_btn)
        footer.addWidget(self.apply_btn)
        layout.addLayout(footer)

        if not page.etype.get("date_fields"):
            self.field_combo.setEnabled(False)
            self.apply_btn.setEnabled(False)

    def _toggle_clear(self, checked):
        self.date_edit.setEnabled(not checked)

    def _apply(self):
        field = self.field_combo.currentData()
        if field is None:
            return
        scope = self.scope_combo.currentData()
        rows = (self.page.selected_row_nums() if scope == "selected"
                else [e["row"] for e in self.page.visible_row_entries()])
        if not rows:
            QMessageBox.information(self, "No rows", "No rows in that scope.")
            return
        value = "" if self.clear_check.isChecked() else self.date_edit.date().toString("yyyy-MM-dd")
        action = "Clear" if self.clear_check.isChecked() else f"Set to {value}"
        label = self.field_combo.currentText()
        reply = QMessageBox.question(
            self, "Mass Edit Dates",
            f"{action} \u2013 {label} \u2013 on {len(rows)} row(s)?")
        if reply != QMessageBox.Yes:
            return
        self.page.apply_mass_date(field, rows, value)
        self.accept()


# =============================================================================
# Stubs - filled in next
# =============================================================================
class EditDialog(QDialog):
    """One continuous scrollable page (no tabs), grouped into titled
    QGroupBox sections, with a 'Jump to' dropdown and a Save/Cancel bar
    that stays fixed at the bottom regardless of scroll position."""

    def __init__(self, parent, series_number, equip_key, row_num, is_new, prefill=None):
        super().__init__(parent)
        self.series_number = series_number
        self.equip_key = equip_key
        self.row_num = row_num
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.widgets = {}
        self.resize(880, 720)

        schema = self.etype["schema"]
        existing = {} if is_new else da.read_full_row(series_number, equip_key, row_num)
        effective = dict(existing)
        if is_new:
            for fid, val in (prefill or {}).items():
                effective.setdefault(fid, val)

        self.setWindowTitle(("Add New " if is_new else "Edit ") + self.etype["label"]
                             + f" \u2013 Row {row_num}")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(16, 14, 16, 6)
        nav_row.addWidget(QLabel("Jump to:"))
        self.section_picker = QComboBox()
        self.section_picker.currentIndexChanged.connect(self._jump_to_section)
        nav_row.addWidget(self.section_picker)
        nav_row.addStretch()
        outer.addLayout(nav_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 4, 16, 12)
        inner_layout.setSpacing(12)

        sections = list(dict.fromkeys(f["section"] for f in schema.LOG_COLUMNS))
        titles = dict(schema.SECTION_TITLES)
        titles.setdefault("control", "Status")

        self.section_boxes = {}
        for section in sections:
            section_title = titles.get(section, section.title())
            box = QGroupBox(section_title)
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(8)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)

            fields_here = [f for f in schema.LOG_COLUMNS if f["section"] == section]
            self._build_section_body(grid, fields_here, effective)

            inner_layout.addWidget(box)
            self.section_boxes[section] = box
            self.section_picker.addItem(section_title, section)

        inner_layout.addStretch()
        self.scroll.setWidget(inner)
        outer.addWidget(self.scroll, stretch=1)

        footer = QFrame()
        footer.setObjectName("Card")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        footer_layout.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        save_btn = make_button("Save", "Success")
        save_btn.clicked.connect(self.save)
        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(save_btn)
        outer.addWidget(footer)

        # Dirty-tracking snapshot AFTER widgets exist, over exactly the
        # fields that got one - the signature field intentionally has none.
        self.initial_values = {fid: effective.get(fid, "") for fid in self.widgets}

    # ------------------------------------------------------------- building
    def _build_section_body(self, grid, fields, existing):
        row = 0
        col_pair = 0
        for field in fields:
            if field["id"] == "yanda_qa_signature":
                if col_pair != 0:
                    row += 1
                    col_pair = 0
                self._add_signature_row(grid, row)
                row += 1
                continue

            widget = self._make_widget(field, existing.get(field["id"], ""))
            self.widgets[field["id"]] = widget

            is_required = field["id"] == self.etype["key_field"]
            label = QLabel(field["label"] + ("  *" if is_required else ""))
            label.setObjectName("RequiredLabel" if is_required else "FieldLabel")
            label.setWordWrap(True)

            if field["ftype"] == "multiline":
                if col_pair != 0:
                    row += 1
                    col_pair = 0
                grid.addWidget(label, row, 0, 1, 4)
                row += 1
                grid.addWidget(widget, row, 0, 1, 4)
                row += 1
            else:
                base_col = col_pair * 2
                grid.addWidget(label, row, base_col)
                grid.addWidget(widget, row, base_col + 1)
                if col_pair == 0:
                    col_pair = 1
                else:
                    col_pair = 0
                    row += 1

    def _add_signature_row(self, grid, row):
        active = da.get_active_signature_path()
        if active:
            label = QLabel(f"\u2713  Signing as: {active.name}")
            label.setObjectName("SigOk")
        else:
            label = QLabel("\u26a0  No signature set up - see Settings \u2192 Manage Signatures")
            label.setObjectName("SigWarn")
        grid.addWidget(label, row, 0, 1, 4)

    def _make_widget(self, field, initial_value):
        return make_field_widget(field, initial_value)

    def _read_widget(self, widget):
        return read_field_widget(widget)

    def _current_values(self):
        return {fid: self._read_widget(w) for fid, w in self.widgets.items()}

    def _jump_to_section(self, index):
        section = self.section_picker.itemData(index)
        box = self.section_boxes.get(section)
        if box:
            self.scroll.ensureWidgetVisible(box, ymargin=10)

    # ------------------------------------------------------------ lifecycle
    def is_dirty(self):
        return self._current_values() != self.initial_values

    def closeEvent(self, event):
        if self.is_dirty():
            reply = QMessageBox.question(self, "Unsaved changes", "Discard unsaved changes?")
            if reply != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()

    def reject(self):
        if self.is_dirty():
            reply = QMessageBox.question(self, "Unsaved changes", "Discard unsaved changes?")
            if reply != QMessageBox.Yes:
                return
        super().reject()

    def save(self):
        values = self._current_values()
        key_field = self.etype["key_field"]
        key_value = values.get(key_field, "").strip()

        if not key_value:
            key_label = next(f["label"] for f in self.etype["schema"].LOG_COLUMNS
                              if f["id"] == key_field)
            QMessageBox.warning(self, "Missing required field",
                                 f'"{key_label}" can\'t be blank - the Index list, the '
                                 f'row-selection, and the PDF filename are all built from it.')
            return

        dup_row = da.find_duplicate_row(self.series_number, self.equip_key, key_value,
                                         exclude_row=self.row_num)
        if dup_row is not None:
            key_label = next(f["label"] for f in self.etype["schema"].LOG_COLUMNS
                              if f["id"] == key_field)
            QMessageBox.warning(self, f"Duplicate {key_label}",
                                 f'"{key_value}" is already used on row {dup_row}. Each '
                                 f'{key_label} must be unique - Installed/Submitted status '
                                 f'and PDF filenames are both keyed off it.')
            return

        try:
            da.save_row(self.series_number, self.equip_key, self.row_num, values)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save", str(exc))
            return
        self.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent, on_series_change=None):
        super().__init__(parent)
        self.on_series_change = on_series_change
        self.setWindowTitle("Settings")
        self.resize(440, 680)

        layout = QVBoxLayout(self)
        settings = da.load_settings()

        appearance_label = QLabel("Appearance")
        appearance_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(appearance_label)

        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:"))
        light_radio = QRadioButton("Light")
        dark_radio = QRadioButton("Dark")
        (dark_radio if settings.get("theme") == "dark" else light_radio).setChecked(True)
        light_radio.toggled.connect(lambda checked: checked and self._set_theme("light"))
        dark_radio.toggled.connect(lambda checked: checked and self._set_theme("dark"))
        theme_row.addWidget(light_radio)
        theme_row.addWidget(dark_radio)
        theme_row.addStretch()
        layout.addLayout(theme_row)

        layout.addSpacing(16)
        export_label = QLabel("Default Export Options")
        export_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(export_label)
        hint = QLabel("Used to prefill the Export dialog each time - can still be changed per export.")
        hint.setObjectName("FieldLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.flatten_check = QCheckBox("Flatten PDFs by default")
        self.flatten_check.setChecked(settings.get("default_flatten", False))
        self.flatten_check.toggled.connect(lambda v: self._save_setting_safe("default_flatten", v))
        layout.addWidget(self.flatten_check)

        self.sig_check = QCheckBox("Include signature stamp by default")
        self.sig_check.setChecked(settings.get("default_include_signature", True))
        self.sig_check.toggled.connect(lambda v: self._save_setting_safe("default_include_signature", v))
        layout.addWidget(self.sig_check)

        layout.addSpacing(16)
        wb_label = QLabel("Workbook")
        wb_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(wb_label)
        wb_name = QLabel(da.WORKBOOK_PATH.name)
        wb_name.setObjectName("FieldLabel")
        layout.addWidget(wb_name)
        open_wb_btn = make_button("Open Excel File", "Ghost")
        open_wb_btn.clicked.connect(self._open_workbook)
        layout.addWidget(open_wb_btn, alignment=Qt.AlignLeft)

        layout.addSpacing(16)
        series_mgmt_label = QLabel("Manage Series")
        series_mgmt_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(series_mgmt_label)
        series_hint = QLabel(
            "Rename gives a series a friendlier label everywhere it's shown. "
            "Remove un-registers it from the app and archives its sheets in "
            "the workbook (hidden, not deleted) - nothing is ever "
            "permanently destroyed by this button.")
        series_hint.setObjectName("FieldLabel")
        series_hint.setWordWrap(True)
        layout.addWidget(series_hint)
        self.series_list_area = QVBoxLayout()
        layout.addLayout(self.series_list_area)
        self._render_series_list()

        layout.addSpacing(16)
        sig_label = QLabel("Signatures")
        sig_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(sig_label)
        active = da.get_setting("active_signature") or "(none set)"
        self.active_sig_label = QLabel(f"Currently signing as: {active}")
        self.active_sig_label.setObjectName("FieldLabel")
        layout.addWidget(self.active_sig_label)
        manage_sig_btn = make_button("Manage Signatures...", "Ghost")
        manage_sig_btn.clicked.connect(self._open_signature_manager)
        layout.addWidget(manage_sig_btn, alignment=Qt.AlignLeft)

        layout.addSpacing(16)
        shortcut_label = QLabel("Desktop Shortcut")
        shortcut_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(shortcut_label)
        shortcut_hint = QLabel("Re-create it here if it ever gets deleted.")
        shortcut_hint.setObjectName("FieldLabel")
        layout.addWidget(shortcut_hint)
        shortcut_btn = make_button("Create Desktop Shortcut", "Ghost")
        shortcut_btn.clicked.connect(self._create_shortcut)
        layout.addWidget(shortcut_btn, alignment=Qt.AlignLeft)

        layout.addStretch()
        close_btn = make_button("Close", "Ghost")
        close_btn.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _set_theme(self, theme_name):
        self._save_setting_safe("theme", theme_name)

    def _save_setting_safe(self, key, value):
        try:
            da.set_setting(key, value)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save setting", str(exc))

    def _render_series_list(self):
        while self.series_list_area.count():
            item = self.series_list_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        numbers = da.list_series()
        if not numbers:
            none_label = QLabel("No series yet.")
            none_label.setObjectName("FieldLabel")
            self.series_list_area.addWidget(none_label)
            return

        for number in numbers:
            row = QHBoxLayout()
            label = QLabel(da.series_display_label(number))
            label.setObjectName("FieldLabel")
            row.addWidget(label, stretch=1)
            rename_btn = make_button("Rename", "Ghost")
            rename_btn.clicked.connect(lambda checked=False, n=number: self._rename_series(n))
            remove_btn = make_button("Remove", "Danger")
            remove_btn.clicked.connect(lambda checked=False, n=number: self._remove_series(n))
            row.addWidget(rename_btn)
            row.addWidget(remove_btn)
            wrapper = QWidget()
            wrapper.setLayout(row)
            self.series_list_area.addWidget(wrapper)

    def _rename_series(self, number):
        rename_series_flow(self, number)
        self._render_series_list()
        if self.on_series_change:
            self.on_series_change()

    def _remove_series(self, number):
        remove_series_flow(self, number)
        self._render_series_list()
        if self.on_series_change:
            self.on_series_change()

    def _open_workbook(self):
        try:
            da.open_workbook()
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't open workbook", str(exc))

    def _open_signature_manager(self):
        SignatureManagerDialog(self, on_change=self._refresh_active_sig).exec()

    def _refresh_active_sig(self):
        active = da.get_setting("active_signature") or "(none set)"
        self.active_sig_label.setText(f"Currently signing as: {active}")

    def _create_shortcut(self):
        try:
            path = da.create_desktop_shortcut()
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't create shortcut", str(exc))
            return
        da.set_setting("desktop_shortcut_created", True)
        QMessageBox.information(self, "Done", f"Shortcut created:\n{path}")


class SignatureManagerDialog(QDialog):
    def __init__(self, parent, on_change=None):
        super().__init__(parent)
        self.on_change = on_change
        self.setWindowTitle("Manage Signatures")
        self.resize(480, 460)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        add_label = QLabel("Add a new signature")
        add_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(add_label)
        hint = QLabel("Name it, then choose a PNG or JPG image - it's copied into "
                      "the assets/ folder under that name.")
        hint.setObjectName("FieldLabel")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        add_row = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. John Smith")
        add_btn = make_button("Choose Image and Add...", "Primary")
        add_btn.clicked.connect(self._browse_and_add)
        add_row.addWidget(self.name_edit)
        add_row.addWidget(add_btn)
        layout.addLayout(add_row)

        layout.addSpacing(12)
        list_label = QLabel("Existing signatures  (pick one to make it active)")
        list_label.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(list_label)

        self.list_area = QVBoxLayout()
        layout.addLayout(self.list_area)
        self._render_list()

        layout.addStretch()
        close_btn = make_button("Close", "Ghost")
        close_btn.clicked.connect(self.accept)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _render_list(self):
        while self.list_area.count():
            item = self.list_area.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        active = da.get_setting("active_signature") or ""
        sigs = da.list_signatures()
        if not sigs:
            none_label = QLabel("No signature images yet - add one above.")
            none_label.setObjectName("FieldLabel")
            self.list_area.addWidget(none_label)
            return

        self.sig_group = QButtonGroup(self)
        for name in sigs:
            row = QHBoxLayout()
            radio = QRadioButton(name)
            radio.setChecked(name == active)
            radio.toggled.connect(lambda checked, n=name: checked and self._activate(n))
            self.sig_group.addButton(radio)
            row.addWidget(radio)
            if name == active:
                active_tag = QLabel("active")
                active_tag.setObjectName("SigOk")
                row.addWidget(active_tag)
            row.addStretch()
            del_btn = make_button("Delete", "Danger")
            del_btn.clicked.connect(lambda checked=False, n=name: self._delete(n))
            row.addWidget(del_btn)
            wrapper = QWidget()
            wrapper.setLayout(row)
            self.list_area.addWidget(wrapper)

    def _activate(self, name):
        try:
            da.set_active_signature(name)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save setting", str(exc))
            return
        if self.on_change:
            self.on_change()
        self._render_list()

    def _browse_and_add(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Type a name for this signature first.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a signature image", "", "Image files (*.png *.jpg *.jpeg)")
        if not path:
            return
        try:
            da.add_signature(path, name)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't add signature", str(exc))
            return
        self.name_edit.clear()
        if self.on_change:
            self.on_change()
        self._render_list()

    def _delete(self, name):
        reply = QMessageBox.question(self, "Delete signature", f'Delete "{name}"?')
        if reply != QMessageBox.Yes:
            return
        try:
            da.delete_signature(name)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't delete signature", str(exc))
            return
        if self.on_change:
            self.on_change()
        self._render_list()


class ExportDialog(QDialog):
    def __init__(self, parent, series_number, equip_key, filters=None):
        super().__init__(parent)
        self.series_number = series_number
        self.equip_key = equip_key
        self.filters = dict(filters or {})
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.setWindowTitle(f"Export {self.etype['label']}s \u2013 "
                             f"{da.series_display_label(series_number)}")
        self.resize(500, 680)
        settings = da.load_settings()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        if self.filters:
            filt_text = ", ".join(f"{k} = {v}" for k, v in self.filters.items())
            filt_label = QLabel(f"\U0001F50E Only exporting rows where {filt_text} "
                                 f"(matches the filter this Index view is currently showing)")
            filt_label.setObjectName("Breadcrumb")
            filt_label.setWordWrap(True)
            layout.addWidget(filt_label)

        which_label = QLabel("Which rows?")
        which_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(which_label)

        checked_count = sum(1 for r in da.read_index_rows_filtered(series_number, equip_key, self.filters)
                             if r.get("export"))
        self.mode_group = QButtonGroup(self)
        selected_radio = QRadioButton(f"Only rows checked in the Export column ({checked_count} checked)")
        selected_radio.setChecked(True)
        flagged_radio = QRadioButton('Only rows flagged "Export to PDF = Y" in Excel')
        all_radio = QRadioButton(f'Every row with a {self.etype["summary_labels"][0]} filled in')
        self.mode_group.addButton(selected_radio, 0)
        self.mode_group.addButton(flagged_radio, 1)
        self.mode_group.addButton(all_radio, 2)
        layout.addWidget(selected_radio)
        if checked_count == 0:
            hint = QLabel("Nothing's checked yet - tick the Export column on the rows you "
                           "want, back in the Index table, or use \u201cQueue All Shown for "
                           "Export\u201d for a quick start.")
            hint.setObjectName("FieldLabel")
            hint.setWordWrap(True)
            layout.addWidget(hint)
        layout.addWidget(flagged_radio)
        layout.addWidget(all_radio)

        layout.addSpacing(4)
        self.clear_after_check = QCheckBox("Uncheck those rows' Export boxes once exported")
        self.clear_after_check.setChecked(True)
        self.clear_after_check.setToolTip("Only applies to the 'checked in the Export column' mode above")
        layout.addWidget(self.clear_after_check)

        layout.addSpacing(10)
        suffix_label = QLabel("Filename suffix")
        suffix_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(suffix_label)
        suffix_hint = QLabel('e.g. "DEV." makes "29103-PIT-1021 DEV..pdf" - leave blank '
                              'for just the tag on its own.')
        suffix_hint.setObjectName("FieldLabel")
        suffix_hint.setWordWrap(True)
        layout.addWidget(suffix_hint)
        self.suffix_edit = QLineEdit("DEV." if equip_key == "transmitter" else "")
        layout.addWidget(self.suffix_edit)

        layout.addSpacing(10)
        opts_row = QHBoxLayout()
        self.flatten_check = QCheckBox("Flatten")
        self.flatten_check.setChecked(settings.get("default_flatten", False))
        self.sig_check = QCheckBox("Include signature")
        self.sig_check.setChecked(settings.get("default_include_signature", True))
        opts_row.addWidget(self.flatten_check)
        opts_row.addWidget(self.sig_check)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        self.merge_check = QCheckBox("Also combine everything into one merged PDF")
        layout.addWidget(self.merge_check)

        layout.addSpacing(10)
        folder_label = QLabel("Output folder")
        folder_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(folder_label)
        folder_hint = QLabel("Files always land inside output_pdfs/ next to the workbook. "
                              "Optionally put this run into its own subfolder there - it's "
                              "created automatically if it doesn't exist.")
        folder_hint.setObjectName("FieldLabel")
        folder_hint.setWordWrap(True)
        layout.addWidget(folder_hint)
        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("output_pdfs/"))
        self.subfolder_edit = QLineEdit()
        folder_row.addWidget(self.subfolder_edit, stretch=1)
        dated_btn = make_button("Use dated folder", "Link")
        dated_btn.clicked.connect(self._fill_dated_folder)
        folder_row.addWidget(dated_btn)
        layout.addLayout(folder_row)

        layout.addSpacing(10)
        date_label = QLabel("Dates")
        date_label.setStyleSheet("font-weight: 700;")
        layout.addWidget(date_label)

        self.filename_date_check = QCheckBox("Include today's date in each filename")
        self.filename_date_check.setToolTip(
            f"e.g. \"29103-PIT-1021 DEV. {datetime.date.today().isoformat()}.pdf\"")
        layout.addWidget(self.filename_date_check)

        self.sign_date_check = None
        self.sign_date_edit = None
        sign_off_hint = QLabel(
            "Sign-off dates come from real columns now, the same for both equipment types - "
            "edit them in the Index grid or with Mass Edit Dates (Ctrl+Shift+D) before "
            "exporting, and they'll appear on the PDF automatically."
            + (" (YANDA QC Representative - Date, in this case.)" if equip_key == "valve" else
               " (QA Rep Date / Client Rep Date, in this case.)"))
        sign_off_hint.setObjectName("FieldLabel")
        sign_off_hint.setWordWrap(True)
        layout.addWidget(sign_off_hint)

        layout.addStretch()
        outer.addWidget(body, stretch=1)

        footer = QFrame()
        footer.setObjectName("Card")
        footer_layout = QHBoxLayout(footer)
        footer_layout.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        run_btn = make_button("Run Export", "Success")
        run_btn.clicked.connect(self._run)
        footer_layout.addWidget(cancel_btn)
        footer_layout.addWidget(run_btn)
        outer.addWidget(footer)

    def _fill_dated_folder(self):
        self.subfolder_edit.setText(f"{datetime.date.today().isoformat()}_export")

    def _run(self):
        mode = {0: "selected", 1: "flagged", 2: "all"}[self.mode_group.checkedId()]
        try:
            written = da.run_export(
                self.series_number, self.equip_key, mode=mode,
                suffix=self.suffix_edit.text(), flatten=self.flatten_check.isChecked(),
                include_signature=self.sig_check.isChecked(),
                subfolder=self.subfolder_edit.text().strip() or None,
                merge=self.merge_check.isChecked(), filters=self.filters or None,
                clear_after_selected=self.clear_after_check.isChecked(),
                include_date_in_filename=self.filename_date_check.isChecked())
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        if not written:
            QMessageBox.information(self, "Nothing exported", "No rows matched - nothing was exported.")
            return
        folder = da.HERE / "output_pdfs" / (self.subfolder_edit.text().strip() or "")
        QMessageBox.information(self, "Export complete",
                                 f"Wrote {len(written)} file(s) to:\n{folder.resolve()}")
        self.accept()



# =============================================================================
# Populating Wizard - bulk data entry for a batch of similar equipment.
#
# Flow: pick a Series + equipment type and a tag pattern (Area Code + Tag
# Type) -> decide which fields should carry over unchanged from one entry
# to the next ("repeat") -> repeatedly fill in just what's different about
# each new item (mainly the sequence number and anything not marked as
# repeating) and save straight into the workbook, looping until you stop.
# A single resumable draft can be saved mid-batch and picked back up later.
# =============================================================================
WIZARD_DEFAULT_STICKY = {
    "transmitter": {
        "customer_ref", "project", "location", "contract_no", "system_number",
        "make", "signal_type", "local_display",
        "te1_make", "te1_model", "te1_serial", "te1_caldate",
        "te2_make", "te2_model", "te2_serial", "te2_caldate",
        "te3_make", "te3_model", "te3_serial", "te3_caldate",
        "yanda_qa_name",
    },
    "valve": {
        "customer_name", "project_name", "contract_no", "location", "system",
        "equip_make", "equip_model", "equip_serial", "equip_caldate",
        "qc_rep_name", "commissioning_rep_name",
    },
}


class DatasheetImportDialog(QDialog):
    """Reviews what datasheet_reader found in the PDF(s) the user picked,
    lets them choose a series and which detected records to bring in, then
    opens each one through the normal Add New form (pre-filled) so nothing
    ever gets saved without a final human look - the importer itself never
    writes a row on its own."""

    def __init__(self, parent, main_window, records):
        super().__init__(parent)
        self.main_window = main_window
        self.records = records
        self.setWindowTitle("Import from Datasheet PDF")
        self.resize(820, 560)

        outer = QVBoxLayout(self)
        header = QLabel("Import from Datasheet PDF")
        header.setObjectName("PageTitle")
        header.setContentsMargins(20, 16, 20, 6)
        outer.addWidget(header)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 0, 20, 16)

        n = len(records)
        intro = QLabel(f"Found {n} recognizable data sheet{'s' if n != 1 else ''}. Pick which "
                        "ones to bring in - each opens the normal Add New form, pre-filled, so "
                        "you can check every field before anything is actually saved.")
        intro.setWordWrap(True)
        body_layout.addWidget(intro)

        form = QHBoxLayout()
        form.addWidget(QLabel("Import into series:"))
        self.series_combo = QComboBox()
        all_series = da.list_series()
        area_counts = {}
        for r in records:
            if r["area_code"]:
                area_counts[r["area_code"]] = area_counts.get(r["area_code"], 0) + 1
        best_area = max(area_counts, key=area_counts.get) if area_counts else None
        default_index = 0
        for i, sn in enumerate(all_series):
            self.series_combo.addItem(da.series_display_label(sn), sn)
            if str(sn) == best_area:
                default_index = i
        if all_series:
            self.series_combo.setCurrentIndex(default_index)
        form.addWidget(self.series_combo, stretch=1)
        body_layout.addLayout(form)

        self.table = QTableWidget(len(records), 4)
        self.table.setHorizontalHeaderLabels(["Import", "Tag", "Type", "Service"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.checkboxes = []
        for r, rec in enumerate(records):
            box = QCheckBox()
            box.setChecked(True)
            wrapper = QWidget()
            wlayout = QHBoxLayout(wrapper)
            wlayout.setContentsMargins(0, 0, 0, 0)
            wlayout.setAlignment(Qt.AlignCenter)
            wlayout.addWidget(box)
            self.table.setCellWidget(r, 0, wrapper)
            self.checkboxes.append(box)
            self.table.setItem(r, 1, QTableWidgetItem(rec["tag"]))
            self.table.setItem(r, 2, QTableWidgetItem(rec["kind_label"]))
            self.table.setItem(r, 3, QTableWidgetItem(rec["fields"].get("service", "")))
        self.table.setColumnWidth(0, 56)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(2, 170)
        body_layout.addWidget(self.table, stretch=1)

        note = QLabel(
            "Only fields the data sheet gives a clear, direct answer for are pre-filled - "
            "everything else (serial numbers, field test results, sign-offs) starts blank, the "
            "same as any new row. Signal Type, and Valve Type for valves, are best-guesses "
            "worth a second look rather than a direct read - double-check those specifically "
            "before saving each one.")
        note.setObjectName("FieldLabel")
        note.setWordWrap(True)
        body_layout.addWidget(note)

        outer.addWidget(body, stretch=1)

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 0, 20, 16)
        footer.addStretch()
        close_btn = make_button("Close", "Ghost")
        close_btn.clicked.connect(self.reject)
        self.import_btn = make_button("Review & Add Checked", "Success")
        self.import_btn.clicked.connect(self._run_import)
        footer.addWidget(close_btn)
        footer.addWidget(self.import_btn)
        outer.addLayout(footer)

        if not all_series:
            self.import_btn.setEnabled(False)
            self.import_btn.setToolTip("Add a series first (+ Add New Series in the sidebar).")

    def _run_import(self):
        series_number = self.series_combo.currentData()
        if series_number is None:
            QMessageBox.warning(self, "No series", "Add a series first.")
            return
        checked = [rec for rec, box in zip(self.records, self.checkboxes) if box.isChecked()]
        if not checked:
            QMessageBox.information(self, "Nothing checked",
                                     "Check at least one record to import.")
            return

        added, skipped = 0, 0
        for rec in checked:
            equip_key = rec["equip_key"]
            row_num = da.find_first_blank_row(series_number, equip_key)
            dlg = EditDialog(self, series_number, equip_key, row_num, is_new=True,
                              prefill=rec["fields"])
            dlg.setWindowTitle(f"Review & Add \u2013 {rec['tag']} ({rec['kind_label']})")
            if dlg.exec() == QDialog.Accepted:
                self._record_add_undo(series_number, equip_key, row_num, rec["tag"])
                added += 1
            else:
                skipped += 1

        self.main_window.refresh_sidebar_and_dashboard()
        msg = (f"Added {added} of {len(checked)} record(s) into "
               f"{da.series_display_label(series_number)}.")
        if skipped:
            msg += f"\n{skipped} closed without saving, so nothing was added for those."
        QMessageBox.information(self, "Import complete", msg)
        self.accept()

    def _record_add_undo(self, series_number, equip_key, row_num, tag):
        mw = self.main_window
        try:
            values = da.read_full_row(series_number, equip_key, row_num)
        except Exception:
            values = None

        def do_undo():
            da.delete_rows(series_number, equip_key, [row_num])
            mw.refresh_current_view()

        def do_redo():
            if values is not None:
                da.save_row(series_number, equip_key, row_num, values)
            mw.refresh_current_view()

        mw.undo_stack.push(f"import {tag} (row {row_num})", do_undo, do_redo)


class MasterListImportDialog(QDialog):
    """Sensei Index 2.1, Phase 10.4 - three steps: pick file & review what
    the parser found (read-only so far), confirm which registered series
    each sheet maps to, then Import. Nothing is written until the final
    Import click on step 3 - and even then, only master_list.json changes.
    This never touches Instrumentation_Master_List.xlsx (read-only
    reference data) or Equipment_Inspection_Tracker.xlsx at all."""

    STEP_TITLES = ["1. Choose file", "2. Map sheets to series", "3. Import"]

    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Import Master List")
        self.resize(820, 600)

        self.file_path = None
        self.items_by_sheet = None
        self.summaries = None
        self.sheet_series_map = {}
        self.series_combos = {}

        outer = QVBoxLayout(self)
        header = QLabel("Import Master List")
        header.setObjectName("PageTitle")
        header.setContentsMargins(20, 16, 20, 0)
        outer.addWidget(header)
        self.step_label = QLabel()
        self.step_label.setObjectName("FieldLabel")
        self.step_label.setContentsMargins(20, 0, 20, 6)
        outer.addWidget(self.step_label)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, stretch=1)
        self.stack.addWidget(self._build_step1())
        self.stack.addWidget(self._build_step2())
        self.stack.addWidget(self._build_step3())

        footer = QHBoxLayout()
        footer.setContentsMargins(20, 0, 20, 16)
        self.back_btn = make_button("← Back", "Ghost")
        self.back_btn.clicked.connect(self._go_back)
        footer.addWidget(self.back_btn)
        footer.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        footer.addWidget(cancel_btn)
        self.next_btn = make_button("Next →", "Primary")
        self.next_btn.clicked.connect(self._go_next)
        footer.addWidget(self.next_btn)
        outer.addLayout(footer)

        remembered = da.get_setting("master_list_path")
        if remembered:
            self.path_edit.setText(remembered)

        self._refresh_step()

    # ------------------------------------------------------------- step 1
    def _build_step1(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 0, 20, 0)

        intro = QLabel(
            "Pick the client's Instrumentation Master List workbook. It's read-only "
            "reference data - this app never writes anything back into it.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        self.path_edit.setPlaceholderText("No file chosen")
        file_row.addWidget(self.path_edit, stretch=1)
        browse_btn = make_button("Browse...", "Ghost")
        browse_btn.clicked.connect(self._browse_file)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        self.summary_table = QTableWidget(0, 6)
        self.summary_table.setHorizontalHeaderLabels(
            ["Sheet", "Rows Found", "Transmitters", "Valves", "Out of Scope", "Problems"])
        self.summary_table.horizontalHeader().setStretchLastSection(True)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.summary_table, stretch=1)

        return page

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose Instrumentation Master List", "", "Excel files (*.xlsx)")
        if not path:
            return
        try:
            items_by_sheet, summaries = da.preview_master_list(path)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't read that file", str(exc))
            return

        self.file_path = path
        self.items_by_sheet = items_by_sheet
        self.summaries = summaries
        self.path_edit.setText(path)
        self._populate_summary_table()
        self.sheet_series_map = {}  # a new file invalidates any prior mapping
        self._rebuild_step2()
        self._refresh_step()

    def _populate_summary_table(self):
        self.summary_table.setRowCount(len(self.summaries))
        for r, summary in enumerate(self.summaries):
            values = [
                summary["sheet_name"], str(summary["rows_found"]),
                str(summary["transmitter"]), str(summary["valve"]),
                str(summary["out_of_scope"]),
                "; ".join(summary["problems"]) if summary["problems"] else "",
            ]
            for c, text in enumerate(values):
                item = QTableWidgetItem(text)
                if c == 5 and text:
                    item.setForeground(QColor("#B45309"))
                self.summary_table.setItem(r, c, item)
        self.summary_table.resizeColumnsToContents()
        self.summary_table.horizontalHeader().setStretchLastSection(True)

    # ------------------------------------------------------------- step 2
    def _build_step2(self):
        page = QWidget()
        self.step2_layout = QVBoxLayout(page)
        self.step2_layout.setContentsMargins(20, 0, 20, 0)

        intro = QLabel(
            "Confirm which of your registered series each sheet's tag numbers belong "
            "to. A guessed match costs nothing to double-check; a sheet with no obvious "
            "match (like a sheet named after an area code that isn't one of your series "
            "numbers) is left for you to pick, or to leave unmapped.")
        intro.setWordWrap(True)
        self.step2_layout.addWidget(intro)

        self.step2_form_host = QWidget()
        self.step2_form = QFormLayout(self.step2_form_host)
        self.step2_layout.addWidget(self.step2_form_host)
        self.step2_layout.addStretch()
        return page

    def _rebuild_step2(self):
        while self.step2_form.rowCount():
            self.step2_form.removeRow(0)
        self.series_combos = {}
        if not self.summaries:
            return

        sheet_names = [s["sheet_name"] for s in self.summaries]
        guesses = da.guess_master_list_series_mapping(sheet_names)
        all_series = da.list_series()

        for sheet_name in sheet_names:
            combo = QComboBox()
            combo.addItem("— none —", None)
            selected_index = 0
            for i, series_number in enumerate(all_series, start=1):
                combo.addItem(da.series_display_label(series_number), series_number)
                if guesses.get(sheet_name) == series_number:
                    selected_index = i
            combo.setCurrentIndex(selected_index)
            self.series_combos[sheet_name] = combo
            self.step2_form.addRow(sheet_name, combo)

    # ------------------------------------------------------------- step 3
    def _build_step3(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 0, 20, 0)
        self.step3_summary = QLabel()
        self.step3_summary.setWordWrap(True)
        layout.addWidget(self.step3_summary)
        layout.addStretch()
        return page

    def _refresh_step3_summary(self):
        if not self.summaries:
            self.step3_summary.setText("")
            return
        self.sheet_series_map = {
            sheet_name: combo.currentData() for sheet_name, combo in self.series_combos.items()
        }
        total = sum(s["rows_found"] for s in self.summaries)
        trans = sum(s["transmitter"] for s in self.summaries)
        valves = sum(s["valve"] for s in self.summaries)
        oos = sum(s["out_of_scope"] for s in self.summaries)
        lines = [
            f"About to import {total} row(s) across {len(self.summaries)} sheet(s): "
            f"{trans} transmitter(s), {valves} valve(s), {oos} out-of-scope item(s) "
            "(kept, shown collapsed in Coverage).",
            "",
            "Sheet → series:",
        ]
        for sheet_name, series_number in self.sheet_series_map.items():
            target = da.series_display_label(series_number) if series_number is not None else "(unmapped)"
            lines.append(f"  • {sheet_name} → {target}")
        lines.append("")
        lines.append(
            "This only writes master_list.json next to the app. Your Instrumentation "
            "Master List file and your tracker workbook are both untouched.")
        self.step3_summary.setText("\n".join(lines))

    # --------------------------------------------------------- navigation
    def _refresh_step(self):
        index = self.stack.currentIndex()
        self.step_label.setText(self.STEP_TITLES[index])
        self.back_btn.setEnabled(index > 0)
        has_parsed = self.items_by_sheet is not None
        if index == 0:
            self.next_btn.setText("Next →")
            self.next_btn.setEnabled(has_parsed)
        elif index == 1:
            self.next_btn.setText("Next →")
            self.next_btn.setEnabled(True)
        else:
            self.next_btn.setText("Import")
            self.next_btn.setEnabled(True)

    def _go_back(self):
        self.stack.setCurrentIndex(max(0, self.stack.currentIndex() - 1))
        self._refresh_step()

    def _go_next(self):
        index = self.stack.currentIndex()
        if index == 2:
            self._run_import()
            return
        if index == 1:
            self._refresh_step3_summary()
        self.stack.setCurrentIndex(index + 1)
        self._refresh_step()

    def _run_import(self):
        try:
            snapshot, summaries = da.import_master_list(self.file_path, self.sheet_series_map)
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        QMessageBox.information(
            self, "Master list imported",
            f"Imported {len(snapshot['items'])} row(s) from {snapshot['source_file']}.\n\n"
            "Open Coverage from the sidebar to see what's matched, missing, or flagged.")
        self.accept()


class PopulatingWizardDialog(QDialog):
    def __init__(self, parent, main_window):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Populating Wizard")
        self.resize(860, 720)

        self.series_number = None
        self.equip_key = None
        self.etype = None
        self.sticky_fields = set()
        self.template_values = {}
        self.entries_this_session = 0
        self.widgets = {}
        self.checklist_boxes = {}
        self.page_entry = None
        self._pending_draft = da.load_wizard_draft()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QLabel("Populating Wizard")
        header.setObjectName("PageTitle")
        header.setContentsMargins(20, 16, 20, 6)
        outer.addWidget(header)

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, stretch=1)

        self.page_setup = self._build_setup_page()
        self.stack.addWidget(self.page_setup)
        self.stack.setCurrentWidget(self.page_setup)

        if self._pending_draft:
            self._offer_resume_draft()

    # ------------------------------------------------------------ Page 1
    def _build_setup_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 6, 20, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Set up the tag pattern for this batch. Area Code and Tag Type combine "
            "with a sequence you type per item to build the full Tag / Equip # "
            "automatically \u2013 e.g. Area 29103 + Type FIT + Sequence 1011 = "
            "29103-FIT-1011.")
        intro.setObjectName("FieldLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.draft_banner = QLabel("")
        self.draft_banner.setObjectName("SigOk")
        self.draft_banner.setWordWrap(True)
        self.draft_banner.setVisible(False)
        layout.addWidget(self.draft_banner)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        form.setColumnStretch(1, 1)

        form.addWidget(QLabel("Series"), 0, 0)
        self.series_combo = QComboBox()
        for sn in da.list_series():
            self.series_combo.addItem(da.series_display_label(sn), sn)
        form.addWidget(self.series_combo, 0, 1)

        form.addWidget(QLabel("Equipment type"), 1, 0)
        self.equip_combo = QComboBox()
        for key, etype in da.EQUIPMENT_TYPES.items():
            self.equip_combo.addItem(f"{etype['label']}s", key)
        self.equip_combo.currentIndexChanged.connect(self._refresh_system_choices)
        form.addWidget(self.equip_combo, 1, 1)

        area_label = QLabel("Area Code")
        form.addWidget(area_label, 2, 0)
        self.area_edit = QLineEdit("29103")
        form.addWidget(self.area_edit, 2, 1)

        form.addWidget(QLabel("Tag Type"), 3, 0)
        self.type_edit = QLineEdit()
        self.type_edit.setPlaceholderText("Ex. FIT")
        form.addWidget(self.type_edit, 3, 1)

        form.addWidget(QLabel("System"), 4, 0)
        self.system_edit = QComboBox()
        self.system_edit.setEditable(True)
        form.addWidget(self.system_edit, 4, 1)

        layout.addLayout(form)
        layout.addStretch()

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        next_btn = make_button("Next \u2192", "Primary")
        next_btn.clicked.connect(self._go_to_repeat_page)
        footer.addWidget(cancel_btn)
        footer.addWidget(next_btn)
        layout.addLayout(footer)

        self._refresh_system_choices()
        return page

    def _refresh_system_choices(self):
        equip_key = self.equip_combo.currentData()
        etype = da.EQUIPMENT_TYPES[equip_key]
        group_field = etype["group_fields"][0]
        values = set()
        for sn in da.list_series():
            try:
                for r in da.read_index_rows(sn, equip_key):
                    v = str(r.get(group_field) or "").strip()
                    if v:
                        values.add(v)
            except KeyError:
                continue
        current_text = self.system_edit.currentText()
        self.system_edit.clear()
        self.system_edit.addItems(sorted(values))
        self.system_edit.setCurrentText(current_text)

    def _offer_resume_draft(self):
        d = self._pending_draft
        saved_at = d.get("saved_at", "an earlier session")
        n = d.get("entries_this_session", 0)
        self.draft_banner.setText(
            f"\u2713 A saved draft from {saved_at} is available ({n} entr"
            f"{'y' if n == 1 else 'ies'} already added that session) \u2013 "
            f"click \u201cResume Draft\u201d below or just fill in Next normally "
            f"to start a fresh batch instead.")
        self.draft_banner.setVisible(True)
        resume_btn = make_button("Resume Draft", "Success")
        resume_btn.clicked.connect(self._resume_draft)
        discard_btn = make_button("Discard Draft", "Ghost")
        discard_btn.clicked.connect(self._discard_draft)
        row = QHBoxLayout()
        row.addWidget(resume_btn)
        row.addWidget(discard_btn)
        row.addStretch()
        self.page_setup.layout().insertLayout(2, row)

    def _discard_draft(self):
        da.clear_wizard_draft()
        self._pending_draft = None
        self.draft_banner.setVisible(False)

    def _resume_draft(self):
        d = self._pending_draft
        try:
            self.series_number = d["series_number"]
            self.equip_key = d["equip_key"]
            self.etype = da.EQUIPMENT_TYPES[self.equip_key]
        except KeyError:
            QMessageBox.warning(self, "Couldn't resume",
                                 "That draft's series/equipment type no longer exists.")
            return
        idx = self.series_combo.findData(self.series_number)
        if idx >= 0:
            self.series_combo.setCurrentIndex(idx)
        idx = self.equip_combo.findData(self.equip_key)
        if idx >= 0:
            self.equip_combo.setCurrentIndex(idx)
        self.area_edit.setText(d.get("area_code", "29103"))
        self.type_edit.setText(d.get("tag_type", ""))
        self.system_edit.setCurrentText(d.get("system_value", ""))
        self.sticky_fields = set(d.get("sticky_fields", []))
        self.template_values = dict(d.get("template_values", {}))
        self.entries_this_session = d.get("entries_this_session", 0)
        self._resume_entry_values = d.get("current_entry_values", {})
        self._resume_sequence_text = d.get("sequence_text", "")
        self._build_repeat_page()
        self._start_entry_loop(resuming=True)

    # ------------------------------------------------------------ Page 2
    def _go_to_repeat_page(self):
        if not self.type_edit.text().strip():
            QMessageBox.warning(self, "Tag Type needed",
                                 "Enter a Tag Type first (e.g. FIT, PIT, TIT, PV, FV) - "
                                 "it's part of every tag this batch will create.")
            return
        self.series_number = self.series_combo.currentData()
        self.equip_key = self.equip_combo.currentData()
        self.etype = da.EQUIPMENT_TYPES[self.equip_key]
        page = self._build_repeat_page()
        self.stack.setCurrentWidget(page)

    def _build_repeat_page(self):
        if hasattr(self, "page_repeat") and self.page_repeat is not None:
            self.stack.removeWidget(self.page_repeat)
            self.page_repeat.deleteLater()

        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 6, 20, 16)
        layout.setSpacing(8)

        intro = QLabel(
            "Tick any field that should carry the SAME value into every entry this "
            "session (Make, Test Equipment, sign-off name, ...). Leave a field unticked "
            "and it resets to blank after every save - use that for anything that "
            "genuinely changes per item (Serial Number, K-Factor, ...).")
        intro.setObjectName("FieldLabel")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        quick_row = QHBoxLayout()
        check_all_btn = make_button("Check All", "Link")
        uncheck_all_btn = make_button("Uncheck All", "Link")
        defaults_btn = make_button("Use Suggested Defaults", "Link")
        quick_row.addWidget(check_all_btn)
        quick_row.addWidget(uncheck_all_btn)
        quick_row.addWidget(defaults_btn)
        quick_row.addStretch()
        layout.addLayout(quick_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        schema = self.etype["schema"]
        key_field = self.etype["key_field"]
        titles = dict(schema.SECTION_TITLES)
        sections = list(dict.fromkeys(f["section"] for f in schema.LOG_COLUMNS))
        self.checklist_boxes = {}
        defaults = WIZARD_DEFAULT_STICKY.get(self.equip_key, set())
        for section in sections:
            fields_here = [f for f in schema.LOG_COLUMNS if f["section"] == section
                            and f["id"] not in ("export_flag", "yanda_qa_signature", key_field)]
            if not fields_here:
                continue
            box = QGroupBox(titles.get(section, section.title()))
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(4)
            for row, field in enumerate(fields_here):
                cb = QCheckBox(field["label"])
                cb.setChecked(field["id"] in (self.sticky_fields or defaults))
                self.checklist_boxes[field["id"]] = cb
                grid.addWidget(cb, row // 2, row % 2)
            inner_layout.addWidget(box)
        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, stretch=1)

        check_all_btn.clicked.connect(lambda: [cb.setChecked(True) for cb in self.checklist_boxes.values()])
        uncheck_all_btn.clicked.connect(lambda: [cb.setChecked(False) for cb in self.checklist_boxes.values()])
        defaults_btn.clicked.connect(
            lambda: [cb.setChecked(fid in defaults) for fid, cb in self.checklist_boxes.items()])

        footer = QHBoxLayout()
        back_btn = make_button("\u2190 Back", "Ghost")
        back_btn.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_setup))
        footer.addWidget(back_btn)
        footer.addStretch()
        cancel_btn = make_button("Cancel", "Ghost")
        cancel_btn.clicked.connect(self.reject)
        next_btn = make_button("Next \u2192 Start Entering", "Primary")
        next_btn.clicked.connect(self._go_to_entry_page)
        footer.addWidget(cancel_btn)
        footer.addWidget(next_btn)
        layout.addLayout(footer)

        self.page_repeat = page
        self.stack.addWidget(page)
        return page

    # ------------------------------------------------------------ Page 3
    def _go_to_entry_page(self):
        self.sticky_fields = {fid for fid, cb in self.checklist_boxes.items() if cb.isChecked()}
        self._start_entry_loop()

    def _start_entry_loop(self, resuming=False):
        page = self._build_entry_page()
        self.stack.setCurrentWidget(page)
        if resuming:
            for fid, value in getattr(self, "_resume_entry_values", {}).items():
                w = self.widgets.get(fid)
                if w is not None:
                    self._set_widget_value(w, value)
            self.sequence_edit.setText(getattr(self, "_resume_sequence_text", ""))
        else:
            self._reset_entry_form(first_time=True)
        self._update_tag_preview()

    def _build_entry_page(self):
        if self.page_entry is not None:
            self.stack.removeWidget(self.page_entry)
            self.page_entry.deleteLater()

        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QFrame()
        top.setObjectName("Card")
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(6)

        self.count_label = QLabel(f"Entries added this session: {self.entries_this_session}")
        self.count_label.setObjectName("SectionLabel")
        top_layout.addWidget(self.count_label)

        seq_row = QHBoxLayout()
        seq_row.addWidget(QLabel("Sequence"))
        self.sequence_edit = QLineEdit()
        self.sequence_edit.setPlaceholderText("e.g. 1011, 1200, 1070J")
        self.sequence_edit.textChanged.connect(self._update_tag_preview)
        seq_row.addWidget(self.sequence_edit)
        self.tag_preview_label = QLabel("Tag: \u2013")
        self.tag_preview_label.setStyleSheet("font-weight: 700;")
        seq_row.addWidget(self.tag_preview_label)
        seq_row.addStretch()
        top_layout.addLayout(seq_row)
        outer.addWidget(top)

        nav_row = QHBoxLayout()
        nav_row.setContentsMargins(16, 8, 16, 4)
        nav_row.addWidget(QLabel("Jump to:"))
        section_picker = QComboBox()
        nav_row.addWidget(section_picker)
        nav_row.addStretch()
        outer.addLayout(nav_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)
        inner_layout.setContentsMargins(16, 4, 16, 12)
        inner_layout.setSpacing(12)

        schema = self.etype["schema"]
        key_field = self.etype["key_field"]
        titles = dict(schema.SECTION_TITLES)
        sections = list(dict.fromkeys(f["section"] for f in schema.LOG_COLUMNS))
        self.widgets = {}
        section_boxes = {}
        for section in sections:
            fields_here = [f for f in schema.LOG_COLUMNS if f["section"] == section
                            and f["id"] not in ("export_flag", "yanda_qa_signature")]
            if not fields_here:
                continue
            box = QGroupBox(titles.get(section, section.title()))
            grid = QGridLayout(box)
            grid.setHorizontalSpacing(14)
            grid.setVerticalSpacing(8)
            grid.setColumnStretch(1, 1)
            grid.setColumnStretch(3, 1)
            row = 0
            col_pair = 0
            for field in fields_here:
                widget = make_field_widget(field, "")
                self.widgets[field["id"]] = widget
                is_key = field["id"] == key_field
                is_sticky = field["id"] in self.sticky_fields
                suffix = "  (auto from Sequence)" if is_key else ("  \u21bb repeats" if is_sticky else "")
                label = QLabel(field["label"] + suffix)
                label.setObjectName("RequiredLabel" if is_key else "FieldLabel")
                label.setWordWrap(True)
                if is_key:
                    widget.setReadOnly(True) if hasattr(widget, "setReadOnly") else None

                if field["ftype"] == "multiline":
                    if col_pair != 0:
                        row += 1
                        col_pair = 0
                    grid.addWidget(label, row, 0, 1, 4)
                    row += 1
                    grid.addWidget(widget, row, 0, 1, 4)
                    row += 1
                else:
                    base_col = col_pair * 2
                    grid.addWidget(label, row, base_col)
                    grid.addWidget(widget, row, base_col + 1)
                    col_pair = 0 if col_pair else 1
                    if col_pair == 0:
                        row += 1
            inner_layout.addWidget(box)
            section_boxes[section] = box
            section_picker.addItem(titles.get(section, section.title()), section)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        outer.addWidget(scroll, stretch=1)

        def jump(index):
            sec = section_picker.itemData(index)
            b = section_boxes.get(sec)
            if b:
                scroll.ensureWidgetVisible(b, ymargin=10)
        section_picker.currentIndexChanged.connect(jump)

        footer = QFrame()
        footer.setObjectName("Card")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 10, 16, 10)
        template_btn = make_button("\u2190 Edit Template", "Ghost")
        template_btn.setToolTip("Go back and change which fields repeat")
        template_btn.clicked.connect(self._edit_template)
        draft_btn = make_button("Save as Draft && Close", "Ghost")
        draft_btn.clicked.connect(self._save_draft_and_close)
        stop_btn = make_button("Stop", "Danger")
        stop_btn.clicked.connect(self.reject)
        save_next_btn = make_button("Save && Next", "Success")
        save_next_btn.clicked.connect(self._save_and_next)
        footer_layout.addWidget(template_btn)
        footer_layout.addWidget(draft_btn)
        footer_layout.addStretch()
        footer_layout.addWidget(stop_btn)
        footer_layout.addWidget(save_next_btn)
        outer.addWidget(footer)

        self.page_entry = page
        self.stack.addWidget(page)
        return page

    def _key_field(self):
        return self.etype["key_field"]

    def _compose_tag(self, sequence_text):
        area = self.area_edit.text().strip() or "29103"
        ttype = self.type_edit.text().strip().upper()
        seq = sequence_text.strip()
        if not ttype or not seq:
            return ""
        return f"{area}-{ttype}-{seq}"

    def _update_tag_preview(self):
        tag = self._compose_tag(self.sequence_edit.text())
        self.tag_preview_label.setText(f"Tag: {tag}" if tag else "Tag: (enter a sequence)")
        key_widget = self.widgets.get(self._key_field())
        if key_widget is not None:
            self._set_widget_value(key_widget, tag)

    def _set_widget_value(self, widget, value):
        if isinstance(widget, QComboBox):
            texts = [widget.itemText(i) for i in range(widget.count())]
            if value in texts:
                widget.setCurrentText(value)
            else:
                widget.setCurrentIndex(-1)
        elif isinstance(widget, QTextEdit):
            widget.setPlainText(value)
        else:
            widget.setText(value)

    def _reset_entry_form(self, first_time=False):
        for fid, w in self.widgets.items():
            if fid == self._key_field():
                continue
            if fid in self.sticky_fields:
                value = self.template_values.get(fid, "")
            else:
                value = ""
            self._set_widget_value(w, value)
        # System is a wizard-level input (page 1), applied to whichever field
        # the schema uses for it (system_number / system) the first time only,
        # so it's there to start with even before anything's been saved yet.
        if first_time:
            group_field = self.etype["group_fields"][0]
            gw = self.widgets.get(group_field)
            sys_value = self.system_edit.currentText().strip()
            if gw is not None and sys_value:
                self._set_widget_value(gw, sys_value)
                self.template_values.setdefault(group_field, sys_value)
                self.sticky_fields.add(group_field)
        self.sequence_edit.clear()
        self._update_tag_preview()
        self.sequence_edit.setFocus()

    def _save_and_next(self):
        values = {fid: read_field_widget(w) for fid, w in self.widgets.items()}
        key_field = self._key_field()
        key_value = values.get(key_field, "").strip()
        if not key_value:
            QMessageBox.warning(self, "Missing Tag/Equip #",
                                 "Type a sequence above so the Tag/Equip # can be built.")
            return
        dup_row = da.find_duplicate_row(self.series_number, self.equip_key, key_value)
        if dup_row is not None:
            QMessageBox.warning(self, "Duplicate",
                                 f'"{key_value}" is already used on row {dup_row}.')
            return
        row_num = da.find_first_blank_row(self.series_number, self.equip_key)
        try:
            da.save_row(self.series_number, self.equip_key, row_num, values)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save", str(exc))
            return

        for fid in self.sticky_fields:
            if fid in values:
                self.template_values[fid] = values[fid]

        self.entries_this_session += 1
        self.count_label.setText(f"Entries added this session: {self.entries_this_session}")
        self.main_window.statusBar().showMessage(
            f"Wizard saved row {row_num} ({key_value})", 3000)
        self.main_window.refresh_sidebar_and_dashboard()
        self._reset_entry_form()

    def _entry_form_has_content(self):
        return any(read_field_widget(w).strip() for fid, w in self.widgets.items()
                   if fid != self._key_field()) or self.sequence_edit.text().strip()

    def _edit_template(self):
        if self._entry_form_has_content():
            reply = QMessageBox.question(
                self, "Edit template",
                "Going back to change which fields repeat will clear whatever's typed "
                "in the current (unsaved) entry. Continue?")
            if reply != QMessageBox.Yes:
                return
        page = self._build_repeat_page()
        self.stack.setCurrentWidget(page)

    def _save_draft_and_close(self):
        current_values = {fid: read_field_widget(w) for fid, w in self.widgets.items()}
        draft = {
            "series_number": self.series_number,
            "equip_key": self.equip_key,
            "area_code": self.area_edit.text(),
            "tag_type": self.type_edit.text(),
            "system_value": self.system_edit.currentText(),
            "sticky_fields": sorted(self.sticky_fields),
            "template_values": self.template_values,
            "current_entry_values": current_values,
            "sequence_text": self.sequence_edit.text(),
            "entries_this_session": self.entries_this_session,
            "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        try:
            da.save_wizard_draft(draft)
        except Exception as exc:
            QMessageBox.critical(self, "Couldn't save draft", str(exc))
            return
        QMessageBox.information(
            self, "Draft saved",
            f"{self.entries_this_session} entr{'y' if self.entries_this_session == 1 else 'ies'} "
            "already saved this session stay in the workbook as-is. This batch's setup and "
            "the entry you were partway through are saved as ONE resumable draft - reopen the "
            "Populating Wizard any time to pick up where you left off. Saving another draft "
            "later will overwrite this one.")
        self.accept()

    def reject(self):
        if self.stack.currentWidget() is self.page_entry and self._entry_form_has_content():
            reply = QMessageBox.question(
                self, "Stop the wizard?",
                f"{self.entries_this_session} entr{'y' if self.entries_this_session == 1 else 'ies'} "
                "already saved this session will stay in the workbook. Anything currently "
                "typed in this unsaved entry will be lost unless you use \u201cSave as Draft\u201d "
                "instead. Stop anyway?")
            if reply != QMessageBox.Yes:
                return
        super().reject()


def main():
    app = QApplication(sys.argv)
    theme = da.get_setting("theme") or "light"
    app.setStyleSheet(DARK_QSS if theme == "dark" else LIGHT_QSS)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
