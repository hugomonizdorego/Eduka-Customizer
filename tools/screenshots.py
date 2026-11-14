#!/usr/bin/env python3
"""Take the screenshots of the user guide (docs/screenshots) from a demo project.

    sudo QT_QPA_PLATFORM=offscreen python3 tools/screenshots.py [/home/disco/mylinux]

The demo project gets a small fake system (enough for every page to show its
contents); nothing is downloaded and nothing is built.
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("DISCO_CONF", os.path.join(tempfile.mkdtemp(prefix="disco-shots-"), "disco.conf"))
os.environ.setdefault("DISCO_DATA", str(ROOT / "data"))
OUT = ROOT / "docs" / "screenshots"


def demo_project(path):
    from disco.core.project import Project
    from tests.conftest import make_rootfs_into
    path = Path(path)
    if path.exists():
        shutil.rmtree(path)
    p = Project.create(path, name="My Linux")
    make_rootfs_into(p.rootfs)
    r = p.rootfs
    for rel, text in (("boot/vmlinuz-6.12.48+deb13-amd64", "k"), ("boot/initrd.img-6.12.48+deb13-amd64", "i"),
                      ("etc/hostname", "mylinux\n"), ("etc/motd", "\nWelcome!\n"),
                      ("usr/share/xsessions/xfce.desktop", "[Desktop Entry]\nName=Xfce Session\nExec=startxfce4\n"),
                      ("etc/skel/.bashrc", "PS1='\\u@\\h:\\w\\$ '\n")):
        f = r / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text)
    p.state["purpose"] = "home"
    p.state["identity"].update({"name": "My Linux", "id": "mylinux", "version": "1.0", "codename": "Aurora",
                                "home_url": "https://mylinux.example.org", "hostname": "mylinux"})
    from disco.core import distro
    p.state["distro"] = distro.detect(p.rootfs).to_dict()
    p.state["source"].update({"kind": "iso", "path": "/home/me/Downloads/debian-live-13.1.0-amd64-standard.iso",
                              "label": "Debian GNU/Linux 13.1.0 live standard"})
    p.record("extract", "debian-live-13.1.0-amd64-standard.iso")
    (p.path / "hooks").mkdir(exist_ok=True)
    (p.path / "hooks/10-welcome.sh").write_text("#!/bin/sh\necho 'Hello from My Linux'\n")
    p.save()
    return p


def grab(w, app, name, page=None, scroll=0, size=(1400, 900)):
    from disco.qt.widgets import QScrollArea
    if page:
        w.go(page)
    w.resize(*size)
    app.processEvents()
    if scroll:
        cur = w.stack.currentWidget().current()
        area = cur.findChild(QScrollArea)
        if area:
            bar = area.verticalScrollBar()
            bar.setValue(bar.maximum() if scroll == "end" else int(scroll))
    for _ in range(3):
        app.processEvents()
    OUT.mkdir(parents=True, exist_ok=True)
    w.grab().save(str(OUT / name))
    print("shot", name)


def main():
    from disco.qt.widgets import QApplication
    app = QApplication(sys.argv[:1])
    project_dir = sys.argv[1] if len(sys.argv) > 1 else "/home/disco/mylinux"
    from disco.gui.main_window import MainWindow
    for old in OUT.glob("*.png"):
        old.unlink()
    # What a new user sees first: Welcome and Start, no project open yet.
    w = MainWindow()
    w.show()
    app.processEvents()
    if w.log.isVisible():
        w.toggle_log()
    grab(w, app, "01-welcome.png", "HomePage")
    grab(w, app, "01b-welcome-support.png", "HomePage", scroll="end")
    p = demo_project(project_dir)
    grab(w, app, "02-start.png", "ProjectPage")
    w.open_project(str(p.path))
    w.project.mark_all_steps()
    w.update_state()
    pages = {pg.__class__.__name__: pg for pg in w.pages}
    start = pages["ProjectPage"]
    start.net_label.setText("<b>✔ Internet connection:</b> packages, desktops, Flatpaks and kernels can be "
                            "installed.")
    grab(w, app, "02b-start-continue.png", "ProjectPage")
    grab(w, app, "02c-start-other-ways.png", "ProjectPage", scroll="end")
    grab(w, app, "03-repositories.png", "SourcesPage")
    grab(w, app, "03b-identity.png", "IdentityPage")
    sysp = pages["SystemFilesPage"]
    w.go("SystemFilesPage")
    sysp.files.setCurrentRow(0)
    sysp.template()
    grab(w, app, "03c-system-files.png")
    grab(w, app, "03d-users.png", "UsersPage")
    grab(w, app, "04-desktop.png", "DesktopPage")
    grab(w, app, "04b-applications.png", "PackagesPage")
    grab(w, app, "05-startup.png", "StartupPage")
    grab(w, app, "05b-startup-programs.png", "StartupPage", scroll="end")
    # Wallpaper & Logo with pictures chosen
    from disco.core import quickbrand
    for kind, pic in (("wallpaper", "tools/demo-wallpaper.png"), ("logo", "icons/disco.svg")):
        src = ROOT / pic
        if src.exists():
            quickbrand.store(w.project, kind, src)
    grab(w, app, "06-wallpaper-logo.png", "EasyBrandPage")
    doc = pages["ReadmePage"]
    w.go("ReadmePage")
    doc.doc_title.setText("Welcome to My Linux")
    doc.first_text()
    grab(w, app, "06b-desktop-document.png")
    grab(w, app, "06c-plymouth.png", "PlymouthPage")
    grab(w, app, "07-themes.png", "ThemesPage")
    sh = pages["ShellBrowserPage"]
    w.go("ShellBrowserPage")
    sh.motd.setPlainText("Documentation: https://mylinux.example.org/docs")
    sh.dynamic.setChecked(True)
    sh.prompt.setCurrentIndex(sh.prompt.findData("brand"))
    sh.home.setText("https://mylinux.example.org")
    sh.locked.setChecked(True)
    sh.bookmarks.setPlainText("Debian | https://www.debian.org\nMy Linux forum | https://forum.mylinux.example.org")
    grab(w, app, "07b-terminal-browser.png")
    grab(w, app, "08-kernel.png", "KernelPage")
    grab(w, app, "08b-boot-loader.png", "BootLoaderPage")
    w.project.state.setdefault("builder", {})["platform"] = "rpi-arm64"
    w.project.state["board"] = {"config_txt": "dtparam=audio=on\ndtoverlay=vc4-kms-v3d", "cmdline": "quiet",
                                "boot_mb": 512, "compress": "xz", "sysconf": True}
    w.project.save()
    grab(w, app, "08c-raspberry-pi.png", "BoardPage")
    w.project.state["builder"]["platform"] = "pc64"
    w.project.save()
    grab(w, app, "09-installer.png", "CalamaresPage")
    files = pages["FilesPage"]
    grab(w, app, "10-files.png", "FilesPage")
    grab(w, app, "10b-files-system.png", "FilesPage", scroll="end")
    grab(w, app, "10c-terminal.png", "TerminalPage")
    # A few waiting changes for Review & Apply
    sh.set_prompt()
    sh.set_browser()
    w.go("SystemFilesPage")
    sysp.files.setCurrentRow(2)
    sysp.template()
    sysp.save()
    box = getattr(w, "_review_box", None)
    if box:
        box.close()
    grab(w, app, "11-review-apply.png", "ReviewPage")
    grab(w, app, "12-build.png", "BuildPage")
    grab(w, app, "13-settings.png", "SettingsPage")
    grab(w, app, "13b-about.png", "AboutPage")
    w.dark = True
    w.apply_style()
    grab(w, app, "14-dark-start.png", "ProjectPage")
    del files
    # Closing the window would ask about the waiting changes: leave without it.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
