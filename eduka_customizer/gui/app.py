"""Start the Eduka-Customizer GUI."""

import os
import shutil
import sys

from eduka_customizer import APP_ID, APP_NAME, VERSION_LABEL


def _relaunch_as_root(args):
    """Restart through pkexec, keeping the display variables the GUI needs."""
    launcher = shutil.which("eduka-customizer-pkexec")
    if launcher and os.path.dirname(launcher) in ("/usr/bin", "/usr/local/bin"):
        os.execv(launcher, [launcher] + args)
    pkexec = shutil.which("pkexec")
    if not pkexec:
        return False
    keep = ["DISPLAY", "XAUTHORITY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE",
            "QT_QPA_PLATFORM", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "LANG", "LANGUAGE"]
    env = ["{}={}".format(k, os.environ[k]) for k in keep if os.environ.get(k)]
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env.append("PYTHONPATH=" + pkg_root)
    os.execv(pkexec, [pkexec, "env"] + env + [sys.executable, "-m", "eduka_customizer", "gui"] + args)
    return True


def run(project=None, iso=None):
    from eduka_customizer.core.log import setup_debug_log
    setup_debug_log("gui")
    from eduka_customizer.qt.core import Qt
    from eduka_customizer.qt.gui import QPalette
    from eduka_customizer.qt.widgets import QApplication, QMessageBox

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(VERSION_LABEL)
    app.setDesktopFileName(APP_ID)
    app.setStyle("Fusion")

    if os.geteuid() != 0 and not os.environ.get("EDUKA_CUSTOMIZER_NO_ROOT"):
        r = QMessageBox.question(None, APP_NAME,
                                 "Eduka-Customizer needs administrator rights to mount, chroot and "
                                 "build images.\n\nRestart as administrator now?")
        if r == QMessageBox.StandardButton.Yes and _relaunch_as_root([a for a in (iso or project,) if a]):
            return 0
        QMessageBox.warning(None, APP_NAME, "Continuing without administrator rights: most actions "
                                            "will fail.")

    from eduka_customizer.core.config import settings
    from eduka_customizer.gui.main_window import MainWindow

    theme = settings().get("general", "theme")
    if theme == "auto":
        dark = app.palette().color(QPalette.ColorRole.Window).lightness() < 110
        try:
            dark = dark or app.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except AttributeError:
            pass
    else:
        dark = theme == "dark"
    win = MainWindow(dark=dark)
    win.show()
    if project:
        win.open_project(project)
    else:
        recent = settings().recent_projects()
        if recent:
            win.open_project(recent[0])
    win.pages[0].refresh()
    if iso:
        win.pages[0].iso.setText(iso)
    return app.exec()
