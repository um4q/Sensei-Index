# -*- coding: utf-8 -*-
"""
Sensei Index - Access Edition. A PySide6 front end for SenseiIndex.accdb -
the same idea as the Excel edition's own gui_app.py (one window, sidebar
navigation, focused Add/Edit dialogs), but covering the core workflow
only: pick a zone/series, browse its equipment by kind, add/edit/delete
rows, check installed/submitted/accepted status, generate a filled PDF.
See README_ACCESS_EDITION.txt's own "what's not here yet" section for
what this deliberately doesn't cover (yet) compared to the Excel
edition's own, much larger gui_app.py - the Master List import wizard,
datasheet-PDF import, progress reports, and search index chief among
them.

WHY A GENERIC ROW-EDIT FORM INSTEAD OF gui_app.py's OWN HAND-LAID-OUT
DIALOGS
------------------------------------------------------------------------
gui_app.py's own edit dialogs are hand-built per section, matching each
form's real printed layout closely (grouped fields, specific widget
choices, etc.) - a lot of genuinely good, deliberate UI work that took
this whole app's own development to build out. Reproducing that same
level of polish for all 9 equipment kinds here would be its own
multi-session effort. This edition's own RowEditDialog instead builds
one straightforward form directly from each schema's own FIELDS list
(grouped by section, in schema order) - plainer, but correct and
complete for every field on every kind with no per-kind hand-authoring,
and a reasonable foundation to make more polished later without
changing anything about the DATA layer underneath it.
"""
import sys
import datetime
import traceback
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QTextEdit, QTreeWidget,
    QTreeWidgetItem, QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QMessageBox, QInputDialog, QCheckBox, QSplitter, QStatusBar, QAbstractItemView,
)

HERE = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) \
    else Path(__file__).resolve().parent
EXCEL_EDITION_DIR = HERE.parent / "Sensei Index 2.9"
if str(EXCEL_EDITION_DIR) not in sys.path:
    sys.path.insert(0, str(EXCEL_EDITION_DIR))

from theme import LIGHT_QSS, DARK_QSS  # noqa: E402  (reused unchanged - plain QSS strings)

import access_db as db  # noqa: E402
import access_data_access as da  # noqa: E402
import access_electrical_data_access as eda  # noqa: E402

APP_TITLE = "Sensei Index - Access Edition"

DOMAINS = {
    "Instrumentation": {"module": da, "types": da.EQUIPMENT_TYPES, "parent_word": "Series"},
    "Electrical": {"module": eda, "types": eda.ELECTRICAL_EQUIPMENT_TYPES, "parent_word": "Zone"},
}


def _install_crash_handler():
    """Same reasoning as gui_app.py's own identical function - a
    windowed exe has no console, so this writes crash_log.txt next to
    the app and shows a message box, rather than silently vanishing."""
    def _handle(exc_type, exc_value, exc_tb):
        text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(HERE / "crash_log.txt", "a", encoding="utf-8") as fh:
                fh.write(f"\n{'=' * 70}\n{stamp}\n{text}")
        except Exception:
            pass
        try:
            app = QApplication.instance()
            if app is not None:
                QMessageBox.critical(
                    None, f"{APP_TITLE} - Unexpected Error",
                    "Something went wrong and the app needs to close.\n\n"
                    "The full error has been saved to crash_log.txt, in the "
                    "same folder as the app.\n\n"
                    f"{text[-1500:]}",
                )
        except Exception:
            pass
        sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _handle


class RowEditDialog(QDialog):
    """One form field per schema field, grouped by section, in schema
    order - see this module's own docstring for why this is generic
    rather than hand-laid-out per equipment kind."""

    def __init__(self, parent, fields, values, title):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(640, 720)
        self._widgets = {}

        outer = QVBoxLayout(self)
        form_container = QWidget()
        form = QFormLayout(form_container)
        form.setLabelAlignment(Qt.AlignRight)

        current_section = None
        for field in fields:
            if field["section"] != current_section:
                current_section = field["section"]
                section_label = QLabel(f"— {current_section.replace('_', ' ').title()} —")
                section_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
                form.addRow(section_label)

            value = values.get(field["id"], "") or ""
            if field["ftype"] == "multiline":
                widget = QTextEdit()
                widget.setPlainText(str(value))
                widget.setFixedHeight(70)
            elif field["ftype"] == "choice":
                widget = QComboBox()
                widget.addItem("")
                widget.addItems(field.get("choices") or [])
                idx = widget.findText(str(value))
                widget.setCurrentIndex(idx if idx >= 0 else 0)
            else:
                widget = QLineEdit(str(value))
            self._widgets[field["id"]] = (field["ftype"], widget)
            form.addRow(field["label"] + ":", widget)

        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(form_container)
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        button_row = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addStretch()
        button_row.addWidget(cancel_btn)
        button_row.addWidget(save_btn)
        outer.addLayout(button_row)

    def values(self):
        result = {}
        for field_id, (ftype, widget) in self._widgets.items():
            if ftype == "multiline":
                result[field_id] = widget.toPlainText().strip()
            elif ftype == "choice":
                result[field_id] = widget.currentText().strip()
            else:
                result[field_id] = widget.text().strip()
        return result


class MainWindow(QMainWindow):
    def __init__(self, conn):
        super().__init__()
        self.conn = conn
        self.setWindowTitle(APP_TITLE)
        self.resize(1200, 800)

        self._domain_name = "Electrical"
        self._parent_value = None  # selected zone name / series number
        self._equip_key = None

        splitter = QSplitter()
        self.setCentralWidget(splitter)

        # --------------------------------------------------------- Sidebar
        sidebar = QWidget()
        sidebar_layout = QVBoxLayout(sidebar)

        domain_row = QHBoxLayout()
        for name in DOMAINS:
            btn = QPushButton(name)
            btn.clicked.connect(lambda checked=False, n=name: self._switch_domain(n))
            domain_row.addWidget(btn)
        sidebar_layout.addLayout(domain_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self._on_tree_item_clicked)
        sidebar_layout.addWidget(self.tree)

        add_parent_btn = QPushButton("Add Zone/Series…")
        add_parent_btn.clicked.connect(self._add_parent)
        sidebar_layout.addWidget(add_parent_btn)

        splitter.addWidget(sidebar)

        # --------------------------------------------------------- Main area
        main_area = QWidget()
        main_layout = QVBoxLayout(main_area)

        toolbar = QHBoxLayout()
        self.add_row_btn = QPushButton("Add Row")
        self.add_row_btn.clicked.connect(self._add_row)
        self.edit_row_btn = QPushButton("Edit Row")
        self.edit_row_btn.clicked.connect(self._edit_selected_row)
        self.delete_row_btn = QPushButton("Delete Row")
        self.delete_row_btn.clicked.connect(self._delete_selected_row)
        self.preview_btn = QPushButton("Generate PDF")
        self.preview_btn.clicked.connect(self._generate_pdf)
        for b in (self.add_row_btn, self.edit_row_btn, self.delete_row_btn, self.preview_btn):
            toolbar.addWidget(b)
        toolbar.addStretch()
        main_layout.addLayout(toolbar)

        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        main_layout.addWidget(self.table)

        splitter.addWidget(main_area)
        splitter.setSizes([260, 940])

        self.setStatusBar(QStatusBar())
        self._refresh_tree()

    # ------------------------------------------------------------- Domain

    def _switch_domain(self, name):
        self._domain_name = name
        self._parent_value = None
        self._equip_key = None
        self._refresh_tree()
        self.table.clear()
        self.table.setRowCount(0)

    def _domain_info(self):
        return DOMAINS[self._domain_name]

    # --------------------------------------------------------------- Tree

    def _refresh_tree(self):
        self.tree.clear()
        info = self._domain_info()
        module = info["module"]
        if self._domain_name == "Instrumentation":
            parents = module.list_series(self.conn)
        else:
            parents = module.list_zones(self.conn)
        for parent in parents:
            parent_item = QTreeWidgetItem([str(parent)])
            parent_item.setData(0, Qt.UserRole, ("parent", parent))
            self.tree.addTopLevelItem(parent_item)
            for equip_key, entry in info["types"].items():
                child = QTreeWidgetItem([entry["table_name"]])
                child.setData(0, Qt.UserRole, ("kind", parent, equip_key))
                parent_item.addChild(child)

    def _on_tree_item_clicked(self, item, _col):
        data = item.data(0, Qt.UserRole)
        if data[0] != "kind":
            return
        _, parent_value, equip_key = data
        self._parent_value = parent_value
        self._equip_key = equip_key
        self._refresh_table()

    def _add_parent(self):
        word = self._domain_info()["parent_word"]
        text, ok = QInputDialog.getText(self, f"Add {word}", f"{word} name/number:")
        if not ok or not text.strip():
            return
        module = self._domain_info()["module"]
        try:
            if self._domain_name == "Instrumentation":
                module.add_series(self.conn, int(text.strip()), text.strip())
            else:
                module.add_zone(self.conn, text.strip())
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            return
        self._refresh_tree()

    # -------------------------------------------------------------- Table

    def _refresh_table(self):
        if self._equip_key is None:
            return
        info = self._domain_info()
        module = info["module"]
        entry = info["types"][self._equip_key]
        rows = module.read_index_rows(self.conn, self._parent_value, self._equip_key)

        summary_ids = [entry["key_field"]] + [f["id"] for f in entry["fields"][:4]
                                               if f["id"] != entry["key_field"]][:3]
        self.table.setColumnCount(len(summary_ids) + 1)
        self.table.setHorizontalHeaderLabels(["id"] + summary_ids)
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table.setItem(r, 0, QTableWidgetItem(str(row["id"])))
            for c, fid in enumerate(summary_ids, start=1):
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(fid, "") or "")))
        self.statusBar().showMessage(
            f"{entry['table_name']} — {self._parent_value} — {len(rows)} row(s)"
        )

    def _selected_row_id(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_idx = selected[0].row()
        return int(self.table.item(row_idx, 0).text())

    # ----------------------------------------------------------- Row CRUD

    def _add_row(self):
        if self._equip_key is None:
            QMessageBox.information(self, "Pick a kind", "Select a zone/series and equipment kind first.")
            return
        info = self._domain_info()
        module = info["module"]
        entry = info["types"][self._equip_key]
        row_id = module.find_first_blank_row(self.conn, self._parent_value, self._equip_key)
        dialog = RowEditDialog(self, entry["fields"], {}, f"Add {entry['table_name']} row")
        if dialog.exec() == QDialog.Accepted:
            values = dialog.values()
            key_field = entry["key_field"]
            if values.get(key_field):
                dupe = module.find_duplicate_row(self.conn, self._parent_value, self._equip_key,
                                                  values[key_field], exclude_row=row_id)
                if dupe is not None:
                    QMessageBox.warning(
                        self, "Possible duplicate",
                        f"Another row already has {key_field} = {values[key_field]!r}. "
                        "Saved anyway - this is advisory, not blocked.",
                    )
            module.save_row(self.conn, self._parent_value, self._equip_key, row_id, values)
        self._refresh_table()

    def _edit_selected_row(self):
        row_id = self._selected_row_id()
        if row_id is None:
            return
        info = self._domain_info()
        module = info["module"]
        entry = info["types"][self._equip_key]
        current = module.read_full_row(self.conn, self._parent_value, self._equip_key, row_id)
        dialog = RowEditDialog(self, entry["fields"], current, f"Edit {entry['table_name']} row")
        if dialog.exec() == QDialog.Accepted:
            module.save_row(self.conn, self._parent_value, self._equip_key, row_id, dialog.values())
        self._refresh_table()

    def _delete_selected_row(self):
        row_id = self._selected_row_id()
        if row_id is None:
            return
        if QMessageBox.question(self, "Delete row", "Delete this row? This cannot be undone.") \
                != QMessageBox.Yes:
            return
        module = self._domain_info()["module"]
        module.delete_rows(self.conn, self._parent_value, self._equip_key, [row_id])
        self._refresh_table()

    def _generate_pdf(self):
        row_id = self._selected_row_id()
        if row_id is None:
            QMessageBox.information(self, "Pick a row", "Select a row first.")
            return
        module = self._domain_info()["module"]
        try:
            out_path = module.generate_preview_pdf(self.conn, self._parent_value, self._equip_key, row_id)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        module_root = module if self._domain_name == "Instrumentation" else module
        try:
            import data_access as legacy_da
            legacy_da.open_file(out_path)
        except Exception:
            QMessageBox.information(self, "PDF generated", f"Saved to:\n{out_path}")


def main():
    _install_crash_handler()
    app = QApplication(sys.argv)
    app.setStyleSheet(LIGHT_QSS)

    try:
        conn = db.get_connection()
    except FileNotFoundError as exc:
        QMessageBox.critical(
            None, f"{APP_TITLE} - No database found", str(exc),
        )
        sys.exit(1)

    win = MainWindow(conn)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
