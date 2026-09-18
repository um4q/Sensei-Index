# -*- coding: utf-8 -*-
"""
Overall Index (GUI audit Part 3, Section 3): one flat table across every
real instrument tag in "Instrumentation Master List.xlsx" - all 9 areas,
all ~100 raw instrument-type strings, not just the three equipment types
(Transmitter/Valve/Gauge) this app can generate a PDF record for. Read-
and-triage only - nothing on this screen ever edits a cell. Activating a
Recorded/Open row opens that tag's real record through main_window's own
view_row (the same read-only dialog the per-series Index table uses);
activating a No form row says plainly that its type has no PDF record
here instead of pretending to open one.

Deliberately virtualized (QAbstractTableModel + QStyledItemDelegate, no
QTableWidget/setItem/setCellWidget) because this table is an order of
magnitude bigger than any per-series Index table - "only the visible
rows exist" isn't optional at this size the way it was a nice-to-have
before. See OverallIndexModel/OverallIndexDelegate below.

Like index_view.py, this module never imports gui_app - it calls back
through main_window instead (see OverallIndexView's docstring), so the
two files can't form an import cycle.
"""
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPen, QPainter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableView, QHeaderView, QAbstractItemView,
    QFrame, QStyledItemDelegate, QStyle, QMessageBox, QButtonGroup, QScrollArea,
)

import master_list as ml
import theme

ROLE_KIND = Qt.UserRole + 1
ROLE_ROWDATA = Qt.UserRole + 2

ROW_HEIGHT = 34
RECORD_LABELS = {"recorded": "Recorded", "open": "Open", "no_form": "No form"}

GROUP_BY_OPTIONS = [
    ("None", None), ("Discipline", "discipline"), ("Type family", "family"),
    ("Area", "area"), ("System", "system"),
]
STATUS_FILTER_OPTIONS = [("all", "All"), ("recorded", "Recorded"), ("open", "Open")]


# =============================================================================
# Model + delegate - see module docstring for why this screen is the one
# place in the app that doesn't build a QTableWidgetItem/cell widget per row.
# =============================================================================
class OverallIndexModel(QAbstractTableModel):
    """Wraps a flat display list built by set_rows(): each entry is either
    {"kind": "row", "data": <a master_list.overall_index_rows() dict>,
    "num": <running count>} or {"kind": "header", "label": ..., "count":
    ...} for a group divider - emitted into the SAME flat list rather
    than a tree, per Section 3.3's "no tree view, no nesting/spanning."
    A header occupies one row slot of the same fixed height as a data
    row; OverallIndexDelegate paints the two kinds differently."""

    COLUMN_LABELS = ["#", "Tag", "Service", "Instrument Type", "System", "Area", "Record"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._display = []

    def set_rows(self, rows, group_by=None):
        self.beginResetModel()
        display = []
        if group_by:
            groups = {}
            order = []
            for r in rows:
                key = r.get(group_by) or "(Not set)"
                if key not in groups:
                    groups[key] = []
                    order.append(key)
                groups[key].append(r)
            order.sort(key=lambda k: -len(groups[k]))
            n = 0
            for key in order:
                display.append({"kind": "header", "label": key, "count": len(groups[key])})
                for r in groups[key]:
                    n += 1
                    display.append({"kind": "row", "data": r, "num": n})
        else:
            for n, r in enumerate(rows, start=1):
                display.append({"kind": "row", "data": r, "num": n})
        self._display = display
        self.endResetModel()

    def entry_at(self, row):
        return self._display[row] if 0 <= row < len(self._display) else None

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._display)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMN_LABELS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self.COLUMN_LABELS[section]
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.NoItemFlags
        entry = self._display[index.row()]
        if entry["kind"] != "row":
            return Qt.ItemIsEnabled
        return Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def _value(self, r, col, entry):
        if col == 0:
            return str(entry["num"])
        if col == 1:
            return r["tag"]
        if col == 2:
            return r["service"] or "—"
        if col == 3:
            return r["type_desc"]
        if col == 4:
            return r["system"] or "—"
        if col == 5:
            return r["area"]
        if col == 6:
            return RECORD_LABELS[r["record_state"]]
        return ""

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        entry = self._display[index.row()]
        col = index.column()
        if role == ROLE_KIND:
            return entry["kind"]
        if entry["kind"] == "header":
            if role == Qt.DisplayRole and col == 1:
                return f"{entry['label']}   ({entry['count']})"
            return None
        r = entry["data"]
        if role == ROLE_ROWDATA:
            return r
        if role == Qt.DisplayRole:
            return self._value(r, col, entry)
        if role == Qt.ToolTipRole and col == 3:
            return r["type_desc"]
        if role == Qt.TextAlignmentRole and col == 0:
            return Qt.AlignCenter
        if role == Qt.AccessibleTextRole:
            return f"{r['tag']}, {self.COLUMN_LABELS[col]}: {self._value(r, col, entry)}"
        return None


class OverallIndexDelegate(QStyledItemDelegate):
    """Paints group-header rows as a solid band (label in the Tag column
    only), the Tag column as a discipline-color rail + monospaced text,
    and the Record column as a filled/outline/muted chip - the three
    places COLUMNS' generic text rendering isn't enough. Every other
    column falls through to the normal QStyledItemDelegate paint, which
    already respects the view's alternating-row-color QSS."""

    def paint(self, painter, option, index):
        if index.data(ROLE_KIND) == "header":
            self._paint_header(painter, option, index)
            return
        col = index.column()
        if col == 1:
            self._paint_tag(painter, option, index)
            return
        if col == 6:
            self._paint_record(painter, option, index)
            return
        super().paint(painter, option, index)

    def _row_background(self, option, index):
        if option.state & QStyle.State_Selected:
            return QColor(theme.LIGHT["highlight"])
        if index.row() % 2 == 1:
            return QColor(theme.LIGHT["zebra"])
        return QColor(theme.LIGHT["white"])

    def _paint_header(self, painter, option, index):
        painter.save()
        painter.fillRect(option.rect, QColor(theme.LIGHT["group_alt"]))
        if index.column() == 1:
            f = QFont("Barlow Condensed SemiBold")
            f.setPointSize(10)
            painter.setFont(f)
            painter.setPen(QColor(theme.LIGHT["navy"]))
            painter.drawText(option.rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft,
                              index.data(Qt.DisplayRole) or "")
        painter.restore()

    def _paint_tag(self, painter, option, index):
        painter.save()
        painter.fillRect(option.rect, self._row_background(option, index))
        r = index.data(ROLE_ROWDATA)
        rail = QColor(theme.DISCIPLINE_COLORS.get(r["discipline"], theme.LIGHT["secondary"]))
        rail_rect = option.rect.adjusted(0, 3, 0, -3)
        rail_rect.setWidth(4)
        painter.fillRect(rail_rect, rail)
        font = QFont()
        font.setFamilies(theme.MONO_FONT_FAMILIES)
        font.setStyleHint(QFont.Monospace)
        painter.setFont(font)
        painter.setPen(QColor(theme.LIGHT["ink"]))
        painter.drawText(option.rect.adjusted(11, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, r["tag"])
        painter.restore()

    def _paint_record(self, painter, option, index):
        painter.save()
        painter.fillRect(option.rect, self._row_background(option, index))
        r = index.data(ROLE_ROWDATA)
        state = r["record_state"]
        chip = option.rect.adjusted(8, 7, -8, -7)
        painter.setRenderHint(QPainter.Antialiasing)
        if state == "recorded":
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.LIGHT["navy"]))
            painter.drawRoundedRect(chip, 4, 4)
            painter.setPen(QColor(theme.LIGHT["white"]))
        elif state == "open":
            pen = QPen(QColor(theme.LIGHT["accent"]))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(chip, 4, 4)
            painter.setPen(QColor(theme.LIGHT["accent"]))
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.LIGHT["chrome"]))
            painter.drawRoundedRect(chip, 4, 4)
            painter.setPen(QColor(theme.LIGHT["secondary"]))
        f = QFont("Barlow Condensed SemiBold")
        f.setPointSize(9)
        painter.setFont(f)
        painter.drawText(chip, Qt.AlignCenter, RECORD_LABELS[state])
        painter.restore()


# =============================================================================
# Discipline card - the same track/fill progress-bar technique MainWindow's
# own series rail already uses, but its OWN colors (see the comment inside
# __init__) rather than gui_app.StatCard's shared Card/StatNumber/StatLabel
# object names.
# =============================================================================
class DisciplineCard(QFrame):
    clicked = Signal()

    def __init__(self, discipline, tags, recorded, active, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        pct = round(100 * recorded / tags) if tags else 0
        self.setAccessibleName(f"{discipline}, {tags} tags, {recorded} recorded, {pct} percent, "
                                + ("selected" if active else "filter to this discipline"))
        # Not objectName("Card") + the shared QLabel#StatNumber/StatLabel/
        # SectionLabel QSS rules - those color themselves from the ACTIVE
        # theme's ink/secondary/body tokens, which is right for a card that
        # sits on the ordinary theme-reactive page background, but this
        # card (like the Overall Index table right below it) is always a
        # white surface, in every theme. Applying that theme-reactive text
        # color to an always-white background is exactly the dark-theme-
        # unreadable bug this session's GUI audit fixed elsewhere (near-
        # white ink on a white card) - so this widget sets its own colors
        # directly from theme.LIGHT instead of opting into rules meant for
        # a different kind of surface. One inline stylesheet covers the
        # whole frame (background, border, radius) so nothing here depends
        # on cascade order against the app-level stylesheet.
        border = theme.DISCIPLINE_COLORS.get(discipline, theme.LIGHT["navy"]) if active else "rgba(29,31,32,.16)"
        border_w = 2 if active else 1
        self.setStyleSheet(
            f"QFrame {{ background: {theme.LIGHT['white']}; border: {border_w}px solid {border}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(3)

        top = QHBoxLayout()
        top.setSpacing(6)
        swatch = QLabel()
        swatch.setFixedSize(10, 10)
        swatch.setStyleSheet(f"background:{theme.DISCIPLINE_COLORS.get(discipline, theme.LIGHT['secondary'])};border-radius:5px;")
        top.addWidget(swatch)
        name = QLabel(discipline)
        name.setStyleSheet(f"font-size:12px;font-weight:600;color:{theme.LIGHT['body']};")
        top.addWidget(name)
        top.addStretch()
        layout.addLayout(top)

        num = QLabel(str(tags))
        num.setStyleSheet(f"font-size:26px;font-weight:600;color:{theme.LIGHT['ink']};")
        layout.addWidget(num)

        sub = QLabel(f"{recorded} recorded ({pct}%)")
        sub.setStyleSheet(f"font-size:12px;color:{theme.LIGHT['secondary']};")
        layout.addWidget(sub)

        track = QFrame()
        track.setFixedHeight(4)
        track.setStyleSheet(f"background:{theme.LIGHT['track']};")
        track_layout = QHBoxLayout(track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        track_layout.setSpacing(0)
        fill = QFrame()
        fill.setStyleSheet(f"background:{theme.LIGHT['navy']};")
        track_layout.addWidget(fill, stretch=max(1, pct))
        if pct < 100:
            track_layout.addStretch(max(1, 100 - pct))
        layout.addWidget(track)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)


DETAIL_FIELDS = [
    ("Raw instrument type", "type_desc"), ("Area", "area"), ("P&ID", "pid"),
    ("Line #", "line"), ("Module ID", "module_id"), ("Location layout", "location_layout"),
    ("Issued for", "issued_for"), ("Make/Model", None), ("Received", "received"),
    ("Installed", "installed_date"), ("EWP", "ewp"),
]


class OverallIndexView(QWidget):
    """main_window only needs to provide: view_row(series_number,
    equip_key, row_num) (already on MainWindow, same dialog the per-series
    Index table opens) and statusBar()."""

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.all_rows = []
        self.filtered_rows = []
        self.discipline_filter = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)
        outer.addLayout(self._build_header())
        outer.addWidget(self._build_cards_area())
        outer.addLayout(self._build_filter_row())
        outer.addWidget(self._build_table(), stretch=1)
        outer.addWidget(self._build_detail_panel())

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self.apply_filters)

        self.reload()

    # ------------------------------------------------------------- header
    def _build_header(self):
        row = QHBoxLayout()
        title = QLabel("Overall Index")
        title.setObjectName("PageTitle")
        row.addWidget(title)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("PageSubtitle")
        row.addWidget(self.subtitle)
        row.addStretch()
        return row

    def _build_cards_area(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setFixedHeight(236)
        holder = QWidget()
        self.cards_grid = QGridLayout(holder)
        self.cards_grid.setSpacing(10)
        scroll.setWidget(holder)
        return scroll

    def _render_cards(self, summary):
        while self.cards_grid.count():
            item = self.cards_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        by_disc = summary["by_discipline"]
        for i, discipline in enumerate(ml.DISCIPLINES):
            stats = by_disc.get(discipline, {"tags": 0, "recorded": 0})
            active = discipline == self.discipline_filter
            card = DisciplineCard(discipline, stats["tags"], stats["recorded"], active)
            card.clicked.connect(lambda d=discipline: self._toggle_discipline_filter(d))
            self.cards_grid.addWidget(card, i // 5, i % 5)

    def _toggle_discipline_filter(self, discipline):
        self.discipline_filter = None if self.discipline_filter == discipline else discipline
        self.apply_filters()
        self._render_cards(ml.summarize(self.all_rows))

    # --------------------------------------------------------- filter row
    def _build_filter_row(self):
        row = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("FilterSearch")
        self.search_edit.setPlaceholderText("⌕ Search tag, service, type, system, line, P&ID")
        self.search_edit.textChanged.connect(lambda _t: self._debounce.start())
        row.addWidget(self.search_edit, stretch=1)

        self.area_combo = QComboBox()
        self.area_combo.currentIndexChanged.connect(lambda _i: self.apply_filters())
        row.addWidget(self.area_combo)

        self.family_combo = QComboBox()
        self.family_combo.currentIndexChanged.connect(lambda _i: self.apply_filters())
        row.addWidget(self.family_combo)

        group_label = QLabel("Group by")
        group_label.setObjectName("FieldLabel")
        row.addWidget(group_label)
        self.group_combo = QComboBox()
        for label, _key in GROUP_BY_OPTIONS:
            self.group_combo.addItem(label)
        self.group_combo.currentIndexChanged.connect(lambda _i: self.apply_filters())
        row.addWidget(self.group_combo)

        self.status_buttons = QButtonGroup(self)
        self.status_buttons.setExclusive(True)
        for value, label in STATUS_FILTER_OPTIONS:
            btn = QPushButton(label)
            btn.setObjectName("DensityButton")
            btn.setCheckable(True)
            btn.setChecked(value == "all")
            btn.clicked.connect(lambda _c, v=value: self._set_status_filter(v))
            self.status_buttons.addButton(btn)
            row.addWidget(btn)
        self.status_filter = "all"

        return row

    def _set_status_filter(self, value):
        self.status_filter = value
        self.apply_filters()

    def _populate_filter_combos(self):
        areas = sorted({r["area"] for r in self.all_rows})
        self.area_combo.blockSignals(True)
        self.area_combo.clear()
        self.area_combo.addItem("All areas")
        self.area_combo.addItems(areas)
        self.area_combo.blockSignals(False)

        families = sorted({r["family"] for r in self.all_rows})
        self.family_combo.blockSignals(True)
        self.family_combo.clear()
        self.family_combo.addItem("All types")
        self.family_combo.addItems(families)
        self.family_combo.blockSignals(False)

    # -------------------------------------------------------------- table
    def _build_table(self):
        self.model = OverallIndexModel(self)
        self.table = QTableView()
        self.table.setObjectName("OverallIndexTable")
        self.table.setModel(self.model)
        self.table.setItemDelegate(OverallIndexDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        header = self.table.horizontalHeader()
        widths = [44, 170, 220, 260, 140, 130, 100]
        for i, w in enumerate(widths):
            header.setSectionResizeMode(i, QHeaderView.Interactive)
            self.table.setColumnWidth(i, w)
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Service
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Instrument Type
        header.setMinimumSectionSize(44)
        self.table.selectionModel().currentRowChanged.connect(self._on_current_changed)
        self.table.doubleClicked.connect(self._activate_index)
        return self.table

    def _build_detail_panel(self):
        self.detail_panel = QFrame()
        self.detail_panel.setFixedHeight(112)
        # Explicit LIGHT-locked inline styling, not objectName("Card") +
        # the shared FieldLabel QSS rule - same reasoning as DisciplineCard
        # above: this panel is an always-white surface, and FieldLabel's
        # color comes from the ACTIVE theme, which is unreadable against a
        # background that never changes with it.
        self.detail_panel.setStyleSheet(
            f"QFrame {{ background: {theme.LIGHT['white']}; border: 1px solid rgba(29,31,32,.16); }}")
        self.detail_grid = QGridLayout(self.detail_panel)
        self.detail_grid.setContentsMargins(16, 10, 16, 10)
        self.detail_grid.setHorizontalSpacing(22)
        self.detail_grid.setVerticalSpacing(4)
        self._detail_value_labels = {}
        for i, (label, _field) in enumerate(DETAIL_FIELDS):
            col = i // 3
            row = i % 3
            key_lbl = QLabel(label)
            key_lbl.setStyleSheet(f"color:{theme.LIGHT['secondary']};font-size:12px;")
            val_lbl = QLabel("—")
            val_lbl.setStyleSheet(f"font-weight:600;color:{theme.LIGHT['ink']};")
            pair = QVBoxLayout()
            pair.setSpacing(0)
            pair.addWidget(key_lbl)
            pair.addWidget(val_lbl)
            self.detail_grid.addLayout(pair, row, col)
            self._detail_value_labels[label] = val_lbl
        self._show_detail(None)
        return self.detail_panel

    def _show_detail(self, r):
        if r is None:
            for lbl in self._detail_value_labels.values():
                lbl.setText("—")
            self._detail_value_labels["Raw instrument type"].setText("Select a row to see its detail")
            return
        for label, field in DETAIL_FIELDS:
            if label == "Make/Model":
                text = " / ".join(x for x in (r.get("mfr"), r.get("model")) if x) or "—"
            else:
                text = r.get(field) or "—"
            self._detail_value_labels[label].setText(text)
        system_note = (f"{r['system']} (from the tracker record)" if r["system_source"] == "recorded"
                        else "Not yet logged – no System on file")
        self._detail_value_labels["Area"].setText(f"{r['area']}  ·  System: {system_note}")

    # ---------------------------------------------------------------- data
    def reload(self):
        try:
            self.all_rows = ml.overall_index_rows()
        except Exception as exc:
            self.main_window.statusBar().showMessage(f"Couldn't read the master list: {exc}", 6000)
            self.all_rows = []
        self._populate_filter_combos()
        self._render_cards(ml.summarize(self.all_rows))
        self.apply_filters()

    def apply_filters(self):
        rows = self.all_rows
        if self.discipline_filter:
            rows = [r for r in rows if r["discipline"] == self.discipline_filter]
        if self.area_combo.currentIndex() > 0:
            rows = [r for r in rows if r["area"] == self.area_combo.currentText()]
        if self.family_combo.currentIndex() > 0:
            rows = [r for r in rows if r["family"] == self.family_combo.currentText()]
        if self.status_filter != "all":
            rows = [r for r in rows if r["record_state"] == self.status_filter]
        query = self.search_edit.text().strip().lower()
        if query:
            terms = query.split()
            def matches(r):
                hay = " ".join(str(r.get(k, "")) for k in
                                ("tag", "service", "type_desc", "system", "line", "pid")).lower()
                return all(t in hay for t in terms)
            rows = [r for r in rows if matches(r)]

        self.filtered_rows = rows
        group_key = GROUP_BY_OPTIONS[self.group_combo.currentIndex()][1]
        self.model.set_rows(rows, group_key)
        self._show_detail(None)

        summary = ml.summarize(self.all_rows)
        self.subtitle.setText(
            f"{len(rows)} of {summary['total_tags']} shown · {summary['areas']} areas · "
            f"{summary['type_strings']} raw type strings · {summary['families']} families · "
            f"{summary['disciplines']} disciplines · {summary['recorded']} recorded "
            f"({summary['recorded_pct']}%) · {summary['no_form']} in families with no PDF form"
            + (f" · {summary['unclassified']} unclassified" if summary["unclassified"] else ""))

    def _on_current_changed(self, current, _previous):
        entry = self.model.entry_at(current.row()) if current.isValid() else None
        self._show_detail(entry["data"] if entry and entry["kind"] == "row" else None)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._activate_index(self.table.currentIndex())
            return
        super().keyPressEvent(event)

    def _activate_index(self, index):
        if not index.isValid():
            return
        entry = self.model.entry_at(index.row())
        if not entry or entry["kind"] != "row":
            return
        r = entry["data"]
        if r["link"] is None:
            QMessageBox.information(
                self, r["tag"],
                f"{r['tag']} ({r['type_desc']}) has no PDF test record in this app - its family, "
                f"“{r['family']}”, has never had one generated here.\n\n"
                f"Service: {r['service'] or '—'}\nArea: {r['area']}")
            return
        series_number, equip_key, row_num = r["link"]
        self.main_window.view_row(series_number, equip_key, row_num)
