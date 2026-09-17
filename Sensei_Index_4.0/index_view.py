# -*- coding: utf-8 -*-
"""
The engineering-grade instrument index - plate 6a of the redesign brief,
"rebuilt, not patched": survey-density table with a two-row grouped
header (identity/process/device/calibration/installation/documents/
progress), monospaced identifiers, row banding every 5th row, document-
state chips, and an exception-counting toolbar, plus the free-text search,
system legend and selection bar from plate 1b underneath it. (Plate 1b's
separate exact-match filter chips were never built - the free-text search
below covers the same "narrow the table down" need day to day; adding real
chips on top of it is still open, tracked separately from this file.)

This REPLACES IndexPage as the series+equipment-type table. It doesn't
reimplement Add/Edit, Export, or the row-detail view - those still open
through MainWindow's existing dialogs (edit_row / view_row / export_rows
/ etc.), passed in as callables so this module never imports gui_app and
gui_app can import this one without a cycle.
"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QSizePolicy, QInputDialog,
)

import data_access as da
import theme

DENSITIES = {
    "Survey": {"row_h": 22, "font_pt": 9},
    "Standard": {"row_h": 30, "font_pt": 10},
    "Comfortable": {"row_h": 40, "font_pt": 11},
}

STAGE_WORDS = ["Not started", "Installed", "Submitted", "Accepted"]

# (label, group, width, kind) - kind picks the renderer: 'mono' identifiers,
# 'text' plain, 'range' right-aligned w/ unit, 'stage' the 3-seg+word
# widget, 'doc' the IFC/IFR/ECN/SUP chip. Service/System are Stretch-resized
# (see _build_table) rather than fixed, so they absorb extra width instead
# of every column just running the total further past the viewport.
COLUMNS = [
    ("Tag", "IDENTITY", 150, "mono"),
    ("Loop ID", "IDENTITY", 80, "mono"),
    ("Service", "IDENTITY", 170, "text"),
    ("System", "PROCESS", 130, "text"),
    ("P&ID (Rev)", "PROCESS", 120, "mono"),
    ("Line #", "PROCESS", 120, "mono"),
    ("Make", "DEVICE", 100, "text"),
    ("Model", "DEVICE", 130, "text"),
    ("Serial #", "DEVICE", 110, "mono"),
    ("Cal. Range", "CALIBRATION", 110, "range"),
    ("Inst. Range", "CALIBRATION", 110, "range"),
    ("Cal. Due", "CALIBRATION", 90, "text"),
    ("Hook-up Dwg", "INSTALLATION", 100, "mono"),
    ("JB / Cable", "INSTALLATION", 100, "mono"),
    ("Loop Dwg", "INSTALLATION", 90, "mono"),
    ("DS Rev", "DOCUMENTS", 60, "text"),
    ("ECN", "DOCUMENTS", 90, "ecn"),
    ("Doc", "DOCUMENTS", 60, "doc"),
    ("Stage", "PROGRESS", 150, "stage"),
    ("QA Date", "PROGRESS", 90, "text"),
]
# Columns wide enough, and read often enough, to be worth the space Stretch
# reclaims from the fixed-width trims above - stretched columns still have
# the width numbers in COLUMNS above as their genuine minimum.
STRETCH_COLUMNS = {"Service", "System"}

# The index table (header, row gutter, stage/doc/ecn chips, legend swatches)
# is a deliberate light-surface exception to the active theme, same as
# theme.py's own QTableWidget#IndexTable QSS rule (background/text/zebra
# all pinned to LIGHT regardless of app theme) - see that rule's comment
# for why. Everything below sources its colors from theme.LIGHT for the
# same reason, instead of the hardcoded hex literals this used to carry
# (which happened to already equal these same LIGHT values, just with no
# single source of truth and no story for why - GUI audit Part 3 #17-19).
_C = theme.LIGHT

GROUP_COLORS = {
    "IDENTITY": _C["highlight"], "PROCESS": _C["group_alt"], "DEVICE": _C["group_alt"],
    "CALIBRATION": _C["highlight"], "INSTALLATION": _C["group_alt"], "DOCUMENTS": _C["highlight"],
    "PROGRESS": _C["group_alt"],
}
GROUP_TEXT = {"IDENTITY": _C["navy"], "CALIBRATION": _C["navy"], "DOCUMENTS": _C["navy"]}
# The header's own hairline column divider and unlabeled-group backdrop -
# not one of theme.py's named tokens (nothing else needs this exact light
# gray), so it stays a local constant rather than inventing a token for a
# single use.
HEADER_DIVIDER = QColor(210, 210, 212)
HEADER_COL_BG = QColor(_C["chrome"])
# The legend's swatch rotation - three of its four stops are named theme
# tokens; this one is a legend-only mid-blue with no other use in the app,
# so it isn't worth inventing a theme.py token for just this one spot.
LEGEND_EXTRA_BLUE = "#749dc4"

ROW_NUM_COL = 0  # inserted before COLUMNS at render time


class GroupedHeaderView(QHeaderView):
    """A two-row header painted in one taller section: a colored group
    band on top (spanning visually - neighbouring same-group columns
    share the color so it reads as one merged block even though nothing
    is literally spanned), the plain column label underneath. All drawn
    from the header's own section geometry, so it never drifts out of
    sync with resizing or scrolling the way a separately-laid-out strip
    of widgets would."""

    GROUP_BAND_H = 18

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setFixedHeight(18 + 26)
        self.setSectionsClickable(True)

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        if logical_index == ROW_NUM_COL:
            group, label = "", "#"
        else:
            label, group, _w, _kind = COLUMNS[logical_index - 1]
        band_color = QColor(GROUP_COLORS.get(group, HEADER_COL_BG))
        text_color = QColor(GROUP_TEXT.get(group, _C["body"]))

        band_rect = rect.adjusted(0, 0, 0, -(rect.height() - self.GROUP_BAND_H))
        painter.fillRect(band_rect, band_color)
        col_rect = rect.adjusted(0, self.GROUP_BAND_H, 0, 0)
        painter.fillRect(col_rect, HEADER_COL_BG)

        painter.setPen(HEADER_DIVIDER)
        painter.drawLine(rect.topRight(), rect.bottomRight())

        f = painter.font()
        f.setFamily("Barlow Condensed SemiBold")
        f.setPointSize(9)
        f.setBold(False)
        painter.setFont(f)
        painter.setPen(text_color)
        show_group_label = (logical_index == ROW_NUM_COL) or (
            logical_index == 1 or COLUMNS[logical_index - 2][1] != group)
        if show_group_label and group:
            painter.drawText(band_rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, group)

        f2 = painter.font()
        f2.setPointSize(9)
        painter.setFont(f2)
        painter.setPen(QColor(_C["body"]))
        painter.drawText(col_rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()


class StageCell(QWidget):
    def __init__(self, stage, tag=""):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        for i in range(3):
            block = QLabel()
            block.setFixedSize(24, 8)
            filled = stage > i
            block.setStyleSheet(f"background:{_C['navy'] if filled else _C['track']};")
            layout.addWidget(block)
        word = QLabel(STAGE_WORDS[stage])
        word.setStyleSheet(f"font:400 11.5px 'Barlow';color:{_C['secondary'] if stage == 0 else _C['ink']};")
        layout.addWidget(word)
        layout.addStretch()
        # Screen-reader users landing on this cell need to know which row
        # they're on, not just its stage in isolation (GUI audit Part 3 #5).
        self.setAccessibleName(f"{tag}, {STAGE_WORDS[stage]}" if tag else f"stage: {STAGE_WORDS[stage]}")


DOC_CHIP_OBJECT_NAMES = {
    "IFC": ("DocChipIFC", "Issued for construction"),
    "IFR": ("DocChipIFR", "Issued for review"),
    "ECN": ("DocChipECN", "Change outstanding"),
    "SUP": ("DocChipSUP", "Superseded"),
}


def doc_chip_label(status):
    text = (status or "").strip().upper()
    if text not in DOC_CHIP_OBJECT_NAMES:
        return None
    object_name, tip = DOC_CHIP_OBJECT_NAMES[text]
    lbl = QLabel(text)
    # theme.py already carries QLabel#DocChipIFC/IFR/ECN/SUP QSS rules for
    # exactly this - using them instead of inline hex here means this chip
    # (unlike the rest of this always-light table) actually does follow
    # high-contrast mode's stronger-border/no-zebra treatment, same as any
    # other themed widget (GUI audit Part 3 #22).
    lbl.setObjectName(object_name)
    lbl.setStyleSheet(f"{css}font:600 10px 'Barlow Condensed SemiBold';padding:2px 5px;")
    lbl.setToolTip(tip)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class IndexView(QWidget):
    """main_window only needs to provide: series_display_label(number)
    (already on da), and these callables/attributes on itself:
    add_new_row(sn, ek), edit_row(sn, ek, row), view_row(sn, ek, row),
    open_export_for(sn, ek, filters), remove_rows(sn, ek, row_nums),
    show_index(sn, ek), refresh_sidebar_and_dashboard(), statusBar(),
    undo_stack (an object with .push(description, do_undo, do_redo))."""

    def __init__(self, main_window, series_number, equip_key):
        super().__init__()
        self.main_window = main_window
        self.series_number = series_number
        self.equip_key = equip_key
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.all_rows = []
        self.filtered_rows = []
        self.density = "Survey"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.addLayout(self._build_toolbar())
        outer.addLayout(self._build_filter_row())
        outer.addWidget(self._build_legend())
        outer.addWidget(self._build_table(), stretch=1)
        self.selection_bar = self._build_selection_bar()
        outer.addWidget(self.selection_bar)
        self.selection_bar.hide()
        outer.addLayout(self._build_footer())

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.apply_filter)

        self.reload()

    # ------------------------------------------------------------- header
    def _build_toolbar(self):
        row = QHBoxLayout()
        title = QLabel(da.series_display_label(self.series_number))
        title.setObjectName("PageTitle")
        row.addWidget(title)
        row.addLayout(self._build_equip_type_tabs())
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("PageSubtitle")
        row.addWidget(self.subtitle)
        row.addStretch()

        density_row = QHBoxLayout()
        density_row.setSpacing(0)
        self._density_buttons = {}
        for name in DENSITIES:
            btn = QPushButton(name)
            btn.setObjectName("DensityButton")
            btn.setCheckable(True)
            btn.setChecked(name == self.density)
            btn.clicked.connect(lambda _c, n=name: self._set_density(n))
            self._density_buttons[name] = btn
            density_row.addWidget(btn)
        row.addLayout(density_row)

        add_btn = QPushButton(f"+ Add {self.etype['label'].lower()}")
        add_btn.setObjectName("Primary")
        add_btn.clicked.connect(self.add_new)
        row.addWidget(add_btn)
        export_btn = QPushButton("Export…")
        export_btn.setObjectName("Ghost")
        export_btn.clicked.connect(self.open_export)
        row.addWidget(export_btn)
        return row

    def _build_equip_type_tabs(self):
        """Plate 1b's equipment-type tabs. Each series has two separate
        logs - Transmitters and Valves - and this table only ever shows
        one at a time (self.equip_key), so without this there is no way
        to reach the other one: the series rail's own counts already sum
        both types together (series_full_summary), but its row always
        opens straight into Transmitters."""
        tabs = QHBoxLayout()
        tabs.setContentsMargins(18, 0, 0, 0)
        tabs.setSpacing(0)
        for key, etype in da.EQUIPMENT_TYPES.items():
            label = etype["label"] + "s"
            is_current = key == self.equip_key
            btn = QPushButton(label)
            btn.setObjectName("EquipTab")
            btn.setCheckable(True)
            btn.setChecked(is_current)
            # "active" property (not just :checked) to match theme.py's
            # existing QPushButton#EquipTab[active="true"] rule and the
            # same convention gui_app.py's own RailRow buttons use - fixed
            # for this widget's whole lifetime (switching tabs swaps in a
            # brand new IndexView rather than toggling this one in place),
            # so no unpolish/polish-on-click is needed the way RailRow's
            # own dynamically-changing "active" row does.
            btn.setProperty("active", "true" if is_current else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            if is_current:
                btn.setAccessibleName(f"{label}, showing")
            else:
                btn.setAccessibleName(f"Switch to {label}")
                btn.clicked.connect(
                    lambda _c=False, sn=self.series_number, k=key: self.main_window.show_index(sn, k))
            tabs.addWidget(btn)
        return tabs

    def _set_density(self, name):
        self.density = name
        for n, btn in self._density_buttons.items():
            btn.setChecked(n == name)
        self._render_rows()

    # --------------------------------------------------------- filter row
    def _build_filter_row(self):
        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("FilterSearch")
        self.search_edit.setPlaceholderText(f"⌕ Search tag, loop, service, P&ID")
        self.search_edit.textChanged.connect(lambda _t: self._debounce.start())
        row.addWidget(self.search_edit, stretch=1)
        self.exception_label = QLabel("")
        self.exception_label.setObjectName("FieldLabel")
        row.addWidget(self.exception_label)
        return row

    def _build_legend(self):
        frame = QFrame()
        frame.setObjectName("SystemLegend")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 6, 10, 6)
        kicker = QLabel("SYSTEM")
        kicker.setObjectName("LegendKicker")
        layout.addWidget(kicker)
        self.legend_body = QHBoxLayout()
        layout.addLayout(self.legend_body)
        layout.addStretch()
        note = QLabel("Swatches are assigned per system and the name is always written out beside them")
        note.setObjectName("FieldLabel")
        layout.addWidget(note)
        return frame

    # -------------------------------------------------------------- table
    def _build_table(self):
        self.table = QTableWidget(0, len(COLUMNS) + 1)
        self.table.setObjectName("IndexTable")
        header = GroupedHeaderView(self.table)
        self.table.setHorizontalHeader(header)
        self.table.setHorizontalHeaderLabels(["#"] + [c[0] for c in COLUMNS])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        # QSS supplies the actual color (LIGHT's zebra, always - see
        # theme.py's #IndexTable rule) - this just turns the mechanism on,
        # replacing the old per-cell setBackground(row_bg) calls in
        # _render_rows, which forced a literal color that ignored theme
        # entirely (GUI audit Part 3 #17).
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 34)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        for i, (label, _group, width, _kind) in enumerate(COLUMNS, start=1):
            # Service/System stretch to absorb whatever width is left over
            # instead of every column running further past the viewport
            # (GUI audit Part 3 #25). A Stretch section can't be dragged by
            # hand, unlike the Interactive ones - trading that off is what
            # buys back screen space without a full "manage columns" UI.
            mode = QHeaderView.Stretch if label in STRETCH_COLUMNS else QHeaderView.Interactive
            self.table.horizontalHeader().setSectionResizeMode(i, mode)
            if mode == QHeaderView.Interactive:
                self.table.setColumnWidth(i, width)
        self.table.horizontalHeader().setMinimumSectionSize(60)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda idx: self.edit_row_at(idx.row()))
        return self.table

    def _build_selection_bar(self):
        bar = QFrame()
        bar.setObjectName("SelectionBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        self.selection_count_label = QLabel("")
        self.selection_count_label.setObjectName("SelectionCount")
        layout.addWidget(self.selection_count_label)
        divider = QFrame()
        divider.setFixedWidth(1)
        # A translucent white overlay works over SelectionBar's navy
        # background in every theme (LIGHT and DARK navy are both dark
        # enough), so this one doesn't need a theme.LIGHT token the way the
        # esc_hint text right below does.
        divider.setStyleSheet("background:rgba(255,255,255,.3);")
        layout.addWidget(divider)
        for label, stage in [("Mark installed", 1), ("Mark submitted", 2), ("Mark accepted", 3)]:
            btn = QPushButton(label)
            btn.setObjectName("SelectionAction")
            btn.clicked.connect(lambda _c, s=stage: self.bulk_set_stage(s))
            layout.addWidget(btn)
        date_btn = QPushButton("Set a date…")
        date_btn.setObjectName("SelectionAction")
        date_btn.clicked.connect(self.bulk_set_date)
        layout.addWidget(date_btn)
        queue_btn = QPushButton("Queue for export")
        queue_btn.setObjectName("SelectionPrimary")
        queue_btn.clicked.connect(self.bulk_queue_export)
        layout.addWidget(queue_btn)
        layout.addStretch()
        clear_btn = QPushButton("Clear rows…")
        clear_btn.setObjectName("SelectionDanger")
        clear_btn.clicked.connect(self.remove_selected)
        layout.addWidget(clear_btn)
        esc_hint = QLabel("Esc to deselect")
        esc_hint.setStyleSheet(f"color:{_C['light_blue']};font-size:12.5px;")
        layout.addWidget(esc_hint)
        return bar

    def _build_footer(self):
        row = QHBoxLayout()
        for text in ["Row banding every 5 · Ctrl+G jumps to a row",
                     "Identifiers monospaced so digits align column-wise",
                     "Enter opens the record · double-click edits · Alt+D documents"]:
            lbl = QLabel(text)
            lbl.setObjectName("FieldLabel")
            row.addWidget(lbl)
        row.addStretch()
        self.shown_label = QLabel("")
        self.shown_label.setObjectName("FieldLabel")
        row.addWidget(self.shown_label)
        return row

    # ---------------------------------------------------------------- data
    def reload(self):
        try:
            self.all_rows = da.read_engineering_index_rows(self.series_number, self.equip_key)
        except Exception as exc:
            self.main_window.statusBar().showMessage(f"Couldn't read the workbook: {exc}", 6000)
            self.all_rows = []
        # Flags are computed lazily in _render_rows, per visible row, not
        # eagerly here for every row regardless of whether it survives the
        # search filter (GUI audit Part 3 #15).
        self.apply_filter()
        self._render_legend()

    def _render_legend(self):
        while self.legend_body.count():
            item = self.legend_body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        counts = {}
        for e in self.all_rows:
            key = e.get("desc") or "(not set)"
            counts[key] = counts.get(key, 0) + 1
        palette = [_C["accent"], LEGEND_EXTRA_BLUE, _C["accent2"], _C["pale_blue"]]
        for i, (name, n) in enumerate(sorted(counts.items(), key=lambda kv: -kv[1])[:5]):
            sw = QLabel()
            sw.setFixedSize(11, 11)
            color = palette[i % len(palette)] if name != "(not set)" else None
            if color:
                sw.setStyleSheet(f"background:{color};")
            else:
                sw.setStyleSheet(f"background:{_C['white']};border:2px dashed {_C['unchecked']};")
            wrap = QHBoxLayout()
            wrap.setSpacing(6)
            wrap.addWidget(sw)
            lbl = QLabel(f"{name}  {n}")
            lbl.setStyleSheet(f"font-size:12px;color:{_C['body']};")
            wrap.addWidget(lbl)
            holder = QWidget()
            holder.setLayout(wrap)
            self.legend_body.addWidget(holder)

    def apply_filter(self):
        query = self.search_edit.text().strip().lower()
        rows = self.all_rows
        if query:
            terms = query.split()
            def matches(r):
                hay = " ".join(str(r.get(k, "")) for k in
                                ("key_value", "loop_id", "desc", "kind", "pid_number")).lower()
                return all(t in hay for t in terms)
            rows = [r for r in rows if matches(r)]
        self.filtered_rows = rows
        self._render_rows()

        missing_serial = sum(1 for r in self.all_rows if not r.get("serial"))
        open_ecn = sum(1 for r in self.all_rows if r.get("open_ecns"))
        missing_cal_due = sum(1 for r in self.all_rows if not r.get("cal_due_date"))
        self.exception_label.setText(
            f"{missing_serial} serials missing · {open_ecn} open ECNs · "
            f"{missing_cal_due} awaiting calibration date")
        self.shown_label.setText(f"{len(rows)} of {len(self.all_rows)} shown")
        self.subtitle.setText(f"{len(self.all_rows)} {self.etype['label'].lower()}s")

    def _render_rows(self):
        d = DENSITIES[self.density]
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        font = QFont("Barlow")
        font.setPointSize(d["font_pt"])
        # A real family list, not the QSS-only font-stack string theme.
        # MONO_FONT is written as (a single string like that would just be
        # looked up as one literal, nonexistent family name) - see theme.
        # MONO_FONT_FAMILIES's own comment (GUI audit Part 3 #23).
        mono_font = QFont()
        mono_font.setFamilies(theme.MONO_FONT_FAMILIES)
        mono_font.setStyleHint(QFont.Monospace)
        mono_font.setPointSize(d["font_pt"])
        for i, entry in enumerate(self.filtered_rows):
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setRowHeight(r, d["row_h"])
            banded = (i + 1) % 5 == 0

            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            num_item.setFlags(num_item.flags() & ~Qt.ItemIsEditable)
            num_item.setBackground(QColor(_C["zebra"]))
            num_item.setForeground(QColor(_C["secondary"]))
            if banded:
                banded_font = QFont(mono_font)
                banded_font.setBold(True)
                num_item.setFont(banded_font)
                num_item.setBackground(QColor(_C["group_alt"]))
            else:
                num_item.setFont(mono_font)
            self.table.setItem(r, 0, num_item)

            values = {
                "Tag": entry["key_value"], "Loop ID": entry.get("loop_id") or "—",
                # entry["service"] only exists for a type that has both a
                # real "service" and a real "system" field (see data_access.
                # EQUIPMENT_TYPES's "service_field") - falls back to "desc"
                # for transmitter/valve, which only ever have one of the two.
                "Service": entry.get("service", entry.get("desc")) or "—",
                "System": entry.get("desc") or "—",
                "P&ID (Rev)": (entry.get("pid_number") or "—") + (
                    f" ({entry['pid_rev']})" if entry.get("pid_rev") else ""),
                "Line #": entry.get("line_number") or "—",
                "Make": entry.get("make") or "—", "Model": entry.get("model") or "—",
                "Serial #": entry.get("serial") or "—",
                "Cal. Range": entry.get("calibration_range") or "—",
                "Inst. Range": entry.get("instrument_range") or "—",
                "Cal. Due": entry.get("cal_due_date") or "—",
                "Hook-up Dwg": entry.get("hookup_dwg") or "—",
                "JB / Cable": "/".join(x for x in (entry.get("jb_number"), entry.get("cable_number")) if x) or "—",
                "Loop Dwg": entry.get("loop_dwg") or "—",
                "DS Rev": entry.get("datasheet_rev") or "—",
                "QA Date": entry.get("qa_date") or "—",
            }
            for c, (label, _group, _w, kind) in enumerate(COLUMNS, start=1):
                if kind == "stage":
                    self.table.setCellWidget(r, c, StageCell(entry["stage"], entry["key_value"]))
                    continue
                if kind == "doc":
                    chip = doc_chip_label(entry.get("doc_status"))
                    if chip:
                        self.table.setCellWidget(r, c, chip)
                    else:
                        item = QTableWidgetItem("—")
                        item.setForeground(QColor(_C["secondary"]))
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(r, c, item)
                    continue
                if kind == "ecn":
                    ecns = entry.get("open_ecns") or []
                    text = ecns[0]["id"] if ecns else "—"
                    item = QTableWidgetItem(text)
                    item.setForeground(QColor(_C["error"]) if ecns else QColor(_C["secondary"]))
                    if ecns:
                        f = QFont(font)
                        f.setBold(True)
                        item.setFont(f)
                    self.table.setItem(r, c, item)
                    continue

                text = values.get(label, entry.get(label, "") or "—")
                item = QTableWidgetItem(str(text))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setFont(mono_font if kind in ("mono", "range") else font)
                if kind == "range":
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                # No explicit background here any more - setAlternatingRow
                # Colors() (see _build_table) now supplies the zebra stripe
                # via QSS, the same theme-independent color in every theme
                # instead of the literal QColor("#f5f5f8")/("#ffffff") this
                # used to force regardless of theme (GUI audit Part 3 #17).
                accessible = f"{entry['key_value']}, {label}: {text}"
                item.setData(Qt.AccessibleTextRole, accessible)
                self.table.setItem(r, c, item)

            # Computed per rendered row, not eagerly for every row in
            # reload() regardless of whether it's actually shown (GUI audit
            # Part 3 #15), and now the same check data_access.run_row_flag
            # uses everywhere else instead of a diverged local copy that
            # silently dropped the "Submitted, no serial" case (GUI audit
            # Part 3 #27).
            submitted = entry.get("stage") == STAGE_WORDS.index("Submitted")
            flag = da.run_row_flag(self.equip_key, entry, submitted)
            if flag:
                flag_item = self.table.item(r, 1)  # Tag column carries the flag as a tooltip
                if flag_item:
                    flag_item.setToolTip(flag)
                    flag_item.setForeground(QColor(_C["error"]))
        self.table.blockSignals(False)

    # -------------------------------------------------------------- rows
    def selected_rows(self):
        idxs = sorted({i.row() for i in self.table.selectedIndexes()})
        return [self.filtered_rows[i] for i in idxs if i < len(self.filtered_rows)]

    def _on_selection_changed(self):
        rows = self.selected_rows()
        if rows:
            self.selection_bar.show()
            self.selection_count_label.setText(
                f"{len(rows)} row{'s' if len(rows) != 1 else ''} selected")
        else:
            self.selection_bar.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.table.clearSelection()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and self.table.hasFocus():
            self.view_selected()
            return
        if event.key() == Qt.Key_G and event.modifiers() & Qt.ControlModifier:
            self.jump_to_row()
            return
        super().keyPressEvent(event)

    def jump_to_row(self):
        n, ok = QInputDialog.getInt(
            self, "Jump to row", "Row # (as shown in the # column):",
            1, 1, max(1, len(self.filtered_rows)))
        if ok and 1 <= n <= len(self.filtered_rows):
            self.table.selectRow(n - 1)
            self.table.scrollToItem(self.table.item(n - 1, 0))
            self.table.setFocus()

    def view_selected(self):
        """Enter on a row opens the read-only Record view (plate 1e) -
        double-click still opens Edit directly, same distinction the
        design draws between a quick look and committing to a change."""
        rows = self.selected_rows()
        if not rows:
            return
        self.main_window.view_row(self.series_number, self.equip_key, rows[0]["row"])
        self.reload()

    # ------------------------------------------------------------- actions
    def add_new(self):
        self.main_window.add_new_row(self.series_number, self.equip_key)
        self.reload()

    def edit_row_at(self, table_row):
        if table_row < 0 or table_row >= len(self.filtered_rows):
            return
        entry = self.filtered_rows[table_row]
        self.main_window.edit_row(self.series_number, self.equip_key, entry["row"])
        self.reload()

    def edit_selected(self):
        """Ctrl+E - edits the first selected row, same as double-clicking
        it. Named to match the shortcut dispatcher's expectations."""
        rows = self.selected_rows()
        if not rows:
            return
        self.main_window.edit_row(self.series_number, self.equip_key, rows[0]["row"])
        self.reload()

    def open_export(self):
        self.main_window.open_export_for(self.series_number, self.equip_key)

    def bulk_set_stage(self, stage):
        """One read + one write of status.json for the whole selection via
        da.bulk_set_stage, not one read+write per row via set_run_stage in
        a loop (GUI audit Part 3 #14), and pushed to undo_stack like every
        equivalent bulk action in gui_app.py already does (#28) - grouped
        by each row's OWN prior stage, since a mixed selection can't be
        undone back to a single shared value with one bulk call."""
        rows = self.selected_rows()
        if not rows:
            return
        keys = [(self.series_number, self.equip_key, e["key_value"]) for e in rows]
        before_by_stage = {}
        for e in rows:
            before_by_stage.setdefault(e.get("stage", 0), []).append(
                (self.series_number, self.equip_key, e["key_value"]))

        def do_redo():
            da.bulk_set_stage(keys, stage)
            self.reload()
            self.main_window.refresh_sidebar_and_dashboard()

        def do_undo():
            for prev_stage, ks in before_by_stage.items():
                da.bulk_set_stage(ks, prev_stage)
            self.reload()
            self.main_window.refresh_sidebar_and_dashboard()

        do_redo()
        self.main_window.undo_stack.push(
            f"{STAGE_WORDS[stage]} on {len(rows)} row(s)", do_undo, do_redo)
        self.main_window.statusBar().showMessage(
            f"{len(rows)} row(s) → {STAGE_WORDS[stage]}", 2500)

    def bulk_set_date(self):
        """Replaces the old Mass Edit Dates dialog per plate 1k's
        "sign-off legend" panel: once every date column carries a signed /
        not-signed mark, the remaining job is one item in the selection
        bar and a normal inline edit - no separate dialog needed. Pushes to
        undo_stack (GUI audit Part 3 #28); entry["qa_date"] already holds
        each row's own prior value (read_engineering_index_rows renames the
        raw qa_date_field to it), so no extra read is needed to snapshot it."""
        rows = self.selected_rows()
        if not rows:
            return
        date_str, ok = QInputDialog.getText(
            self, "Set a date", "Date (YYYY-MM-DD), or leave blank to clear:")
        if not ok:
            return
        qa_field = self.etype["qa_date_field"]
        new_val = date_str.strip()
        before = [(e["row"], qa_field, e.get("qa_date") or "") for e in rows]
        updates = [(e["row"], qa_field, new_val) for e in rows]

        def do_redo():
            da.save_fields_bulk(self.series_number, self.equip_key, updates)
            self.reload()

        def do_undo():
            da.save_fields_bulk(self.series_number, self.equip_key, before)
            self.reload()

        do_redo()
        self.main_window.undo_stack.push(
            f"Set {qa_field.replace('_', ' ')} on {len(rows)} row(s)", do_undo, do_redo)
        self.main_window.statusBar().showMessage(
            f"Set {qa_field.replace('_', ' ')} on {len(rows)} row(s)", 3000)

    def bulk_queue_export(self):
        """Pushes to undo_stack (GUI audit Part 3 #28), grouped by each
        row's own prior queued flag for the same reason bulk_set_stage
        groups by prior stage."""
        rows = self.selected_rows()
        if not rows:
            return
        keys = [(self.series_number, self.equip_key, e["key_value"]) for e in rows]
        before_by_flag = {}
        for e in rows:
            before_by_flag.setdefault(bool(e.get("queued")), []).append(
                (self.series_number, self.equip_key, e["key_value"]))

        def do_redo():
            da.bulk_set_status(keys, export=True)
            self.reload()

        def do_undo():
            for prev_flag, ks in before_by_flag.items():
                da.bulk_set_status(ks, export=prev_flag)
            self.reload()

        do_redo()
        self.main_window.undo_stack.push(f"Queue {len(rows)} row(s) for export", do_undo, do_redo)
        self.main_window.statusBar().showMessage(f"Queued {len(rows)} row(s) for export", 2500)

    def remove_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        self.main_window.remove_rows(self.series_number, self.equip_key, [e["row"] for e in rows])
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()
