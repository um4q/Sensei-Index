# -*- coding: utf-8 -*-
"""App title/version branding - locks in the Sensei Index 2.9 rename so a
future accidental revert (e.g. someone copy-pastes an older gui_app.py
snippet) is caught immediately rather than silently shipping stale
branding."""
import gui_app


def test_app_title_is_2_9():
    assert gui_app.APP_TITLE == "Sensei Index 2.9"


def test_main_window_title_bar_shows_2_9(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    assert win.windowTitle() == "Sensei Index 2.9"


def test_sidebar_title_label_shows_2_9(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    win = gui_app.MainWindow()
    qtbot.addWidget(win)
    labels = [w.text() for w in win.findChildren(gui_app.QLabel) if w.objectName() == "SidebarTitle"]
    assert labels == ["Sensei Index 2.9"]
