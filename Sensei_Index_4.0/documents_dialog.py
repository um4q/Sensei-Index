# -*- coding: utf-8 -*-
"""
Documents & ECN - plate 6b: "the register, the revision history and the
engineering change notices for one tag, one keystroke (Alt+D) from its
row."

Reads documents.json / ecn.json / revision_log.json through data_access.py
(the "three stores, all local and all small" the plate's build note
describes) - never imports gui_app, same no-cycle pattern as index_view.py.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QScrollArea, QWidget,
    QMessageBox,
)

import data_access as da

DOC_CHIP_STYLE = {
    "IFC": "background:#eef6ff;color:#1d2d3d;",
    "IFR": "background:#e7e7ea;color:#42474b;",
    "ECN": "background:#fdecea;color:#c0392b;",
    "SUP": "background:#e7e7ea;color:#5d5d60;",
}


class DocumentsDialog(QDialog):
    def __init__(self, parent, series_number, equip_key, key_value):
        super().__init__(parent)
        self.series_number = series_number
        self.equip_key = equip_key
        self.key_value = key_value
        self.etype = da.EQUIPMENT_TYPES[equip_key]
        self.resize(900, 860)
        self.setWindowTitle(f"{key_value} — documents & change")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)
        scroll.setWidget(body)

        layout.addLayout(self._build_header())
        self.ecn_banner_slot = QVBoxLayout()
        layout.addLayout(self.ecn_banner_slot)
        layout.addWidget(self._build_document_register())
        layout.addWidget(self._build_revision_history())
        layout.addStretch()

        outer.addWidget(scroll, stretch=1)
        outer.addWidget(self._build_footer())

        self._reload_ecn_banner()

    # ------------------------------------------------------------- header
    def _build_header(self):
        col = QVBoxLayout()
        loop = QLabel(f"LOOP {self._loop_id() or '—'}")
        loop.setObjectName("FieldLabel")
        col.addWidget(loop)

        title_row = QHBoxLayout()
        title = QLabel(self.key_value)
        title.setObjectName("PageTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        open_sheet_btn = QPushButton("Open check sheet")
        open_sheet_btn.setObjectName("Ghost")
        open_sheet_btn.clicked.connect(self._open_check_sheet)
        title_row.addWidget(open_sheet_btn)
        col.addLayout(title_row)

        entry = self._entry()
        subtitle_bits = [entry.get(self.etype["summary_fields"][-1], ""),
                          entry.get("service", "") or entry.get("system", ""),
                          entry.get("pid_number", "")]
        subtitle = QLabel(" · ".join(b for b in subtitle_bits if b))
        subtitle.setObjectName("PageSubtitle")
        col.addWidget(subtitle)
        return col

    def _loop_id(self):
        try:
            return da.read_full_row(self.series_number, self.equip_key, self._row_num()).get("loop_id", "")
        except Exception:
            return ""

    def _row_num(self):
        rows = da.read_index_rows(self.series_number, self.equip_key)
        key_field = self.etype["key_field"]
        for r in rows:
            if r.get(key_field) == self.key_value:
                return r["row"]
        return None

    def _entry(self):
        row_num = self._row_num()
        if row_num is None:
            return {}
        try:
            return da.read_full_row(self.series_number, self.equip_key, row_num)
        except Exception:
            return {}

    def _open_check_sheet(self):
        self.accept()
        parent = self.parent()
        row_num = self._row_num()
        if parent is not None and row_num is not None and hasattr(parent, "edit_row"):
            parent.edit_row(self.series_number, self.equip_key, row_num)

    # --------------------------------------------------------------- ECN
    def _reload_ecn_banner(self):
        while self.ecn_banner_slot.count():
            item = self.ecn_banner_slot.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        open_ecns = da.ecns_for_tag(self.key_value, open_only=True)
        for ecn in open_ecns:
            banner = QFrame()
            banner.setStyleSheet("background:#fdecea;")
            blayout = QVBoxLayout(banner)
            blayout.setContentsMargins(12, 10, 12, 10)
            blayout.setSpacing(6)
            label = QLabel(f"{ecn['id']} · OPEN")
            label.setStyleSheet("color:#c0392b;font:600 11px 'Barlow Condensed SemiBold';letter-spacing:1px;")
            blayout.addWidget(label)
            body = QLabel(ecn.get("narrative", ""))
            body.setWordWrap(True)
            body.setStyleSheet("color:#42474b;font-size:13px;")
            blayout.addWidget(body)
            row = QHBoxLayout()
            row.addStretch()
            ack_btn = QPushButton(f"Acknowledge {ecn['id']}")
            ack_btn.setObjectName("Primary")
            ack_btn.clicked.connect(lambda _c, e=ecn: self._acknowledge(e))
            row.addWidget(ack_btn)
            blayout.addLayout(row)
            self.ecn_banner_slot.addWidget(banner)

    def _acknowledge(self, ecn):
        range_changed = "range" in (ecn.get("narrative") or "").lower()
        affected = []
        for tag in ecn.get("affected_tags", []):
            for series_number in da.list_series():
                for equip_key in da.EQUIPMENT_TYPES:
                    rows = da.read_index_rows(series_number, equip_key)
                    key_field = da.EQUIPMENT_TYPES[equip_key]["key_field"]
                    if any(r.get(key_field) == tag for r in rows):
                        affected.append((series_number, equip_key, tag))
        who = da.get_setting("crew_name") or "Unnamed crew member"
        da.acknowledge_ecn(ecn["id"], who, range_changed=range_changed, affected_records=affected)
        da.append_revision(self.key_value, who, f"acknowledged {ecn['id']}", ecn_id=ecn["id"])
        self._reload_ecn_banner()
        self._reload_revisions()
        QMessageBox.information(self, "Acknowledged", f"{ecn['id']} acknowledged.")

    # --------------------------------------------------- document register
    def _build_document_register(self):
        frame = QFrame()
        frame.setObjectName("Card")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 12, 14, 12)
        kicker = QLabel("DOCUMENT REGISTER")
        kicker.setObjectName("SectionLabel")
        layout.addWidget(kicker)

        table = QTableWidget(0, 6)
        table.setHorizontalHeaderLabels(["Doc No.", "Title", "Rev", "Status", "Issued", "Transmittal"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        docs = da.documents_for_tag(self.key_value)
        table.setRowCount(len(docs))
        for r, doc in enumerate(docs):
            superseded = doc.get("status") == "SUP"
            color = Qt.gray if superseded else Qt.black
            for c, key in enumerate(["doc_no", "title", "rev", "status", "issued", "transmittal"]):
                item = QTableWidgetItem(str(doc.get(key, "")))
                if superseded:
                    item.setForeground(color)
                table.setItem(r, c, item)
        layout.addWidget(table)
        if not docs:
            empty = QLabel("No documents registered for this tag yet.")
            empty.setObjectName("FieldLabel")
            layout.addWidget(empty)
        return frame

    # --------------------------------------------------- revision history
    def _build_revision_history(self):
        self.revisions_frame = QFrame()
        self.revisions_frame.setObjectName("Card")
        self._revisions_layout = QVBoxLayout(self.revisions_frame)
        self._revisions_layout.setContentsMargins(14, 12, 14, 12)
        self._reload_revisions()
        return self.revisions_frame

    def _reload_revisions(self):
        layout = self._revisions_layout
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        kicker = QLabel("REVISION HISTORY — THIS RECORD")
        kicker.setObjectName("SectionLabel")
        layout.addWidget(kicker)

        entries = da.read_revisions(self.key_value)
        if not entries:
            empty = QLabel("Nothing recorded yet - every save from here on writes one line.")
            empty.setObjectName("FieldLabel")
            layout.addWidget(empty)
            return
        for entry in entries:
            row = QHBoxLayout()
            marker = QLabel("■")
            marker.setStyleSheet("color:#1d2d3d;")
            row.addWidget(marker)
            text = QLabel(f"{entry['date']} · {entry['who']}"
                          + (f" · {entry['ecn_id']}" if entry.get("ecn_id") else ""))
            text.setStyleSheet("font-weight:500;")
            row.addWidget(text)
            row.addStretch()
            layout.addLayout(row)
            body = QLabel(entry["what"])
            body.setWordWrap(True)
            body.setObjectName("FieldLabel")
            body.setContentsMargins(20, 0, 0, 6)
            layout.addWidget(body)

    # -------------------------------------------------------------- footer
    def _build_footer(self):
        bar = QFrame()
        bar.setStyleSheet("background:#e9e9ea;border-top:1px solid rgba(29,31,32,.16);")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 8, 16, 8)
        note = QLabel("Every entry is an undo-stack action already recorded - this pane reads it, it does not add bookkeeping.")
        note.setObjectName("FieldLabel")
        layout.addWidget(note)
        layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("Ghost")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        return bar
