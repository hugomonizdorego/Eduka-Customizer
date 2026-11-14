"""Press every button and tick every box of every page, offscreen.

Dialogs answer by themselves (No / Cancel / nothing chosen), no program is started
and background tasks are only recorded. Any error a button causes in the window
fails the test (0.11 shipped a Builder whose step buttons crashed: never again)."""

import os
import subprocess
import sys
from pathlib import Path

CLICK_ALL = r'''
import os, sys, traceback, subprocess
from pathlib import Path
errors = []
sys.excepthook = lambda t, v, tb: errors.append("".join(traceback.format_exception(t, v, tb)))

from disco.qt.widgets import (QAbstractButton, QApplication, QCheckBox, QDialog, QFileDialog, QInputDialog,
                              QMessageBox, QTabWidget)
app = QApplication([])
B = QMessageBox.StandardButton
QMessageBox.question = staticmethod(lambda *a, **k: B.No)
QMessageBox.information = staticmethod(lambda *a, **k: B.Ok)
QMessageBox.warning = staticmethod(lambda *a, **k: B.Ok)
QMessageBox.critical = staticmethod(lambda *a, **k: B.Ok)
QMessageBox.exec = lambda self: 0
QDialog.exec = lambda self: 0
QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getOpenFileNames = staticmethod(lambda *a, **k: ([], ""))
QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
QInputDialog.getText = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getItem = staticmethod(lambda *a, **k: ("", False))
QInputDialog.getInt = staticmethod(lambda *a, **k: (0, False))
QInputDialog.getDouble = staticmethod(lambda *a, **k: (0.0, False))
QInputDialog.getMultiLineText = staticmethod(lambda *a, **k: ("", False))
from disco.qt.widgets import QColorDialog, QMenu
QColorDialog.getColor = staticmethod(lambda *a, **k: __import__("disco.qt.gui", fromlist=["QColor"]).QColor())
QMenu.exec = lambda self, *a, **k: None
try:
    from disco.qt.widgets import QFontDialog
    QFontDialog.getFont = staticmethod(lambda *a, **k: (None, False))
except ImportError:
    pass
import faulthandler
faulthandler.dump_traceback_later(240, exit=True)


class NoProcess:
    def __init__(self, *a, **k):
        raise OSError("no programs are started in this test")


subprocess.Popen = NoProcess
import disco.gui.opener as opener
opener.open_url = lambda *a, **k: True
from disco.core import qemu, livesession
qemu.start = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no QEMU in this test"))
livesession.LiveSession.start = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no live session in this test"))

from disco.core.project import Project
from disco.gui.main_window import MainWindow
started = []


def fake_run_task(self, name, func, done=None, queue=False, page=None):
    if queue and self.project and self.collect_changes():
        self.queue_change(name, func, done, page)
        return None
    started.append((name, func))
    return None


MainWindow.run_task = fake_run_task
w = MainWindow()
if sys.argv[1]:
    assert w.open_project(sys.argv[1])
    w.project.mark_all_steps()
    w.update_state()
w.show()
pressed = 0
skip = {"Quit"}
for page in list(w.pages):
    name = page.__class__.__name__
    if not w.section_open(page.nav_section):
        continue           # without a project only Welcome, Start and Settings open
    print("page", name, flush=True)
    w.go(name)
    app.processEvents()
    try:
        page.refresh()
    except Exception:
        errors.append(name + " refresh:\n" + traceback.format_exc())
    for b in page.findChildren(QAbstractButton):
        if not b.isEnabled() or b.text() in skip or not b.isVisibleTo(page):
            continue
        before = len(errors)
        try:
            b.click()
            if isinstance(b, QCheckBox):
                b.click()        # back as it was
            pressed += 1
        except Exception:
            errors.append(traceback.format_exc())
        app.processEvents()
        for i in range(before, len(errors)):
            errors[i] = "{} '{}':\n{}".format(name, b.text(), errors[i])
# The bars (Back / Next / Finish) and the sidebar buttons
for sec in w.sections:
    if not w.section_open(sec):
        continue
    w.go_section(sec)
    app.processEvents()
    for b in (sec.bar.findChildren(QAbstractButton) if sec.bar else []):
        try:
            b.click()
            pressed += 1
        except Exception:
            errors.append("bar of {} '{}':\n{}".format(sec.title, b.text(), traceback.format_exc()))
        app.processEvents()
for text in ("Dark mode", "Light mode", "Hide log", "Show log"):
    for b in w.findChildren(QAbstractButton):
        if b.text() == text and b.isVisible():
            b.click()
            app.processEvents()
# Run the work of every button (with the system's programs replaced): mistakes in the code show up as
# AttributeError, TypeError, NameError...; refusals with a message (RuntimeError, ValueError, OSError)
# are what the window shows to the user and are fine here.
from disco.core import runner, chroot, apt


class T:
    set_progress = staticmethod(lambda *a: None)
    set_stage = staticmethod(lambda *a: None)


runner.run = lambda *a, **k: 0
runner.output = lambda *a, **k: ""
chroot.Chroot.run = lambda self, *a, **k: 0
chroot.Chroot.output = lambda self, *a, **k: ""
chroot.Chroot.__enter__ = lambda self: self
chroot.Chroot.__exit__ = lambda self, *a: False
apt.Packages.available = lambda self, names: set(names)
apt.Packages.update = lambda self: None
apt.Packages.install = lambda self, *a, **k: None
apt.Packages.remove = lambda self, *a, **k: None
MISTAKES = (AttributeError, TypeError, NameError, UnboundLocalError, ImportError, IndexError, KeyError,
            ZeroDivisionError)
work = [(ch["name"], ch["func"]) for ch in w.pending] + started
ran = 0
for name, func in work:
    try:
        func(T())
        ran += 1
    except MISTAKES:
        errors.append("task '{}':\n{}".format(name, traceback.format_exc()))
    except Exception as e:  # a message for the user
        ran += 1
        print("refused:", name, "->", type(e).__name__, str(e)[:120])
print("pressed", pressed, "tasks", len(started), "waiting", len(w.pending), "ran", ran)
for e in errors:
    print("ERROR:", e)
os._exit(1 if errors else 0)
'''


def test_press_every_button(tmp_path):
    _press_all(tmp_path, "pc64")


def test_press_every_button_raspberry_pi(tmp_path):
    """A Raspberry Pi project: the Build page makes an SD-card image, the Raspberry Pi page is active."""
    _press_all(tmp_path, "rpi-arm64")


def _press_all(tmp_path, platform):
    from disco.core.project import Project
    from tests.conftest import make_rootfs_into
    p = Project.create(tmp_path / "clicks", name="Clicks")
    make_rootfs_into(p.rootfs)
    r = p.rootfs
    for rel, text in (("etc/xdg/autostart/nm-applet.desktop", "[Desktop Entry]\nName=Network\nExec=nm-applet\n"),
                      ("lib/systemd/system/ssh.service", "[Unit]\nDescription=OpenBSD Secure Shell server\n"
                                                         "[Service]\nExecStart=/usr/sbin/sshd\n"
                                                         "[Install]\nWantedBy=multi-user.target\n"),
                      ("etc/hostname", "clicks\n"), ("boot/vmlinuz-6.12.48+deb13-amd64", "k"),
                      ("boot/initrd.img-6.12.48+deb13-amd64", "i")):
        f = r / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    p.state["identity"].update({"name": "Clicks", "id": "clicks", "version": "1.0"})
    p.state.setdefault("builder", {})["platform"] = platform
    p.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", CLICK_ALL, str(p.path)], capture_output=True, text=True, env=env,
                         timeout=600)
    out = res.stdout + res.stderr[-4000:]
    assert res.returncode == 0, out
    assert "pressed" in res.stdout


def test_press_every_button_without_a_project():
    """What a new user sees first: no project open (Welcome, Start, Settings)."""
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", CLICK_ALL, ""], capture_output=True, text=True, env=env, timeout=600)
    out = res.stdout + res.stderr[-4000:]
    assert res.returncode == 0, out
    assert "page HomePage" in res.stdout and "page ProjectPage" in res.stdout
