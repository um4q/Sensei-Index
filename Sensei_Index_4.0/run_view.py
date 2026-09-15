# -*- coding: utf-8 -*-
"""
The Run view - Sensei Index 4.0's primary screen.

One flat, cross-series, cross-equipment-type worklist instead of navigating
series-by-series and type-by-type through the sidebar (that Index view is
still there, still fully working, for anyone who wants the old per-series
Excel-style grid). Built from the "Sensei Index 4.0 - The Run" design:
keyboard-first (arrow keys move, Space advances a stage, A accepts, E
queues for export, F toggles Field mode, / jumps to search), a live check
column, and a permanent, stamped journal of every change.

Every write goes through data_access.py exactly the way the Index view's
writes do (da.set_run_stage / da.set_status), so the two views can never
disagree about what "Submitted" means. Every change here is ALSO recorded
through the app's normal Ctrl+Z UndoManager (main_window.undo_stack) - Run
doesn't invent a second undo system, it just also appends a permanent,
human-readable line to the Run journal (da.append_journal) alongside it,
since the workbook itself has no memory of *when* a status changed or
*who* changed it, only what it currently is.

Accessibility (from the "Accessible Redesign" mockup): stage is always
shown as a word, never color alone; every icon-only control gets an
accessible name that includes the control's own current state, not just
a generic label; the row a screen reader focuses on reads back
"<tag>, <stage>, <check or 'no flags'>" as one sentence via
Qt.AccessibleTextRole, not three separate unlabeled cells.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QButtonGroup, QSplitter, QListWidget, QListWidgetItem, QFrame,
    QSizePolicy,
)

import data_access as da

STAGE_WORDS = da.STAGE_WORDS  # ["Not started", "Installed", "Submitted", "Accepted"]

BOARDS = [
    ("run", "Everything", lambda rows: rows),
    ("install", "Needs install", lambda rows: [r for r in rows if r["stage"] == 0]),
    ("submit", "Ready to submit", lambda rows: [r for r in rows if r["stage"] == 1]),
    ("accept", "Awaiting client", lambda rows: [r for r in rows if r["stage"] == 2]),
    ("flagged", "Flagged", lambda rows: [r for r in rows if r["flag"]]),
]

STAGE_FILL_COLOR = "#1d2d3d"
STAGE_EMPTY_COLOR = "#d4d4d7"
FLAG_COLOR = "#c0392b"
ACCEPT_ROW_TINT = QColor("#eaf6ee")


def _row_key(entry):
    return (entry["series_number"], entry["equip_key"], entry["key_value"])


class StageWidget(QWidget):
    """Three small blocks + the stage word, never color alone - a filled
    block also gets a check-mark glyph so the state doesn't depend on
    seeing the color at all. Click advances one stage (mouse affordance);
    keyboard users select the row and press Space/Shift+Space instead."""

    def __init__(self, entry, on_click):
        super().__init__()
        self._entry = entry
        self._on_click = on_click
        self.setCursor(Qt.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)

        self._blocks = []
        for i in range(3):
            block = QLabel("✓" if entry["stage"] > i else "")
            block.setFixedSize(20, 16)
            block.setAlignment(Qt.AlignCenter)
            filled = entry["stage"] > i
            block.setStyleSheet(
                f"background:{STAGE_FILL_COLOR if filled else STAGE_EMPTY_COLOR};"
                f"color:#fff;font-weight:700;font-size:10px;"
            )
            layout.addWidget(block)
            self._blocks.append(block)

        word = QLabel(STAGE_WORDS[entry["stage"]])
        word.setObjectName("FieldLabel")
        layout.addWidget(word)
        layout.addStretch()

        self.setAccessibleName(f"{entry['key_value']}, stage: {STAGE_WORDS[entry['stage']]}")
        self.setToolTip("Click to advance a stage (or select the row and press Space)")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._on_click(self._entry)
        super().mousePressEvent(event)


class RunTable(QTableWidget):
    """Plain arrow-key row navigation comes free from QAbstractItemView -
    this only intercepts the keys native navigation doesn't cover: Space /
    Shift+Space to advance/step back a stage, A to accept outright, E to
    toggle the export queue, matching the footer legend one-for-one."""

    def __init__(self, *args, run_view=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.run_view = run_view

    def keyPressEvent(self, event):
        rv = self.run_view
        key = event.key()
        if rv is not None:
            if key == Qt.Key_Space:
                rv.advance(-1 if event.modifiers() & Qt.ShiftModifier else 1)
                return
            if key == Qt.Key_A and not event.modifiers():
                rv.accept_current()
                return
            if key == Qt.Key_E and not event.modifiers():
                rv.toggle_queue()
                return
            if key == Qt.Key_F and not event.modifiers():
                rv.toggle_field_mode()
                return
            if event.text() == "/":
                rv.focus_search()
                return
        super().keyPressEvent(event)


class RunView(QWidget):
    COLUMNS = ["#", "Tag / Equip #", "Description", "Stage", "Check"]

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.all_rows = []
        self.filtered_rows = []
        self.board = "run"
        self.cursor_key = None
        self.field_mode = bool(da.get_setting("run_field_mode"))

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.apply_filter)

        outer = QVBoxLayout(self)
        outer.setSpacing(10)
        outer.addLayout(self._build_header())
        outer.addLayout(self._build_board_bar())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_table())
        self.journal_panel = self._build_journal_panel()
        splitter.addWidget(self.journal_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([1000, 320])
        outer.addWidget(splitter, stretch=1)

        outer.addLayout(self._build_footer())

        self.reload()
        self.search_edit.setFocus()

    # ------------------------------------------------------------- header
    def _build_header(self):
        row = QHBoxLayout()
        title = QLabel("The Run")
        title.setObjectName("PageTitle")
        row.addWidget(title)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Type a tag, service, or series to filter…")
        self.search_edit.setAccessibleName("Search the run list")
        self.search_edit.setToolTip("Filters as you type (/ to jump here)")
        self.search_edit.textChanged.connect(lambda _: self._debounce.start())
        row.addWidget(self.search_edit, stretch=1)

        self.field_btn = make_toggle_button("")
        self.field_btn.clicked.connect(self.toggle_field_mode)
        row.addWidget(self.field_btn)

        self.journal_btn = make_toggle_button("")
        self.journal_btn.clicked.connect(self.toggle_journal)
        row.addWidget(self.journal_btn)

        self._refresh_toggle_labels()
        return row

    def _refresh_toggle_labels(self):
        field_label = f"Field mode: {'on' if self.field_mode else 'off'}"
        self.field_btn.setText(field_label)
        self.field_btn.setAccessibleName(field_label + " (F)")
        n = len(da.read_journal())
        journal_label = f"Journal · {n}" if n else "Journal"
        self.journal_btn.setText(journal_label)
        self.journal_btn.setAccessibleName(journal_label + ", toggle panel")

    # ----------------------------------------------------------- board bar
    def _build_board_bar(self):
        row = QHBoxLayout()
        self._board_buttons = {}
        group = QButtonGroup(self)
        group.setExclusive(True)
        for board_id, label, _ in BOARDS:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(board_id == self.board)
            btn.setStyleSheet(BOARD_BTN_QSS)
            btn.clicked.connect(lambda _checked, b=board_id: self._select_board(b))
            group.addButton(btn)
            row.addWidget(btn)
            self._board_buttons[board_id] = btn
        row.addStretch()
        self.shown_label = QLabel("")
        self.shown_label.setObjectName("FieldLabel")
        row.addWidget(self.shown_label)
        return row

    def _select_board(self, board_id):
        self.board = board_id
        self.apply_filter()

    # -------------------------------------------------------------- table
    def _build_table(self):
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = RunTable(0, len(self.COLUMNS), run_view=self)
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 190)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self.table.setColumnWidth(3, 170)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(4, 190)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda _i: self.advance(1))
        layout.addWidget(self.table)
        return wrap

    # ------------------------------------------------------------ journal
    def _build_journal_panel(self):
        panel = QFrame()
        panel.setObjectName("Card")
        layout = QVBoxLayout(panel)

        heading = QLabel("JOURNAL — APPEND ONLY")
        heading.setObjectName("SectionLabel")
        layout.addWidget(heading)
        blurb = QLabel("Every change is written here first, stamped and permanent. "
                        "Undoing a change adds a new line rather than erasing the old one.")
        blurb.setObjectName("FieldLabel")
        blurb.setWordWrap(True)
        layout.addWidget(blurb)

        self.journal_list = QListWidget()
        self.journal_list.setAccessibleName("Run journal, most recent change first")
        self.journal_list.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self.journal_list, stretch=1)

        undo_row = QHBoxLayout()
        undo_btn = make_button("Undo last", "Ghost")
        undo_btn.setAccessibleName("Undo last change (Ctrl+Z)")
        undo_btn.clicked.connect(self.main_window.undo_action)
        undo_row.addWidget(undo_btn)
        layout.addLayout(undo_row)
        return panel

    def _reload_journal_panel(self):
        self.journal_list.clear()
        entries = da.read_journal(limit=60)
        if not entries:
            item = QListWidgetItem("Nothing yet this run. Advance a stage and it lands here.")
            item.setFlags(Qt.NoItemFlags)
            self.journal_list.addItem(item)
            return
        for e in entries:
            text = f"{e['time']}   {e['tag']} — {e['what']}\n{e['who']}"
            item = QListWidgetItem(text)
            item.setFlags(Qt.NoItemFlags)
            self.journal_list.addItem(item)

    def toggle_journal(self):
        self.journal_panel.setVisible(not self.journal_panel.isVisible())

    # -------------------------------------------------------------- footer
    def _build_footer(self):
        row = QHBoxLayout()

        def legend(key, text):
            lbl = QLabel(f"<b>{key}</b> {text}")
            lbl.setObjectName("FieldLabel")
            lbl.setTextFormat(Qt.RichText)
            return lbl

        for key, text in [
            ("↑ ↓", "move"), ("Space", "advance stage"),
            ("Shift+Space", "step back"), ("A", "accept"), ("E", "toggle export queue"),
            ("Ctrl+Z", "undo"), ("/", "search"), ("F", "field mode"),
        ]:
            row.addWidget(legend(key, text))
        row.addStretch()
        self.status_line = QLabel("")
        self.status_line.setObjectName("FieldLabel")
        row.addWidget(self.status_line)
        return row

    # ---------------------------------------------------------------- data
    def reload(self):
        try:
            self.all_rows = da.read_run_rows()
        except Exception as exc:
            self.main_window.statusBar().showMessage(f"Couldn't read the workbook: {exc}", 6000)
            self.all_rows = []
        self.apply_filter()
        self._reload_journal_panel()
        self._refresh_toggle_labels()

    def apply_filter(self):
        board_filter = next(f for bid, _lbl, f in BOARDS if bid == self.board)
        rows = board_filter(self.all_rows)

        query = self.search_edit.text().strip().lower()
        if query:
            terms = query.split()
            def matches(r):
                hay = f"{r['key_value']} {r['desc']} {r['kind']} {r['series_label']}".lower()
                return all(t in hay for t in terms)
            rows = [r for r in rows if matches(r)]

        self.filtered_rows = rows
        self._render_rows()
        self.shown_label.setText(f"{len(rows)} of {len(self.all_rows)} shown")
        for board_id, _label, f in BOARDS:
            count = len(f(self.all_rows))
            self._board_buttons[board_id].setText(f"{dict((b, l) for b, l, _ in BOARDS)[board_id]}  {count}")

    def _render_rows(self):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for i, entry in enumerate(self.filtered_rows):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, 54 if self.field_mode else 34)

            num_item = QTableWidgetItem(str(i + 1))
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            num_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, num_item)

            tag_item = QTableWidgetItem(f"{entry['key_value']}\n{entry['equip_label']} · {entry['series_label']}")
            tag_item.setFlags(tag_item.flags() & ~Qt.ItemIsEditable)
            accessible_text = (f"{entry['key_value']}, {STAGE_WORDS[entry['stage']]}, "
                                f"{entry['flag'] or 'no flags'}")
            tag_item.setData(Qt.AccessibleTextRole, accessible_text)
            if self.field_mode:
                f = tag_item.font()
                f.setPointSize(f.pointSize() + 2)
                tag_item.setFont(f)
            self.table.setItem(r, 1, tag_item)

            desc_item = QTableWidgetItem(f"{entry['desc']}\n{entry['kind']}")
            desc_item.setFlags(desc_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(r, 2, desc_item)

            stage_widget = StageWidget(entry, self._advance_entry)
            self.table.setCellWidget(r, 3, stage_widget)

            flag_item = QTableWidgetItem(entry["flag"] or "—")
            flag_item.setFlags(flag_item.flags() & ~Qt.ItemIsEditable)
            if entry["flag"]:
                flag_item.setForeground(QColor(FLAG_COLOR))
            self.table.setItem(r, 4, flag_item)

            if entry["stage"] == 3:
                for c in range(len(self.COLUMNS)):
                    item = self.table.item(r, c)
                    if item is not None:
                        item.setBackground(ACCEPT_ROW_TINT)

        self.table.resizeRowsToContents()
        if self.field_mode:
            for r in range(self.table.rowCount()):
                self.table.setRowHeight(r, max(54, self.table.rowHeight(r)))
        self.table.blockSignals(False)
        self._restore_cursor()

    def _restore_cursor(self):
        if not self.filtered_rows:
            self.status_line.setText("Nothing matches that")
            return
        target = 0
        if self.cursor_key is not None:
            for i, e in enumerate(self.filtered_rows):
                if _row_key(e) == self.cursor_key:
                    target = i
                    break
        self.table.selectRow(target)
        self.table.setCurrentCell(target, 1)

    def _on_selection_changed(self):
        entry = self.current_entry()
        if entry is None:
            return
        self.cursor_key = _row_key(entry)
        self.status_line.setText(f"{entry['key_value']} — {STAGE_WORDS[entry['stage']]}")

    def current_entry(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        idx = rows[0].row()
        if idx < 0 or idx >= len(self.filtered_rows):
            return None
        return self.filtered_rows[idx]

    # -------------------------------------------------------------- writes
    def advance(self, direction):
        entry = self.current_entry()
        if entry is None:
            return
        self._advance_entry(entry, direction)

    def _advance_entry(self, entry, direction=1):
        new_stage = max(0, min(3, entry["stage"] + direction))
        if new_stage == entry["stage"]:
            return
        self._apply_stage(entry, new_stage,
                           verb="marked" if direction > 0 else "stepped back to")

    def accept_current(self):
        entry = self.current_entry()
        if entry is None or entry["stage"] == 3:
            return
        self._apply_stage(entry, 3, verb="marked")

    def _apply_stage(self, entry, new_stage, verb):
        sn, ek, kv = entry["series_number"], entry["equip_key"], entry["key_value"]
        old_stage = entry["stage"]
        try:
            da.set_run_stage(sn, ek, kv, new_stage)
        except Exception as exc:
            self.main_window.statusBar().showMessage(f"Couldn't save: {exc}", 5000)
            return
        da.append_journal(kv, f"{verb} {STAGE_WORDS[new_stage].lower()}")
        self._record_stage_undo(sn, ek, kv, old_stage, new_stage)
        self.cursor_key = (sn, ek, kv)
        self.main_window.statusBar().showMessage(
            f"{kv} — {STAGE_WORDS[new_stage]}", 2500)
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()

    def _record_stage_undo(self, sn, ek, kv, old_stage, new_stage):
        mw = self.main_window

        def do_undo():
            da.set_run_stage(sn, ek, kv, old_stage)
            da.append_journal(kv, f"reverted to {STAGE_WORDS[old_stage].lower()} (undo)")
            mw.refresh_current_view()

        def do_redo():
            da.set_run_stage(sn, ek, kv, new_stage)
            da.append_journal(kv, f"marked {STAGE_WORDS[new_stage].lower()} (redo)")
            mw.refresh_current_view()

        mw.undo_stack.push(f"{STAGE_WORDS[new_stage]} – {kv}", do_undo, do_redo)

    def toggle_queue(self):
        entry = self.current_entry()
        if entry is None:
            return
        sn, ek, kv = entry["series_number"], entry["equip_key"], entry["key_value"]
        new_val = not entry["queued"]
        try:
            da.set_status(sn, ek, kv, export=new_val)
        except Exception as exc:
            self.main_window.statusBar().showMessage(f"Couldn't save: {exc}", 5000)
            return
        da.append_journal(kv, "queued for export" if new_val else "removed from export queue")
        mw = self.main_window

        def do_undo():
            da.set_status(sn, ek, kv, export=not new_val)
            mw.refresh_current_view()

        def do_redo():
            da.set_status(sn, ek, kv, export=new_val)
            mw.refresh_current_view()

        mw.undo_stack.push(f"Export queue – {kv}", do_undo, do_redo)
        self.cursor_key = (sn, ek, kv)
        self.reload()

    # ------------------------------------------------------------- toggles
    def toggle_field_mode(self):
        self.field_mode = not self.field_mode
        da.set_setting("run_field_mode", self.field_mode)
        self._refresh_toggle_labels()
        self._render_rows()

    def focus_search(self):
        self.search_edit.setFocus()
        self.search_edit.selectAll()


BOARD_BTN_QSS = """
QPushButton {
    border: 0; padding: 8px 14px; background: #fff; color: #1d1f20;
    font: 500 13px "Barlow", sans-serif;
}
QPushButton:checked {
    background: #1d2d3d; color: #fff; font-weight: 600;
}
QPushButton:hover:!checked { background: #eef2f6; }
"""


def make_toggle_button(text):
    btn = QPushButton(text)
    btn.setStyleSheet(
        "QPushButton { border: 1px solid rgba(0,0,0,.25); background: transparent; "
        "padding: 7px 12px; } QPushButton:hover { background: rgba(0,0,0,.06); }"
    )
    return btn


# gui_app.make_button isn't imported to avoid a circular import (gui_app
# imports this module) - this is the same tiny helper, kept in lockstep on
# purpose rather than restructured into a shared module for one function.
def make_button(text, object_name=None):
    btn = QPushButton(text)
    if object_name:
        btn.setObjectName(object_name)
    return btn
