# -*- coding: utf-8 -*-
"""
Visual styling for Sensei Index 4.0 - the design system from the redesign
brief (Sensei_Index_-_Accessible_Redesign.dc.html, plate 1k "Foundations").

Three QSS strings, applied once at startup and again whenever Settings >
Appearance changes: LIGHT_QSS, DARK_QSS, HIGH_CONTRAST_QSS. Everything in
the app is styled purely through setObjectName(...) + the selectors below -
there are no hardcoded colors anywhere else in the codebase.

Palette (from 1k's "CONTRAST" and "DARK MAPPING" panels - kept as named
constants so gui_app.py can reach for a color when it needs to paint
something QSS can't reach, e.g. a table cell background):

    LIGHT                              DARK
    ground      #f2f2f3                ground      #1d2d3d
    ink         #1d1f20                ink         #eef6ff  (14.2:1)
    secondary   #5d5d60                secondary   #b5d9fd
    body        #42474b                border      #2c455d
    accent      #416180                accent      #94bce3  (8.6:1)
    accent-2    #5980a6 (focus ring)   focus ring  #94bce3
    navy        #1d2d3d (header/chip)
    highlight   #eef6ff
    chrome      #e9e9ea
    group-alt   #e7e7ea
    zebra       #f5f5f8
    error       #c0392b
    ecn-bg      #fdecea
    track       #d4d4d7
    unchecked   #7a7a7d

Every focusable widget gets the same 2px accent-ring, 2px-offset focus
style (1k, panel 1: "QSS: *:focus { outline: 2px solid #5980a6;
outline-offset: 2px; }") - Qt has no outline-offset, so the closest
faithful mapping is a 2px solid border in the focus color, which is what
every rule below does for :focus.
"""
from paths import FONTS_DIR

BODY_FONT = "Barlow"
# The bundled static TTFs don't carry the name-table entries Qt needs to
# group weights under one family (each weight registers as its own family -
# "Barlow Condensed SemiBold" rather than "Barlow Condensed" at weight 600),
# so QSS references the actual registered semibold family directly - that
# covers the design's overwhelming majority use of condensed text (kickers,
# section labels, table headers, page titles are all weight 600).
HEADING_FONT = "Barlow Condensed SemiBold"
MONO_FONT = "ui-monospace, Menlo, Consolas, monospace"

LIGHT = {
    "ground": "#f2f2f3", "ink": "#1d1f20", "secondary": "#5d5d60", "body": "#42474b",
    "accent": "#416180", "accent2": "#5980a6", "navy": "#1d2d3d",
    "highlight": "#eef6ff", "chrome": "#e9e9ea", "group_alt": "#e7e7ea",
    "zebra": "#f5f5f8", "error": "#c0392b", "ecn_bg": "#fdecea",
    "track": "#d4d4d7", "unchecked": "#7a7a7d", "white": "#ffffff",
    "light_blue": "#b5d9fd", "pale_blue": "#94bce3",
}

DARK = {
    "ground": "#1d2d3d", "ink": "#eef6ff", "secondary": "#b5d9fd", "body": "#cfe3f5",
    "accent": "#94bce3", "accent2": "#94bce3", "navy": "#0f1a24",
    "highlight": "#28405a", "chrome": "#243b52", "group_alt": "#213649",
    "zebra": "#22384e", "error": "#f0b0b0", "ecn_bg": "#3a2226",
    "track": "#2c455d", "unchecked": "#5d7994", "white": "#ffffff",
    "light_blue": "#b5d9fd", "pale_blue": "#94bce3",
}


def load_bundled_fonts():
    """Registers the bundled Barlow / Barlow Condensed weights with Qt so
    the design's typography renders correctly even on a Windows machine
    that's never had these fonts installed. Call once, before building any
    widgets. Silently no-ops per file if it's missing - a missing weight
    just falls back to the nearest one Qt already loaded, never a crash."""
    from PySide6.QtGui import QFontDatabase
    for filename in (
        "Barlow-Regular.ttf", "Barlow-Medium.ttf", "Barlow-SemiBold.ttf",
        "BarlowCondensed-Medium.ttf", "BarlowCondensed-SemiBold.ttf",
    ):
        path = FONTS_DIR / filename
        if path.exists():
            QFontDatabase.addApplicationFont(str(path))


def _build_qss(c, zebra_on=True, contrast_borders=False):
    border_alpha = "1" if contrast_borders else "0.16"
    border_strong = c["ink"] if contrast_borders else f'rgba(29,31,32,{border_alpha})'
    zebra_rule = f'alternate-background-color: {c["zebra"]};' if zebra_on else ""
    return f"""
QMainWindow, QDialog, QWidget {{
    background: {c["ground"]};
    color: {c["ink"]};
    font-family: "{BODY_FONT}", "Segoe UI", sans-serif;
    font-size: 13px;
}}

*:focus {{
    border: 2px solid {c["accent2"]} !important;
}}
QPushButton:focus, QCheckBox:focus, QComboBox:focus {{
    outline: none;
}}

QWidget#ContentArea {{ background: {c["ground"]}; }}

/* ------------------------------------------------------------ app header */
QFrame#AppHeaderBar {{
    background: {c["navy"]};
    border: none;
    min-height: 56px;
    max-height: 56px;
}}
QLabel#AppWordmark {{
    color: #ffffff;
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 17px;
    font-weight: 600;
}}
QLineEdit#GlobalSearch {{
    background: #ffffff;
    color: {c["secondary"]};
    border: 1px solid {c["pale_blue"]};
    border-radius: 0px;
    padding: 8px 12px;
}}
QPushButton#HeaderPillButton {{
    background: transparent;
    color: #ffffff;
    border: 1px solid rgba(255,255,255,.45);
    border-radius: 0px;
    padding: 7px 12px;
    font-size: 12.5px;
    font-weight: 500;
}}
QPushButton#HeaderPillButton:hover {{ background: rgba(255,255,255,.14); }}

/* -------------------------------------------------------- priorities strip */
QFrame#PrioritiesStrip {{
    background: {c["white"] if not contrast_borders else c["ground"]};
    border: none;
    border-bottom: 2px solid {c["navy"]};
    min-height: 40px;
    max-height: 40px;
}}
QLabel#PrioritiesKicker {{
    color: {c["accent"]};
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 11px;
    font-weight: 600;
}}
QPushButton#PriorityChip {{
    background: transparent;
    color: {c["ink"]};
    border: 1px solid rgba(29,31,32,.28);
    border-radius: 0px;
    padding: 6px 11px;
    font-size: 13px;
}}
QPushButton#PriorityChip[urgent="true"] {{
    border-color: {c["navy"]};
    font-weight: 600;
}}
QPushButton#PriorityChip[warning="true"] {{
    border-color: {c["error"]};
    color: {c["error"]};
    font-weight: 500;
}}

/* ------------------------------------------------------------ series rail */
QFrame#SeriesRail {{
    background: {c["white"]};
    border: none;
    border-right: 1px solid {border_strong};
}}
QLabel#RailSectionLabel {{
    color: {c["secondary"]};
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1px;
}}
QPushButton#RailRow {{
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 10px 13px;
    color: {c["ink"]};
    font-size: 14px;
}}
QPushButton#RailRow:hover {{ background: {c["highlight"]}; }}
QPushButton#RailRow[active="true"] {{
    background: {c["highlight"]};
    border-left: 3px solid {c["accent2"]};
    font-weight: 500;
}}
QPushButton#RailFooterButton {{
    background: transparent;
    border: 1px solid rgba(29,31,32,.3);
    padding: 8px 12px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#RailFooterButton:hover {{ background: {c["zebra"]}; }}

/* ------------------------------------------------------------ equip tabs */
QPushButton#EquipTab {{
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 9px 16px;
    color: {c["body"]};
    font-size: 14px;
}}
QPushButton#EquipTab[active="true"] {{
    border-bottom: 3px solid {c["accent2"]};
    color: {c["ink"]};
    font-weight: 500;
}}

/* -------------------------------------------------------------- filter row */
QLineEdit#FilterSearch {{
    background: {c["white"]};
    border: 1px solid rgba(29,31,32,.28);
    border-radius: 0px;
    padding: 7px 11px;
}}
QPushButton#FilterChip {{
    background: {c["navy"]};
    color: #ffffff;
    border: none;
    border-radius: 0px;
    padding: 7px 10px;
    font-size: 12.5px;
    font-weight: 500;
}}
QPushButton#AddFilterChip {{
    background: transparent;
    border: 1px dashed rgba(29,31,32,.35);
    color: {c["body"]};
    padding: 7px 10px;
    font-size: 12.5px;
}}

/* ------------------------------------------------------------- system legend */
QFrame#SystemLegend {{
    background: {c["white"]};
    border: 1px solid rgba(29,31,32,.16);
}}
QLabel#LegendKicker {{
    color: {c["secondary"]};
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 1px;
}}

/* -------------------------------------------------------------- index table */
QTableWidget#IndexTable {{
    background: {c["white"]};
    {zebra_rule}
    gridline-color: rgba(29,31,32,.08);
    border: 1px solid rgba(29,31,32,.16);
    font-size: 12.5px;
}}
QTableWidget#IndexTable::item:selected {{
    background: {c["highlight"]};
    color: {c["ink"]};
}}
QHeaderView::section {{
    background: {c["chrome"]};
    color: {c["body"]};
    border: none;
    border-right: 1px solid rgba(29,31,32,.14);
    border-bottom: 1px solid rgba(29,31,32,.2);
    padding: 5px 7px;
    font-family: "{HEADING_FONT}", sans-serif;
    font-weight: 600;
    font-size: 11.5px;
}}

/* ----------------------------------------------------------- selection bar */
QFrame#SelectionBar {{
    background: {c["navy"]};
    border: none;
    min-height: 44px;
}}
QLabel#SelectionCount {{ color: #ffffff; font-size: 14px; font-weight: 500; }}
QPushButton#SelectionAction {{
    background: transparent;
    color: #ffffff;
    border: 1px solid rgba(255,255,255,.55);
    border-radius: 0px;
    padding: 7px 12px;
    font-size: 12.5px;
}}
QPushButton#SelectionPrimary {{
    background: #ffffff;
    color: {c["navy"]};
    border: none;
    border-radius: 0px;
    padding: 7px 12px;
    font-size: 12.5px;
    font-weight: 600;
}}
QPushButton#SelectionDanger {{
    background: transparent;
    color: #ffd9d9;
    border: 1px solid #f0b0b0;
    border-radius: 0px;
    padding: 7px 12px;
    font-size: 12.5px;
}}

/* --------------------------------------------------------------- status bar */
QStatusBar {{
    background: {c["chrome"]};
    color: {c["body"]};
    border-top: 1px solid rgba(29,31,32,.16);
    font-size: 12px;
}}

/* ------------------------------------------------------------------ text */
QLabel#PageTitle {{
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 27px;
    font-weight: 600;
    color: {c["ink"]};
}}
QLabel#PageSubtitle {{ font-size: 12.5px; color: {c["body"]}; }}
QLabel#SectionLabel {{
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 11px;
    font-weight: 600;
    color: {c["accent"]};
    letter-spacing: 1px;
}}
QLabel#Breadcrumb {{ font-size: 12.5px; color: {c["secondary"]}; }}
QLabel#FieldLabel {{ color: {c["secondary"]}; font-size: 12px; }}
QLabel#RequiredLabel {{ color: {c["accent"]}; font-size: 12px; font-weight: 600; }}
QLabel#SigOk {{ color: {c["accent"]}; font-weight: 600; }}
QLabel#SigWarn {{ color: {c["error"]}; font-weight: 600; }}
QLabel#DocChipIFC {{ background: {c["highlight"]}; color: {c["navy"]}; font-weight: 600; padding: 3px 6px; font-size: 10.5px; }}
QLabel#DocChipIFR {{ background: {c["group_alt"]}; color: {c["body"]}; font-weight: 600; padding: 3px 6px; font-size: 10.5px; }}
QLabel#DocChipECN {{ background: {c["ecn_bg"]}; color: {c["error"]}; font-weight: 600; padding: 3px 6px; font-size: 10.5px; }}
QLabel#DocChipSUP {{ background: {c["group_alt"]}; color: {c["secondary"]}; font-weight: 600; padding: 3px 6px; font-size: 10.5px; }}

/* ------------------------------------------------------------------ card */
QFrame#Card {{
    background: {c["white"]};
    border: 1px solid rgba(29,31,32,.16);
}}
QLabel#StatNumber {{
    font-family: "{HEADING_FONT}", sans-serif;
    font-size: 30px;
    font-weight: 600;
    color: {c["ink"]};
}}
QLabel#StatLabel {{ font-size: 12px; color: {c["secondary"]}; }}

/* -------------------------------------------------------------- controls */
QLineEdit, QComboBox, QTextEdit, QSpinBox, QDateEdit {{
    background: {c["white"]};
    color: {c["ink"]};
    border: 1px solid rgba(29,31,32,.28);
    border-radius: 0px;
    padding: 6px 9px;
    selection-background-color: {c["accent2"]};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {c["accent2"]};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QCheckBox, QRadioButton {{ spacing: 8px; color: {c["ink"]}; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {c["unchecked"]};
    background: {c["white"]};
}}
QCheckBox::indicator {{ border-radius: 0px; }}
QRadioButton::indicator {{ border-radius: 8px; }}
QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {c["accent2"]}; }}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {c["accent"]}; border-color: {c["accent"]};
}}
QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
    background: {c["zebra"]}; border-color: rgba(29,31,32,.2);
}}
QTableView::indicator, QAbstractItemView::indicator {{
    width: 16px; height: 16px;
    border: 2px solid {c["unchecked"]};
    background: {c["white"]};
}}
QTableView::indicator:checked, QAbstractItemView::indicator:checked {{
    background: {c["accent"]}; border-color: {c["accent"]};
}}
QGroupBox {{
    border: 1px solid rgba(29,31,32,.2);
    border-radius: 0px;
    margin-top: 14px;
    padding-top: 14px;
    font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}

/* --------------------------------------------------------------- buttons */
QPushButton {{
    background: {c["white"]};
    color: {c["ink"]};
    border: 1px solid rgba(29,31,32,.3);
    border-radius: 0px;
    padding: 9px 16px;
    font-size: 13.5px;
}}
QPushButton:hover {{ background: {c["zebra"]}; }}
QPushButton:pressed {{ background: {c["group_alt"]}; }}
QPushButton#Primary {{
    background: {c["accent"]};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {c["navy"]}; }}
QPushButton#Success {{ background: #2e6b48; color: #ffffff; border: none; font-weight: 600; }}
QPushButton#Success:hover {{ background: #245939; }}
QPushButton#Danger {{
    background: {c["white"]}; color: {c["error"]};
    border: 1px solid #e3b0a8; font-weight: 600;
}}
QPushButton#Danger:hover {{ background: {c["ecn_bg"]}; }}
QPushButton#Ghost {{ background: transparent; border: 1px solid rgba(29,31,32,.3); color: {c["ink"]}; }}
QPushButton#Ghost:hover {{ background: {c["zebra"]}; }}
QPushButton#Link {{
    background: transparent; border: none; color: {c["accent"]};
    text-decoration: underline; padding: 4px 2px;
}}
QPushButton#Link:hover {{ color: {c["navy"]}; }}

/* -------------------------------------------------------------- scroll */
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: {c["unchecked"]}; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0px; }}

QMessageBox {{ background: {c["ground"]}; color: {c["ink"]}; }}
"""


LIGHT_QSS = _build_qss(LIGHT)
DARK_QSS = _build_qss(DARK)
HIGH_CONTRAST_QSS = _build_qss(LIGHT, zebra_on=False, contrast_borders=True)
