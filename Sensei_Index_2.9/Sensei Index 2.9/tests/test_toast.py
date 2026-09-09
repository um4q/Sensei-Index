# -*- coding: utf-8 -*-
"""Phase 13.6 - Toast widget."""
from PySide6.QtWidgets import QDialog, QWidget

import gui_app


def test_toast_shows_text_and_self_dismisses(qtbot):
    parent = QWidget()
    qtbot.addWidget(parent)
    parent.show()

    toast = gui_app.Toast(parent, "Saved", duration_ms=50)
    assert toast.isVisible()

    # Toast owns its own lifecycle (self._dismiss() closes + deleteLater()s
    # itself) - wait for the C++ object's destroyed signal rather than
    # polling isVisible() on what may already be a deleted wrapper, and
    # don't hand it to qtbot.addWidget (that would double-manage cleanup).
    with qtbot.waitSignal(toast.destroyed, timeout=2000):
        pass


def test_show_toast_anchors_to_outermost_parent_not_a_closing_dialog():
    """A QDialog is always its own top-level window (QWidget.window()
    returns the dialog itself) - show_toast must NOT use .window(), or a
    toast shown right before dialog.accept() would close along with it."""
    root = QWidget()
    dialog = QDialog(root)

    anchor = gui_app._toast_anchor(dialog)
    assert anchor is root
    assert anchor is not dialog


def test_show_toast_creates_toast_parented_to_root(qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    root.show()
    dialog = QDialog(root)

    toast = gui_app.show_toast(dialog, "Imported 3 rows", duration_ms=50)
    assert toast.parentWidget() is root

    # Closing (and destroying) the dialog must not take the toast with it.
    dialog.close()
    dialog.deleteLater()
    assert toast.isVisible()
