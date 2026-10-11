"""0.9.5 Beta: host names, Devuan, init systems, desktop recommendations, resources, styles."""

import pytest

from eduka_customizer.core import distro, initsystem
from tests.conftest import make_rootfs
from tests.test_v016 import cal, nochroot  # noqa: F401 (fixtures)

DEVUAN = ('PRETTY_NAME="Devuan GNU/Linux 6 (excalibur)"\nNAME="Devuan GNU/Linux"\nVERSION_ID="6"\n'
          'VERSION="6 (excalibur)"\nVERSION_CODENAME=excalibur\nID=devuan\nID_LIKE=debian\n')
DEVUAN_SOURCES = ("Types: deb\nURIs: http://deb.devuan.org/merged\nSuites: excalibur excalibur-updates "
                  "excalibur-security\nComponents: main\n")


def test_hostnames():
    from eduka_customizer.core.branding import Branding, split_hostname
    assert split_hostname("localhost.localdomain", "mylinux") == ("mylinux", "")
    assert split_hostname("localhost", "mylinux") == ("mylinux", "")
    assert split_hostname("PC1.Example.org") == ("pc1", "pc1.example.org")
    assert split_hostname("", "mylinux") == ("mylinux", "")
    for bad in ("my_pc", "-pc", "pc..x", "a" * 64):
        with pytest.raises(ValueError):
            split_hostname(bad)
    assert Branding.check_identity({"name": "My Linux", "hostname": "localhost.localdomain"}) == "my-linux"
    with pytest.raises(ValueError):
        Branding.check_identity({"name": "My Linux", "hostname": "bad host"})
    with pytest.raises(ValueError):
        Branding.check_identity({"name": ""})


def test_identity_with_localdomain_applies(project, nochroot):  # noqa: F811
    from eduka_customizer.core.branding import Branding
    ident = dict(project.state["identity"], hostname="localhost.localdomain")
    Branding(project).apply_identity(ident)
    r = project.rootfs
    assert (r / "etc/hostname").read_text() == "edukasaun\n"
    assert "127.0.1.1\tedukasaun" in (r / "etc/hosts").read_text()
    Branding(project).apply_identity(dict(ident, hostname="lab1.school.example"))
    assert (r / "etc/hostname").read_text() == "lab1\n"
    assert "127.0.1.1\tlab1.school.example lab1" in (r / "etc/hosts").read_text()


def test_devuan_is_detected(tmp_path):
    r = make_rootfs(tmp_path / "devuan", DEVUAN, "13.1", None)
    (r / "etc/apt/sources.list.d/devuan.sources").write_text(DEVUAN_SOURCES)
    (r / "etc/devuan_version").write_text("excalibur\n")
    info = distro.detect(r)
    assert info.is_devuan and info.devuan_codename == "excalibur"
    assert info.debian_codename == "trixie" and info.suite == "stable"
    assert distro.validate(info, r)
    assert "Devuan excalibur" in info.summary()
    # A Devuan derivative without numbers in debian_version and only /etc/devuan_version.
    r2 = make_rootfs(tmp_path / "refracta", 'PRETTY_NAME="Refracta 12"\nNAME=Refracta\nID=refracta\n'
                     'ID_LIKE="devuan debian"\n', "daedalus/ceres", None)
    (r2 / "etc/devuan_version").write_text("daedalus\n")
    info2 = distro.detect(r2)
    assert info2.is_devuan and info2.debian_codename == "bookworm"


def test_devuan_sources(tmp_path):
    from eduka_customizer.core.apt import Sources, parse_deb822
    r = make_rootfs(tmp_path / "devuan", DEVUAN, "13.1", None)
    (r / "etc/apt/sources.list.d/old.sources").write_text(DEVUAN_SOURCES)
    (r / "etc/devuan_version").write_text("excalibur\n")
    src = Sources(r)
    assert src.is_devuan()
    src.set_debian("stable")
    st = parse_deb822((r / "etc/apt/sources.list.d/devuan.sources").read_text())[0]
    assert st["URIs"] == "http://deb.devuan.org/merged"
    assert st["Suites"] == "excalibur excalibur-updates excalibur-security"
    assert "devuan-archive-keyring" in st["Signed-By"]
    assert (r / "etc/apt/sources.list.d/old.sources.eduka-old").exists()
    assert not (r / "etc/apt/sources.list.d/debian.sources").exists()


def _status(r, *pkgs):
    text = (r / "var/lib/dpkg/status").read_text()
    for p in pkgs:
        text += "\nPackage: {}\nStatus: install ok installed\nVersion: 1\n".format(p)
    (r / "var/lib/dpkg/status").write_text(text)


def test_init_detection_and_blockers(project):
    r = project.rootfs
    assert initsystem.current(r) == "systemd"
    _status(r, "systemd-sysv")
    assert initsystem.current(r) == "systemd"
    assert initsystem.live_packages(r) == ["live-boot", "live-config", "live-config-systemd"]
    opts = {o[0]: o for o in initsystem.options(project)}
    assert opts["systemd"][5] and opts["sysvinit"][3] and not opts["s6"][3] and not opts["shepherd"][3]
    _status(r, "gnome-shell")
    opts = {o[0]: o for o in initsystem.options(project)}
    assert not opts["openrc"][3] and "GNOME" in opts["openrc"][4]
    with pytest.raises(ValueError):
        initsystem.use(project, "openrc")
    with pytest.raises(ValueError):
        initsystem.use(project, "s6")


def test_switch_to_sysvinit(cal, monkeypatch):  # noqa: F811
    from eduka_customizer.core import apt, chroot, yamlconf
    r = cal.rootfs
    _status(r, "systemd-sysv", "live-config", "live-config-systemd", "xserver-xorg-core")
    calls = []

    def run(self, cmd, *a, **k):
        calls.append(list(cmd))
        if cmd[:2] == ["apt-get", "-y"] and "install" in cmd:
            text = (r / "var/lib/dpkg/status").read_text()
            for p in [c[:-1] for c in cmd if c.endswith("-")]:
                text = text.replace("Package: {}\nStatus: install ok installed".format(p),
                                    "Package: {}\nStatus: deinstall ok config-files".format(p))
            (r / "var/lib/dpkg/status").write_text(text)
            _status(r, *[c for c in cmd[cmd.index("install") + 1:] if not c.startswith("-") and not c.endswith("-")])
        return 0
    monkeypatch.setattr(chroot.Chroot, "run", run)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "available", lambda self, names: set(names))
    monkeypatch.setattr(apt.Packages, "update", lambda self, *a, **k: None)
    (r / "etc/systemd/system/multi-user.target.wants").mkdir(parents=True)
    unit = r / "etc/systemd/system/eduka-system-sounds.service"
    unit.write_text("[Unit]\nDescription=System sounds\n[Service]\nExecStart=/usr/lib/x/play boot\n"
                    "ExecStop=/usr/lib/x/play down\n")
    (r / "etc/systemd/system/multi-user.target.wants/eduka-system-sounds.service").symlink_to(
        "/etc/systemd/system/eduka-system-sounds.service")
    settings = (r / "etc/calamares/settings.conf").read_text().replace("  - displaymanager\n",
                                                                        "  - displaymanager\n  - services-systemd\n")
    (r / "etc/calamares/settings.conf").write_text(settings)
    (r / "etc/calamares/modules/machineid.conf").write_text("---\nsystemd: true\ndbus: true\n")
    initsystem.use(cal, "sysvinit")
    apt_call = next(c for c in calls if "--allow-remove-essential" in c)
    assert "sysvinit-core" in apt_call and "systemd-sysv-" in apt_call and "live-config-sysvinit" in apt_call
    assert "live-config-systemd-" in apt_call and "elogind" in apt_call and "libpam-elogind" in apt_call
    assert initsystem.current(r) == "sysvinit"
    script = (r / "etc/init.d/eduka-system-sounds").read_text()
    assert "start) /usr/lib/x/play boot ;;" in script and "Default-Start:     2 3 4 5" in script
    assert ["update-rc.d", "eduka-system-sounds", "defaults"] in calls
    data = yamlconf.load((r / "etc/calamares/settings.conf").read_text())
    exec_ = [m for st in data["sequence"] if "exec" in st for m in st["exec"]]
    assert "services-systemd" not in exec_ and "displaymanager" in exec_
    assert yamlconf.load((r / "etc/calamares/modules/machineid.conf").read_text())["systemd"] is False
    assert initsystem.live_packages(r)[-1] == "live-config-sysvinit"
    # OpenRC brings Calamares' services-openrc module.
    initsystem.use(cal, "openrc")
    data = yamlconf.load((r / "etc/calamares/settings.conf").read_text())
    exec_ = [m for st in data["sequence"] if "exec" in st for m in st["exec"]]
    assert exec_[exec_.index("displaymanager") + 1] == "services-openrc"
    assert (r / "etc/calamares/modules/services-openrc.conf").exists()
    assert initsystem.current(r) == "openrc"


def test_recommendations_follow_the_desktop():
    from eduka_customizer.core import desktop as dsk
    assert dsk.recommend("xfce")["dm"] == "lightdm" and dsk.recommend("xfce")["session_type"] == "x11"
    kde = dsk.recommend("kde")
    assert kde["dm"] == "sddm" and kde["session_type"] == "wayland" and kde["compositor"] == "kwin"
    sway = dsk.recommend("sway")
    assert sway["session_type"] == "wayland" and sway["dm"] == "greetd"
    assert dsk.recommend("cinnamon")["dm"] == "lightdm-slick"
    assert dsk.recommend("eduka")["session_type"] == "x11"


GUI_DESKTOP = """
import sys
from eduka_customizer.qt.widgets import QApplication
app = QApplication([])
from eduka_customizer.gui.main_window import MainWindow
w = MainWindow()
assert w.open_project(sys.argv[1])
w.project.mark_all_steps(); w.update_state()
w.go("DesktopPage")
page = w.stack.currentWidget().current()
page.tiles["kde"].setChecked(True)
assert page._dm_selected() == "sddm" and page.st_type.currentData() == "wayland", page._dm_selected()
assert page.comp.currentData() == "kwin" and not page.eduka_card.isVisibleTo(page)
page.tiles["xfce"].setChecked(True)
assert page._dm_selected() == "lightdm" and page.st_type.currentData() == "x11"
page.dm_tiles["lightdm-slick"].setChecked(True)   # the user may choose another one
page.tiles["eduka"].setChecked(True)
assert page.eduka_card.isVisibleTo(page) and page.wm.isVisibleTo(page)
page.tiles["xfce"].setChecked(True)
w._told_review = True
page.add_change()
assert len(w.pending) == 1 and w.pending[0]["name"].startswith("Set up desktop: Xfce"), w.pending
print("ok")
"""


def test_gui_desktop_follows_choice(project):
    import os
    import subprocess
    import sys
    from pathlib import Path
    project.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", GUI_DESKTOP, str(project.path)], capture_output=True, text=True,
                         env=env, timeout=120)
    assert res.returncode == 0, res.stderr[-3000:]


def test_preview_changes_nothing(project):
    import os
    import subprocess
    from eduka_customizer.core.preview import Preview, leftover
    if os.geteuid() != 0:
        pytest.skip("needs root for overlayfs")
    p = Preview(project)
    project.save()
    try:
        p.start()
    except RuntimeError as e:
        pytest.skip(str(e))
    try:
        assert p.active
        (project.rootfs / "etc/preview-test").write_text("temporary\n")
        project.state["identity"]["name"] = "Changed in preview"
        project.save()
        assert p.size() > 0
    finally:
        p.stop()
    assert not p.active and not p.work.exists()
    assert not (project.rootfs / "etc/preview-test").exists()
    assert project.state["identity"]["name"] == "Edukasaun OS"
    # A preview left behind by a crash is found and ended.
    p.start()
    (project.rootfs / "x").write_text("x")
    assert leftover(type(project)(project.path)) and not (project.rootfs / "x").exists()
    assert "overlay" not in subprocess.run(["findmnt", "-no", "FSTYPE", str(project.path)], capture_output=True,
                                           text=True).stdout


GUI_PREVIEW = """
import os, sys, time
from eduka_customizer.qt.widgets import QApplication, QMessageBox
QMessageBox.information = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok)
QMessageBox.question = staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
app = QApplication([])
from eduka_customizer.gui.main_window import MainWindow
w = MainWindow()
assert w.open_project(sys.argv[1])
w.project.mark_all_steps(); w.update_state(); w._told_review = True
r = w.project.rootfs
page = next(p for p in w.pages if p.__class__.__name__ == "SoundsPage")
page.task("Apply system sounds", lambda t: (r / "etc/try-me").write_text("x"))
def wait():
    t0 = time.time()
    while w.task and time.time() - t0 < 30:
        app.processEvents(); time.sleep(0.02)
w.preview_start(); wait()
assert w.preview_active() and (r / "etc/try-me").exists() and len(w.pending) == 1
w.preview_discard(); wait()
assert not w.preview_active() and not (r / "etc/try-me").exists() and len(w.pending) == 1
w.preview_start(); wait()
w.preview_keep(); wait()
assert not w.preview_active() and (r / "etc/try-me").exists() and w.pending == []
print("ok")
"""


def test_gui_preview_keep_and_discard(project):
    import os
    import subprocess
    import sys
    from pathlib import Path
    if os.geteuid() != 0:
        pytest.skip("needs root for overlayfs")
    project.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", GUI_PREVIEW, str(project.path)], capture_output=True, text=True,
                         env=env, timeout=180)
    assert res.returncode == 0, res.stderr[-3000:]


def test_resources_plan():
    from eduka_customizer.core import resources
    big = {"cores": 8, "mem_total": 16 << 30, "mem_available": 12 << 30}
    full, bal, light = (resources.plan(m, "zstd", 15, big) for m in ("full", "balanced", "light"))
    assert full["processors"] == 8 and bal["processors"] == 6 and light["processors"] == 4
    assert resources.plan("balanced", "xz", 0, big)["processors"] == 7
    assert light["nice"] == 19 and full["nice"] == 0 and bal["mem_mb"] <= 8192
    small = {"cores": 2, "mem_total": 2 << 30, "mem_available": 1 << 30}
    p = resources.plan("balanced", "zstd", 15, small)
    assert p["processors"] == 1 and p["mem_mb"] >= 256
    cmd = resources.wrap(["mksquashfs", "a", "b"], light)
    assert cmd[-3:] == ["mksquashfs", "a", "b"] and cmd[0] in ("nice", "ionice", "mksquashfs")
