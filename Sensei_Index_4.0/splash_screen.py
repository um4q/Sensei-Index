# -*- coding: utf-8 -*-
"""
The startup splash - plate 5a of the redesign brief: "what the .bat file's
black console should have been."

Pure UI, no business logic - bootstrap.py drives it by calling set_step()
as each real startup signal actually happens (package check, writability
check, workbook load, index build). Nothing here is a fake timer.
"""
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QPlainTextEdit, QApplication,
)

from theme import LIGHT

STEP_LABELS = [
    "Required packages present",
    "Folder is writable",
    "Reading the workbook…",
    "Building the index",
]


class _StepRow(QWidget):
    def __init__(self, label_text):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.icon = QLabel()
        self.icon.setFixedSize(15, 15)
        layout.addWidget(self.icon)

        self.label = QLabel(label_text)
        self.label.setStyleSheet(f"font:400 13px 'Barlow',sans-serif;color:{LIGHT['ink']};")
        layout.addWidget(self.label, stretch=1)

        self.time_label = QLabel("")
        self.time_label.setStyleSheet(f"font:400 12px 'Barlow',sans-serif;color:{LIGHT['secondary']};")
        layout.addWidget(self.time_label)

        self.set_state("pending")

    def set_state(self, state, detail=None, elapsed=None):
        if state == "pending":
            self.icon.setStyleSheet(
                "border:2px dashed #b7b7ba;background:#fff;")
            self.icon.setText("")
            self.label.setStyleSheet(f"font:400 13px 'Barlow',sans-serif;color:{LIGHT['secondary']};")
        elif state == "active":
            self.icon.setStyleSheet(
                f"border:2px solid {LIGHT['accent2']};background:{LIGHT['highlight']};")
            self.icon.setText("")
            self.label.setStyleSheet(f"font:400 13px 'Barlow',sans-serif;color:{LIGHT['ink']};")
        elif state == "done":
            self.icon.setStyleSheet(f"background:{LIGHT['navy']};color:#fff;")
            self.icon.setText("✓")
            self.icon.setAlignment(Qt.AlignCenter)
            self.icon.setStyleSheet(
                f"background:{LIGHT['navy']};color:#fff;font:600 10px 'Barlow',sans-serif;")
            self.label.setStyleSheet(f"font:400 13px 'Barlow',sans-serif;color:{LIGHT['ink']};")
        elif state == "error":
            self.icon.setStyleSheet(f"background:{LIGHT['error']};")
            self.icon.setText("!")
            self.icon.setAlignment(Qt.AlignCenter)
            self.icon.setStyleSheet(
                f"background:{LIGHT['error']};color:#fff;font:700 10px 'Barlow',sans-serif;")
            self.label.setText(detail or self.label.text())
            self.label.setStyleSheet(f"font:500 13px 'Barlow',sans-serif;color:{LIGHT['error']};")
        if elapsed is not None:
            self.time_label.setText(f"{elapsed:.1f}s")


class SplashScreen(QWidget):
    """Frameless, borderless, takes no keyboard input (Esc does nothing -
    the whole point is nothing can go wrong by pressing a key while it's
    up). Shown before anything heavy is imported."""

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(660, 400)
        self.setStyleSheet(f"background:{LIGHT['white']};")
        self._log_lines = []
        self._error = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.setLayout(outer)
        frame = QFrame()
        frame.setStyleSheet(f"border:1px solid rgba(29,31,32,.3);background:{LIGHT['white']};")
        outer.addWidget(frame)
        root = QVBoxLayout(frame)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- header band ----
        header = QFrame()
        header.setStyleSheet(f"background:{LIGHT['navy']};")
        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(26, 22, 26, 22)
        hlayout.setSpacing(18)
        logo = QLabel()
        pix = QPixmap("assets/oathplatehelm.png")
        if not pix.isNull():
            logo.setPixmap(pix.scaledToHeight(58, Qt.SmoothTransformation))
        hlayout.addWidget(logo)
        title_col = QVBoxLayout()
        title_col.setSpacing(4)
        title = QLabel("SENSEI INDEX 3.0")
        title.setStyleSheet("font:600 30px 'Barlow Condensed SemiBold','Barlow Condensed',sans-serif;"
                             "letter-spacing:1px;color:#fff;")
        title_col.addWidget(title)
        subtitle = QLabel("K1B Equipment Tracker · Instrumentation QA/QC")
        subtitle.setStyleSheet(f"font:400 13px 'Barlow',sans-serif;color:{LIGHT['light_blue']};")
        title_col.addWidget(subtitle)
        hlayout.addLayout(title_col)
        hlayout.addStretch()
        root.addWidget(header)

        # ---- body ----
        body = QVBoxLayout()
        body.setContentsMargins(26, 20, 26, 20)
        body.setSpacing(14)

        prog_row = QHBoxLayout()
        self.progress_label = QLabel("Starting…")
        self.progress_label.setStyleSheet(f"font:500 14px 'Barlow',sans-serif;color:{LIGHT['ink']};")
        prog_row.addWidget(self.progress_label)
        prog_row.addStretch()
        self.progress_count = QLabel("0 of 4")
        self.progress_count.setStyleSheet(f"font:400 12.5px 'Barlow',sans-serif;color:{LIGHT['secondary']};")
        prog_row.addWidget(self.progress_count)
        body.addLayout(prog_row)

        self.progress_track = QFrame()
        self.progress_track.setFixedHeight(8)
        self.progress_track.setStyleSheet(f"background:{LIGHT['chrome']};")
        track_layout = QHBoxLayout(self.progress_track)
        track_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_fill = QFrame()
        self.progress_fill.setStyleSheet(f"background:{LIGHT['accent']};")
        track_layout.addWidget(self.progress_fill, stretch=0)
        track_layout.addStretch(1)
        body.addWidget(self.progress_track)

        self.step_rows = []
        for label_text in STEP_LABELS:
            row = _StepRow(label_text)
            self.step_rows.append(row)
            body.addWidget(row)

        callout = QFrame()
        callout.setStyleSheet(f"background:{LIGHT['highlight']};")
        callout_layout = QVBoxLayout(callout)
        callout_layout.setContentsMargins(12, 10, 12, 10)
        callout_label = QLabel(
            "First run after adding data can take 20–30 seconds. It is reading, "
            "not frozen — this screen keeps counting.")
        callout_label.setWordWrap(True)
        callout_label.setStyleSheet(f"font:400 12.5px 'Barlow',sans-serif;color:{LIGHT['navy']};")
        callout_layout.addWidget(callout_label)
        body.addWidget(callout)
        body.addStretch()

        # error-only controls, hidden until something fails
        self.error_row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy details")
        self.copy_btn.setStyleSheet(
            f"border:1px solid rgba(29,31,32,.3);padding:7px 12px;font:500 12.5px 'Barlow';")
        self.copy_btn.clicked.connect(self._copy_details)
        self.copy_btn.hide()
        self.close_btn = QPushButton("Close")
        self.close_btn.setStyleSheet(
            f"border:1px solid rgba(29,31,32,.3);padding:7px 12px;font:500 12.5px 'Barlow';")
        self.close_btn.clicked.connect(self.close)
        self.close_btn.hide()
        self.error_row.addWidget(self.copy_btn)
        self.error_row.addWidget(self.close_btn)
        self.error_row.addStretch()
        body.addLayout(self.error_row)

        root.addLayout(body)

        # ---- technical log panel (hidden by default) ----
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFixedHeight(90)
        self.log_view.setStyleSheet(
            "font:400 11px ui-monospace,Menlo,monospace;background:#f5f5f8;border:0;")
        self.log_view.hide()
        root.addWidget(self.log_view)

        # ---- footer ----
        footer = QFrame()
        footer.setStyleSheet("border-top:1px solid rgba(29,31,32,.14);")
        flayout = QHBoxLayout(footer)
        flayout.setContentsMargins(26, 10, 26, 10)
        version_label = QLabel("Version 3.0")
        version_label.setStyleSheet(f"font:400 12px 'Barlow',sans-serif;color:{LIGHT['secondary']};")
        flayout.addWidget(version_label)
        flayout.addStretch()
        self.log_toggle = QPushButton("Show technical log")
        self.log_toggle.setFlat(True)
        self.log_toggle.setCursor(Qt.PointingHandCursor)
        self.log_toggle.setStyleSheet(
            f"border:none;background:transparent;color:{LIGHT['accent']};"
            f"font:400 12px 'Barlow',sans-serif;text-decoration:underline;")
        self.log_toggle.clicked.connect(self._toggle_log)
        flayout.addWidget(self.log_toggle)
        root.addWidget(footer)

        screen = QApplication.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    # ------------------------------------------------------------ keyboard
    def keyPressEvent(self, event):
        """The window takes no input - Esc (or anything else) does
        nothing, so a stray keystroke can never dismiss a screen that's
        reporting real progress."""
        pass

    # ---------------------------------------------------------------- API
    def set_step(self, index, state, detail=None, elapsed=None):
        row = self.step_rows[index]
        row.set_state(state, detail=detail, elapsed=elapsed)
        self._log_lines.append(
            f"[{time.strftime('%H:%M:%S')}] {STEP_LABELS[index]}: {state}"
            + (f" ({elapsed:.2f}s)" if elapsed is not None else "")
            + (f" - {detail}" if detail else ""))
        self.log_view.setPlainText("\n".join(self._log_lines))

        if state == "active":
            self.progress_label.setText(STEP_LABELS[index])
            self.progress_count.setText(f"{index} of {len(STEP_LABELS)}")
            frac = index / len(STEP_LABELS)
        elif state == "done":
            self.progress_count.setText(f"{index + 1} of {len(STEP_LABELS)}")
            frac = (index + 1) / len(STEP_LABELS)
        elif state == "error":
            self._error = True
            self.progress_label.setText("Something needs attention")
            frac = index / len(STEP_LABELS)
            self.copy_btn.show()
            self.close_btn.show()
        else:
            frac = index / len(STEP_LABELS)

        total_w = self.progress_track.width() or (660 - 52)
        self.progress_fill.setFixedWidth(max(0, int(total_w * frac)))
        QApplication.processEvents()

    def _toggle_log(self):
        self.log_view.setVisible(not self.log_view.isVisible())
        self.log_toggle.setText(
            "Hide technical log" if self.log_view.isVisible() else "Show technical log")

    def _copy_details(self):
        QApplication.clipboard().setText("\n".join(self._log_lines))
        self.log_toggle.setText("Copied — Show technical log")
