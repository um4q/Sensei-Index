# -*- coding: utf-8 -*-
"""
The engineering-grade instrument index - plate 6a of the redesign brief,
"rebuilt, not patched": survey-density table with a two-row grouped
header (identity/process/device/calibration/installation/documents/
progress), monospaced identifiers, row banding every 5th row, document-
state chips, and an exception-counting toolbar, plus the filter chips,
system legend and selection bar from plate 1b underneath it.

This REPLACES IndexPage as the series+equipment-type table. It doesn't
reimplement Add/Edit, Export, or the row-detail view - those still open
through MainWindow's existing dialogs (edit_row / view_row / export_rows
/ etc.), passed in as callables so this module never imports gui_app and
gui_app can import this one without a cycle.
"""
import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QSizePolicy, QInputDialog,
)

import data_access as da

DENSITIES = {
    "Survey": {"row_h": 22, "font_pt": 9},
    "Standard": {"row_h": 30, "font_pt": 10},
    "Comfortable": {"row_h": 40, "font_pt": 11},
}

STAGE_WORDS = ["Not started", "Installed", "Submitted", "Accepted"]

# (label, group, width, kind) - kind picks the renderer: 'mono' identifiers,
# 'text' plain, 'range' right-aligned w/ unit, 'stage' the 3-seg+word
# widget, 'doc' the IFC/IFR/ECN/SUP chip.
COLUMNS = [
    ("Tag", "IDENTITY", 150, "mono"),
    ("Loop ID", "IDENTITY", 80, "mono"),
    ("Service", "IDENTITY", 170, "text"),
    ("System", "PROCESS", 130, "text"),
    ("P&ID (Rev)", "PROCESS", 130, "mono"),
    ("Line #", "PROCESS", 130, "mono"),
    ("Make", "DEVICE", 100, "text"),
    ("Model", "DEVICE", 140, "text"),
    ("Serial #", "DEVICE", 110, "mono"),
    ("Cal. Range", "CALIBRATION", 130, "range"),
    ("Inst. Range", "CALIBRATION", 130, "range"),
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

GROUP_COLORS = {
    "IDENTITY": "#eef6ff", "PROCESS": "#e7e7ea", "DEVICE": "#e7e7ea",
    "CALIBRATION": "#eef6ff", "INSTALLATION": "#e7e7ea", "DOCUMENTS": "#eef6ff",
    "PROGRESS": "#e7e7ea",
}
GROUP_TEXT = {"IDENTITY": "#1d2d3d", "CALIBRATION": "#1d2d3d", "DOCUMENTS": "#1d2d3d"}

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
        band_color = QColor(GROUP_COLORS.get(group, "#e9e9ea"))
        text_color = QColor(GROUP_TEXT.get(group, "#42474b"))

        band_rect = rect.adjusted(0, 0, 0, -(rect.height() - self.GROUP_BAND_H))
        painter.fillRect(band_rect, band_color)
        col_rect = rect.adjusted(0, self.GROUP_BAND_H, 0, 0)
        painter.fillRect(col_rect, QColor("#e9e9ea"))

        painter.setPen(QColor(210, 210, 212))
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
        painter.setPen(QColor("#42474b"))
        painter.drawText(col_rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, label)
        painter.restore()


def _numeric_bounds(text):
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text or "")]


def row_flag(entry):
    cal = _numeric_bounds(entry.get("calibration_range", ""))
    span = _numeric_bounds(entry.get("instrument_range", ""))
    if len(cal) == 2 and len(span) == 2 and (cal[0] < span[0] or cal[1] > span[1]):
        return "Range exceeds instrument span"
    serial = (entry.get("serial") or "").strip()
    if not serial:
        return "No serial number"
    return ""


class StageCell(QWidget):
    def __init__(self, stage):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(2)
        for i in range(3):
            block = QLabel()
            block.setFixedSize(24, 8)
            filled = stage > i
            block.setStyleSheet(f"background:{'#1d2d3d' if filled else '#d4d4d7'};")
            layout.addWidget(block)
        word = QLabel(STAGE_WORDS[stage])
        word.setStyleSheet(f"font:400 11.5px 'Barlow';color:{'#5d5d60' if stage == 0 else '#1d1f20'};")
        layout.addWidget(word)
        layout.addStretch()
        self.setAccessibleName(f"stage: {STAGE_WORDS[stage]}")


def doc_chip_label(status):
    text = (status or "").strip().upper()
    styles = {
        "IFC": ("background:#eef6ff;color:#1d2d3d;", "Issued for construction"),
        "IFR": ("background:#e7e7ea;color:#42474b;", "Issued for review"),
        "ECN": ("background:#fdecea;color:#c0392b;", "Change outstanding"),
        "SUP": ("background:#e7e7ea;color:#5d5d60;", "Superseded"),
    }
    if text not in styles:
        return None
    css, tip = styles[text]
    lbl = QLabel(text)
    lbl.setStyleSheet(f"{css}font:600 10px 'Barlow Condensed SemiBold';padding:2px 5px;")
    lbl.setToolTip(tip)
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


class IndexView(QWidget):
    """main_window only needs to provide: series_display_label(number)
    (already on da), and these callables on itself: edit_row(sn, ek, row),
    view_row(sn, ek, row), open_export(sn, ek, filters), open_documents
    (sn, ek, key_value), statusBar(), undo_stack, refresh_sidebar_and_
    dashboard()."""

    def __init__(self, main_window, series_number, equip_key):
        super().__init__()
        self.main_window = main_window
        self.series_number = series_number
        self.equip_key = equip_key
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.all_rows = []
        self.filtered_rows = []
        self.density = "Survey"
        self.active_filters = {}  # label -> predicate

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
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("PageSubtitle")
        row.addWidget(self.subtitle)
        row.addStretch()

        density_row = QHBoxLayout()
        density_row.setSpacing(0)
        self._density_buttons = {}
        for name in DENSITIES:
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == self.density)
            btn.setStyleSheet(
                "QPushButton{border:1px solid rgba(29,31,32,.3);padding:5px 10px;font-size:12px;}"
                "QPushButton:checked{background:#1d2d3d;color:#fff;}")
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
        self.table.setColumnWidth(0, 34)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        for i, (_label, _group, width, _kind) in enumerate(COLUMNS, start=1):
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.Interactive)
            self.table.setColumnWidth(i, width)
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
        esc_hint.setStyleSheet("color:#b5d9fd;font-size:12.5px;")
        layout.addWidget(esc_hint)
        return bar

    def _build_footer(self):
        row = QHBoxLayout()
        for text in ["Row banding every 5 · Ctrl+G jumps to a row",
                     "Identifiers monospaced so digits align column-wise"]:
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
        for e in self.all_rows:
            e["flag"] = row_flag(e)
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
        palette = ["#416180", "#749dc4", "#5980a6", "#94bce3"]
        for i, (name, n) in enumerate(sorted(counts.items(), key=lambda kv: -kv[1])[:5]):
            sw = QLabel()
            sw.setFixedSize(11, 11)
            color = palette[i % len(palette)] if name != "(not set)" else None
            if color:
                sw.setStyleSheet(f"background:{color};")
            else:
                sw.setStyleSheet("background:#fff;border:2px dashed #7a7a7d;")
            wrap = QHBoxLayout()
            wrap.setSpacing(6)
            wrap.addWidget(sw)
            lbl = QLabel(f"{name}  {n}")
            lbl.setStyleSheet("font-size:12px;color:#42474b;")
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
        mono_font = QFont("ui-monospace")
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
            num_item.setBackground(QColor("#f5f5f8"))
            num_item.setForeground(QColor("#5d5d60"))
            if banded:
                banded_font = QFont(mono_font)
                banded_font.setBold(True)
                num_item.setFont(banded_font)
                num_item.setBackground(QColor("#e0e0e3"))
            else:
                num_item.setFont(mono_font)
            self.table.setItem(r, 0, num_item)

            row_bg = QColor("#f5f5f8") if i % 2 else QColor("#ffffff")
            values = {
                "Tag": entry["key_value"], "Loop ID": entry.get("loop_id") or "—",
                "Service": entry.get("desc") or "—", "System": entry.get("desc") or "—",
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
                    self.table.setCellWidget(r, c, StageCell(entry["stage"]))
                    continue
                if kind == "doc":
                    chip = doc_chip_label(entry.get("doc_status"))
                    if chip:
                        self.table.setCellWidget(r, c, chip)
                    else:
                        item = QTableWidgetItem("—")
                        item.setForeground(QColor("#5d5d60"))
                        item.setTextAlignment(Qt.AlignCenter)
                        self.table.setItem(r, c, item)
                    continue
                if kind == "ecn":
                    ecns = entry.get("open_ecns") or []
                    text = ecns[0]["id"] if ecns else "—"
                    item = QTableWidgetItem(text)
                    item.setForeground(QColor("#c0392b") if ecns else QColor("#5d5d60"))
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
                item.setBackground(row_bg)
                accessible = f"{entry['key_value']}, {label}: {text}"
                item.setData(Qt.AccessibleTextRole, accessible)
                self.table.setItem(r, c, item)

            if entry.get("flag"):
                flag_item = self.table.item(r, 1)  # Tag column carries the flag as a tooltip
                if flag_item:
                    flag_item.setToolTip(entry["flag"])
                    flag_item.setForeground(QColor("#c0392b"))
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
        super().keyPressEvent(event)

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
        rows = self.selected_rows()
        if not rows:
            return
        for entry in rows:
            da.set_run_stage(self.series_number, self.equip_key, entry["key_value"], stage)
        self.main_window.statusBar().showMessage(
            f"{len(rows)} row(s) → {STAGE_WORDS[stage]}", 2500)
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()

    def bulk_set_date(self):
        """Replaces the old Mass Edit Dates dialog per plate 1k's
        "sign-off legend" panel: once every date column carries a signed /
        not-signed mark, the remaining job is one item in the selection
        bar and a normal inline edit - no separate dialog needed."""
        rows = self.selected_rows()
        if not rows:
            return
        date_str, ok = QInputDialog.getText(
            self, "Set a date", "Date (YYYY-MM-DD), or leave blank to clear:")
        if not ok:
            return
        qa_field = "yanda_qa_date" if self.equip_key == "transmitter" else "qc_date"
        updates = [(e["row"], qa_field, date_str.strip()) for e in rows]
        da.save_fields_bulk(self.series_number, self.equip_key, updates)
        self.main_window.statusBar().showMessage(
            f"Set {qa_field.replace('_', ' ')} on {len(rows)} row(s)", 3000)
        self.reload()

    def bulk_queue_export(self):
        rows = self.selected_rows()
        if not rows:
            return
        keys = [(self.series_number, self.equip_key, e["key_value"]) for e in rows]
        da.bulk_set_status(keys, export=True)
        self.main_window.statusBar().showMessage(f"Queued {len(rows)} row(s) for export", 2500)
        self.reload()

    def remove_selected(self):
        rows = self.selected_rows()
        if not rows:
            return
        self.main_window.remove_rows(self.series_number, self.equip_key, [e["row"] for e in rows])
        self.reload()
        self.main_window.refresh_sidebar_and_dashboard()
