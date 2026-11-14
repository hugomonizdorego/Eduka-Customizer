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
    from disco.core import presets
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
    presets.apply(p, presets.find("Debian Xfce desktop (PC 64-bit)"))
    p.state["identity"].update({"name": "My Linux", "id": "mylinux", "version": "1.0", "codename": "Aurora",
                                "home_url": "https://mylinux.example.org", "hostname": "mylinux"})
    p.state["builder"]["distro_name"] = "My Linux"
    from disco.core import distro
    p.state["distro"] = distro.detect(p.rootfs).to_dict()
    p.state["pipeline"] = {"prepare": "2026-11-14 09:12", "base": "2026-11-14 09:31",
                           "packages": "2026-11-14 09:58"}
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
    p = demo_project(project_dir)
    from disco.gui.main_window import MainWindow
    w = MainWindow()
    w.open_project(str(p.path))
    w.project.mark_all_steps()
    w.update_state()
    w.show()
    app.processEvents()
    if w.log.isVisible():
        w.toggle_log()
    for old in OUT.glob("*.png"):
        old.unlink()
    pages = {pg.__class__.__name__: pg for pg in w.pages}
    grab(w, app, "01-builder.png", "BuilderPage")
    grab(w, app, "01b-builder-lists.png", "BuilderPage", scroll=430)
    grab(w, app, "01c-builder-tools.png", "BuilderPage", scroll="end")
    # The package list editor with the catalog
    from disco.core.pkglists import Lists
    from disco.gui.pages.builder import ListEditor
    pl = Lists(w.project).get("applications")
    dlg = ListEditor(w, pl.title, pl.packages(), pl.comment())
    dlg.resize(1100, 700)
    dlg.show()
    app.processEvents()
    dlg.grab().save(str(OUT / "01d-list-editor.png"))
    print("shot 01d-list-editor.png")
    dlg.close()
    grab(w, app, "01e-start-sources.png", "ProjectPage")
    grab(w, app, "02-repositories.png", "SourcesPage")
    grab(w, app, "02b-identity.png", "IdentityPage")
    sysp = pages["SystemFilesPage"]
    w.go("SystemFilesPage")
    sysp.files.setCurrentRow(0)
    sysp.template()
    grab(w, app, "02c-system-files.png")
    grab(w, app, "02d-users.png", "UsersPage")
    grab(w, app, "02e-init-system.png", "InitSystemPage")
    grab(w, app, "03-desktop.png", "DesktopPage")
    grab(w, app, "03b-packages.png", "PackagesPage")
    grab(w, app, "04-kernel.png", "KernelPage")
    grab(w, app, "04b-boot-loader.png", "BootLoaderPage")
    grab(w, app, "04c-boot-menu.png", "BootMenuPage")
    # The Raspberry Pi page of a Pi project
    w.project.state["builder"]["platform"] = "rpi-arm64"
    w.project.state["board"] = {"config_txt": "dtparam=audio=on\ndtoverlay=vc4-kms-v3d", "cmdline": "quiet",
                                "boot_mb": 512, "compress": "xz", "sysconf": True}
    w.project.state["last_image"] = str(w.project.output / "mylinux-1.0-stable-arm64-20261114.img.xz")
    Path(w.project.state["last_image"]).write_bytes(b"")
    w.project.save()
    grab(w, app, "04d-raspberry-pi.png", "BoardPage")
    w.project.state["builder"]["platform"] = "pc64"
    w.project.save()
    builder = pages["BuilderPage"]
    builder.project_changed()
    grab(w, app, "05-branding.png", "BrandingPage")
    grab(w, app, "05b-wallpaper-login.png", "AppearancePage")
    grab(w, app, "05c-plymouth.png", "PlymouthPage")
    doc = pages["ReadmePage"]
    w.go("ReadmePage")
    doc.doc_title.setText("Welcome to My Linux")
    doc.first_text()
    grab(w, app, "05d-desktop-document.png")
    grab(w, app, "06-themes.png", "ThemesPage")
    sh = pages["ShellBrowserPage"]
    w.go("ShellBrowserPage")
    sh.motd.setPlainText("Documentation: https://mylinux.example.org/docs")
    sh.dynamic.setChecked(True)
    sh.prompt.setCurrentIndex(sh.prompt.findData("brand"))
    sh.home.setText("https://mylinux.example.org")
    sh.locked.setChecked(True)
    sh.bookmarks.setPlainText("Debian | https://www.debian.org\nMy Linux forum | https://forum.mylinux.example.org")
    grab(w, app, "06b-terminal-browser.png")
    grab(w, app, "06c-terminal-browser-policies.png", scroll="end")
    grab(w, app, "07-installer.png", "CalamaresPage")
    grab(w, app, "08-advanced.png", "TerminalPage")
    # A few waiting changes for Review & Apply
    sh.set_prompt()
    sh.set_browser()
    w.go("SystemFilesPage")
    sysp.files.setCurrentRow(2)
    sysp.template()
    sysp.save()
    for box in [getattr(w, "_review_box", None)]:
        if box:
            box.close()
    grab(w, app, "09-review-apply.png", "ReviewPage")
    grab(w, app, "10-check-build.png", "BuildPage")
    grab(w, app, "11-settings.png", "SettingsPage")
    grab(w, app, "11b-about.png", "AboutPage")
    w.dark = True
    w.apply_style()
    grab(w, app, "12-dark-builder.png", "BuilderPage")
    # Closing the window would ask about the waiting changes: leave without it.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
