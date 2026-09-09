# -*- coding: utf-8 -*-
"""Phase C (Sensei Index 2.9) - the startup splash screen. Must be a real
Qt window (QSplashScreen), not a terminal message, showing the same logo
used in the sidebar enlarged, with status text tied to real startup
steps - and it must survive QT_QPA_PLATFORM=offscreen without hanging,
same as every other GUI test in this suite."""
import gui_app


def test_splash_pixmap_is_larger_than_the_sidebar_logo(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    pixmap = gui_app._build_splash_pixmap("light")
    assert not pixmap.isNull()
    assert pixmap.height() > 42  # the sidebar's own logo scale - splash must read as "enlarged"
    assert pixmap.height() >= gui_app.SPLASH_LOGO_HEIGHT


def test_splash_pixmap_theme_aware(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    light = gui_app._build_splash_pixmap("light")
    dark = gui_app._build_splash_pixmap("dark")
    assert not light.isNull() and not dark.isNull()


def test_run_startup_with_splash_shows_real_status_messages_in_order(qtbot, isolated_app_dir):
    tmp_path, da = isolated_app_dir
    seen = []
    original_show_message = gui_app.QSplashScreen.showMessage

    def spy(self, message, *a, **k):
        seen.append(message)
        return original_show_message(self, message, *a, **k)

    gui_app.QSplashScreen.showMessage = spy
    try:
        app = gui_app.QApplication.instance() or gui_app.QApplication([])
        win = gui_app._run_startup_with_splash(app)
        qtbot.addWidget(win)
        assert isinstance(win, gui_app.MainWindow)
    finally:
        gui_app.QSplashScreen.showMessage = original_show_message

    assert seen == [
        "Loading Instrumentation data…",
        "Loading Electrical data…",
        "Building interface…",
        "Ready",
    ]


def test_run_startup_with_splash_actually_warms_both_workbook_caches_first(qtbot, isolated_app_dir):
    """The status text names real work, not decoration - confirm the
    Instrumentation and Electrical workbook caches are already warm by
    the time MainWindow() is constructed (not lazily loaded for the
    first time during the window's own tree-building)."""
    tmp_path, da = isolated_app_dir
    import electrical_data_access as eda
    eda.add_zone("K1B Well Pad")  # with zero zones there's genuinely nothing to load -
                                  # give count_all_by_type() something real to touch

    da.invalidate_workbook_cache()
    eda.invalidate_workbook_cache()

    original_init = gui_app.MainWindow.__init__
    cache_state_at_construction = {}

    def spy_init(self, *a, **k):
        cache_state_at_construction["da_mtime"] = da._wb_cache["mtime"]
        cache_state_at_construction["eda_mtime"] = eda._wb_cache["mtime"]
        return original_init(self, *a, **k)

    gui_app.MainWindow.__init__ = spy_init
    try:
        app = gui_app.QApplication.instance() or gui_app.QApplication([])
        win = gui_app._run_startup_with_splash(app)
        qtbot.addWidget(win)
    finally:
        gui_app.MainWindow.__init__ = original_init

    assert cache_state_at_construction["da_mtime"] is not None
    assert cache_state_at_construction["eda_mtime"] is not None
