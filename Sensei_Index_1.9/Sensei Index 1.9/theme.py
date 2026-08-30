# -*- coding: utf-8 -*-
"""
Visual styling for InstINDEX (PySide6 build).

gui_app.py only ever needs two things from this file: LIGHT_QSS and
DARK_QSS, applied once at startup and again whenever the user flips the
Settings > Theme radio buttons (see apply_theme() / _set_theme() in
gui_app.py). Everything else in the app is styled purely through
setObjectName(...) + the selectors below - there are no hardcoded colors
anywhere else in the codebase, so this one file controls the entire look.

Object names this stylesheet targets (all defined in gui_app.py):
    Sidebar, SidebarTitle, SidebarSubtitle, SidebarTree, SidebarFooterButton
    ContentArea, PageTitle, PageSubtitle, SectionLabel, Breadcrumb
    Card, StatNumber, StatLabel
    FieldLabel, RequiredLabel, SigOk, SigWarn
    Primary, Ghost, Link, Success, Danger   (QPushButton variants)
"""

LIGHT_QSS = """
QMainWindow, QDialog, QWidget {
    background: #f4f5f7;
    color: #1f2430;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget#ContentArea {
    background: #f4f5f7;
}

/* ---------------------------------------------------------------- sidebar */
QFrame#Sidebar {
    background: #ffffff;
    border: none;
    border-right: 1px solid #e2e5ec;
}
QLabel#SidebarTitle {
    color: #1f2430;
    font-size: 20px;
    font-weight: 700;
    padding: 20px 18px 0px 18px;
}
QLabel#SidebarSubtitle {
    color: #6b7285;
    font-size: 11px;
    padding: 2px 18px 14px 18px;
}
QTreeWidget#SidebarTree {
    background: #ffffff;
    border: none;
    color: #3a4258;
    outline: none;
    padding: 4px 8px;
}
QTreeWidget#SidebarTree::item {
    padding: 7px 6px;
    border-radius: 6px;
}
QTreeWidget#SidebarTree::item:hover {
    background: #eef0f4;
}
QTreeWidget#SidebarTree::item:selected {
    background: #3a63e0;
    color: #ffffff;
}
QTreeWidget#SidebarTree::branch {
    background: #ffffff;
}
QPushButton#SidebarFooterButton {
    background: transparent;
    color: #3a4258;
    border: none;
    border-top: 1px solid #e2e5ec;
    border-radius: 0px;
    text-align: left;
    padding: 12px 18px;
    font-size: 12px;
}
QPushButton#SidebarFooterButton:hover {
    background: #eef0f4;
    color: #1f2430;
}

/* ------------------------------------------------------------------ text */
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #1f2430;
}
QLabel#PageSubtitle {
    font-size: 12.5px;
    color: #6b7285;
}
QLabel#SectionLabel {
    font-size: 13px;
    font-weight: 700;
    color: #3a4258;
    padding-top: 6px;
}
QLabel#Breadcrumb {
    font-size: 12px;
    color: #6b7285;
}
QLabel#FieldLabel {
    color: #6b7285;
    font-size: 12px;
}
QLabel#RequiredLabel {
    color: #c0392b;
    font-size: 12px;
    font-weight: 600;
}
QLabel#SigOk {
    color: #1e8e5a;
    font-weight: 600;
}
QLabel#SigWarn {
    color: #b8860b;
    font-weight: 600;
}

/* ------------------------------------------------------------------ card */
QFrame#Card {
    background: #ffffff;
    border: 1px solid #e2e5ec;
    border-radius: 10px;
}
QLabel#StatNumber {
    font-size: 30px;
    font-weight: 800;
    color: #1f2430;
}
QLabel#StatLabel {
    font-size: 12px;
    color: #6b7285;
}

/* -------------------------------------------------------------- controls */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDateEdit {
    background: #ffffff;
    border: 1px solid #d6dae3;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #3a63e0;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #3a63e0;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    color: #1f2430;
}
/* Explicit indicator painting, on purpose - QSS + the native Windows style
   are known to fight over who draws the checkmark glyph, and the usual
   result is a checkbox that LOOKS unchecked even when it's checked (the
   click registers, the box just never visibly fills in). Taking over the
   whole indicator - unchecked is a plain outline, checked is a solid fill -
   sidesteps that fight entirely: there's no glyph to fail to render, the
   state is the fill itself, so it's unmistakable on every platform. */
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid #9aa1b5;
    background: #ffffff;
}
QCheckBox::indicator {
    border-radius: 4px;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #3a63e0;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #3a63e0;
    border-color: #3a63e0;
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background: #eceef2;
    border-color: #d9dbe2;
}
/* Color-coded status checkboxes on the Index table - checked fill matches
   the row-number highlight it drives, so the checkbox and the row color
   always agree at a glance. */
QCheckBox#SubmittedCheck::indicator:checked {
    background: #d9a441;
    border-color: #d9a441;
}
QCheckBox#AcceptedCheck::indicator:checked {
    background: #1e8e5a;
    border-color: #1e8e5a;
}
QCheckBox#ExportCheck::indicator:checked {
    background: #6b7285;
    border-color: #6b7285;
}
/* Item-view (table/tree) checkboxes - a different QSS sub-control from
   QCheckBox::indicator, styled the same way for the same reason. */
QTableView::indicator, QAbstractItemView::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #9aa1b5;
    border-radius: 4px;
    background: #ffffff;
}
QTableView::indicator:checked, QAbstractItemView::indicator:checked {
    background: #3a63e0;
    border-color: #3a63e0;
}
QGroupBox {
    border: 1px solid #e2e5ec;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

/* --------------------------------------------------------------- tables */
QTableWidget, QTableView, QTreeWidget {
    background: #ffffff;
    alternate-background-color: #f7f8fa;
    gridline-color: #e6e8ee;
    border: 1px solid #e2e5ec;
    border-radius: 6px;
}
QHeaderView::section {
    background: #eef0f4;
    color: #3a4258;
    border: none;
    border-bottom: 1px solid #dde0e8;
    padding: 6px 8px;
    font-weight: 600;
}

/* -------------------------------------------------------------- buttons */
QPushButton {
    background: #eceef2;
    color: #1f2430;
    border: 1px solid #d6dae3;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover {
    background: #e2e5ec;
}
QPushButton:pressed {
    background: #d6dae3;
}
QPushButton#Primary {
    background: #3a63e0;
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton#Primary:hover { background: #3457c9; }
QPushButton#Primary:pressed { background: #2c49ab; }

QPushButton#Success {
    background: #1e8e5a;
    color: #ffffff;
    border: none;
    font-weight: 600;
}
QPushButton#Success:hover { background: #197a4d; }

QPushButton#Danger {
    background: #ffffff;
    color: #c0392b;
    border: 1px solid #e3b0a8;
    font-weight: 600;
}
QPushButton#Danger:hover { background: #fdecea; }

QPushButton#Ghost {
    background: transparent;
    border: 1px solid #d6dae3;
    color: #1f2430;
}
QPushButton#Ghost:hover { background: #eceef2; }

QPushButton#Link {
    background: transparent;
    border: none;
    color: #3a63e0;
    text-decoration: underline;
    padding: 4px 2px;
}
QPushButton#Link:hover { color: #2c49ab; }

QPushButton#FilterChip {
    background: #eceef2;
    color: #3a4258;
    border: 1px solid #d6dae3;
    border-radius: 13px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton#FilterChip:hover { background: #e2e5ec; }
QPushButton#FilterChip:checked {
    background: #3a63e0;
    color: #ffffff;
    border: 1px solid #3a63e0;
}

QWidget#Toast {
    background: #1f2430;
    border-radius: 8px;
}
QLabel#ToastLabel {
    color: #ffffff;
    font-weight: 600;
}

/* -------------------------------------------------------------- scroll */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #c7ccd8;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }

QMessageBox { background: #f4f5f7; }
"""

DARK_QSS = """
QMainWindow, QDialog, QWidget {
    background: #1a1b26;
    color: #c0caf5;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}

QWidget#ContentArea {
    background: #1a1b26;
}

/* ---------------------------------------------------------------- sidebar */
QFrame#Sidebar {
    background: #16161e;
    border: none;
}
QLabel#SidebarTitle {
    color: #ffffff;
    font-size: 20px;
    font-weight: 700;
    padding: 20px 18px 0px 18px;
}
QLabel#SidebarSubtitle {
    color: #565f89;
    font-size: 11px;
    padding: 2px 18px 14px 18px;
}
QTreeWidget#SidebarTree {
    background: #16161e;
    border: none;
    color: #a9b1d6;
    outline: none;
    padding: 4px 8px;
}
QTreeWidget#SidebarTree::item {
    padding: 7px 6px;
    border-radius: 6px;
}
QTreeWidget#SidebarTree::item:hover {
    background: #24283b;
}
QTreeWidget#SidebarTree::item:selected {
    background: #7aa2f7;
    color: #16161e;
}
QTreeWidget#SidebarTree::branch {
    background: #16161e;
}
QPushButton#SidebarFooterButton {
    background: transparent;
    color: #a9b1d6;
    border: none;
    border-top: 1px solid #24283b;
    border-radius: 0px;
    text-align: left;
    padding: 12px 18px;
    font-size: 12px;
}
QPushButton#SidebarFooterButton:hover {
    background: #24283b;
    color: #ffffff;
}

/* ------------------------------------------------------------------ text */
QLabel#PageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #c0caf5;
}
QLabel#PageSubtitle {
    font-size: 12.5px;
    color: #7982a9;
}
QLabel#SectionLabel {
    font-size: 13px;
    font-weight: 700;
    color: #a9b1d6;
    padding-top: 6px;
}
QLabel#Breadcrumb {
    font-size: 12px;
    color: #7982a9;
}
QLabel#FieldLabel {
    color: #7982a9;
    font-size: 12px;
}
QLabel#RequiredLabel {
    color: #f7768e;
    font-size: 12px;
    font-weight: 600;
}
QLabel#SigOk {
    color: #9ece6a;
    font-weight: 600;
}
QLabel#SigWarn {
    color: #e0af68;
    font-weight: 600;
}

/* ------------------------------------------------------------------ card */
QFrame#Card {
    background: #24283b;
    border: 1px solid #2f3549;
    border-radius: 10px;
}
QLabel#StatNumber {
    font-size: 30px;
    font-weight: 800;
    color: #c0caf5;
}
QLabel#StatLabel {
    font-size: 12px;
    color: #7982a9;
}

/* -------------------------------------------------------------- controls */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDateEdit {
    background: #1f2335;
    color: #c0caf5;
    border: 1px solid #2f3549;
    border-radius: 6px;
    padding: 6px 8px;
    selection-background-color: #7aa2f7;
    selection-color: #16161e;
}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
    border: 1px solid #7aa2f7;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QComboBox QAbstractItemView {
    background: #1f2335;
    color: #c0caf5;
    selection-background-color: #7aa2f7;
    selection-color: #16161e;
}
QCheckBox, QRadioButton {
    spacing: 8px;
    color: #c0caf5;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 17px;
    height: 17px;
    border: 2px solid #565f89;
    background: #1f2335;
}
QCheckBox::indicator {
    border-radius: 4px;
}
QRadioButton::indicator {
    border-radius: 9px;
}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {
    border-color: #7aa2f7;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background: #7aa2f7;
    border-color: #7aa2f7;
}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {
    background: #24283b;
    border-color: #363b54;
}
QCheckBox#SubmittedCheck::indicator:checked {
    background: #e0af68;
    border-color: #e0af68;
}
QCheckBox#AcceptedCheck::indicator:checked {
    background: #9ece6a;
    border-color: #9ece6a;
}
QCheckBox#ExportCheck::indicator:checked {
    background: #a9b1d6;
    border-color: #a9b1d6;
}
QTableView::indicator, QAbstractItemView::indicator {
    width: 16px;
    height: 16px;
    border: 2px solid #565f89;
    border-radius: 4px;
    background: #1f2335;
}
QTableView::indicator:checked, QAbstractItemView::indicator:checked {
    background: #7aa2f7;
    border-color: #7aa2f7;
}
QGroupBox {
    border: 1px solid #2f3549;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: 600;
    color: #a9b1d6;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}

/* --------------------------------------------------------------- tables */
QTableWidget, QTableView, QTreeWidget {
    background: #1f2335;
    alternate-background-color: #24283b;
    gridline-color: #2f3549;
    color: #c0caf5;
    border: 1px solid #2f3549;
    border-radius: 6px;
}
QHeaderView::section {
    background: #24283b;
    color: #a9b1d6;
    border: none;
    border-bottom: 1px solid #2f3549;
    padding: 6px 8px;
    font-weight: 600;
}

/* -------------------------------------------------------------- buttons */
QPushButton {
    background: #2a2e42;
    color: #c0caf5;
    border: 1px solid #363b54;
    border-radius: 6px;
    padding: 7px 14px;
}
QPushButton:hover {
    background: #353a54;
}
QPushButton:pressed {
    background: #24283b;
}
QPushButton#Primary {
    background: #7aa2f7;
    color: #16161e;
    border: none;
    font-weight: 600;
}
QPushButton#Primary:hover { background: #89b4fa; }
QPushButton#Primary:pressed { background: #6690e6; }

QPushButton#Success {
    background: #9ece6a;
    color: #16161e;
    border: none;
    font-weight: 600;
}
QPushButton#Success:hover { background: #aede7c; }

QPushButton#Danger {
    background: #2a2e42;
    color: #f7768e;
    border: 1px solid #4a3040;
    font-weight: 600;
}
QPushButton#Danger:hover { background: #33283a; }

QPushButton#Ghost {
    background: transparent;
    border: 1px solid #363b54;
    color: #c0caf5;
}
QPushButton#Ghost:hover { background: #24283b; }

QPushButton#Link {
    background: transparent;
    border: none;
    color: #7aa2f7;
    text-decoration: underline;
    padding: 4px 2px;
}
QPushButton#Link:hover { color: #89b4fa; }

QPushButton#FilterChip {
    background: #262b3d;
    color: #c0caf5;
    border: 1px solid #363b54;
    border-radius: 13px;
    padding: 4px 12px;
    font-weight: 600;
}
QPushButton#FilterChip:hover { background: #2f3550; }
QPushButton#FilterChip:checked {
    background: #7aa2f7;
    color: #16161e;
    border: 1px solid #7aa2f7;
}

QWidget#Toast {
    background: #0d0e14;
    border-radius: 8px;
    border: 1px solid #363b54;
}
QLabel#ToastLabel {
    color: #ffffff;
    font-weight: 600;
}

/* -------------------------------------------------------------- scroll */
QScrollBar:vertical {
    background: transparent;
    width: 10px;
}
QScrollBar::handle:vertical {
    background: #363b54;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }

QMessageBox { background: #1a1b26; color: #c0caf5; }
"""
