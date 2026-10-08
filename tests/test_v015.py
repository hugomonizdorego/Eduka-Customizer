"""0.15: general Debian-based builder, install editions, replacing default
applications, pre-build checks and the step-by-step menus."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from eduka_customizer.core import desktop as dsk
from eduka_customizer.core import preflight, profiles, replace
from eduka_customizer.core.project import Project


@pytest.fixture
def nochroot(monkeypatch):
    from eduka_customizer.core import apt, chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(list(cmd)) or 0)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "install", lambda self, names, **k: calls.append(["install"] + list(names)))
    monkeypatch.setattr(apt.Packages, "remove", lambda self, names, **k: calls.append(["remove"] + list(names)))
    return calls


# Desktops ------------------------------------------------------------------------------------

def test_catalog_has_debian_desktops_and_editions():
    cat = dsk.catalog()
    ids = [d["id"] for d in cat["desktops"]]
    for wanted in ("eduka", "gnome", "kde", "xfce", "cinnamon", "mate", "lxqt", "lxde", "budgie",
                   "gnome-flashback", "enlightenment", "openbox", "i3", "bspwm", "sway", "labwc", "wayfire"):
        assert wanted in ids, wanted
    assert len(ids) == len(set(ids))
    assert [e["id"] for e in dsk.editions()] == ["mini", "compact", "full", "full_apps"]
    for d in cat["desktops"]:
        assert set(d["editions"]) == set(dsk.EDITIONS), d["id"]
        for e in d["editions"].values():
            assert e["packages"], d["id"]
            assert not any("ubuntu" in p for p in e["packages"]), d["id"]
            assert e.get("apps") in (None,) + tuple(cat["app_sets"]), d["id"]
    # Every native compositor belongs to a desktop of the list.
    for c in cat["compositors"]:
        if c["kind"] == "native":
            assert c["desktop"] in ids
            assert dsk.desktop(c["desktop"])["native_compositor"] == c["id"]


def test_edition_plan():
    pkgs, apps, norec = dsk.edition_plan("xfce", "mini")
    assert "xfce4" in pkgs and not apps and norec
    pkgs, apps, norec = dsk.edition_plan("xfce", "full")
    assert pkgs == ["task-xfce-desktop"] and not apps and not norec
    pkgs, apps, norec = dsk.edition_plan("kde", "full_apps")
    assert "task-kde-desktop" in pkgs and "okular" in apps
    with pytest.raises(ValueError):
        dsk.edition_plan("xfce", "huge")


def test_install_edition(project, nochroot, monkeypatch):
    from eduka_customizer.core import apt
    monkeypatch.setattr(apt.Packages, "available", lambda self, names: set(names) - {"krita"})
    monkeypatch.setattr(dsk.DesktopManager, "set_display_manager", lambda self, dm: None)
    monkeypatch.setattr(dsk.DesktopManager, "set_default_session", lambda self, s: None)
    dsk.DesktopManager(project).install("kde", edition="full_apps")
    installs = [c for c in nochroot if c[0] == "install"]
    assert installs[0][1:] == ["task-kde-desktop", "kde-standard"]
    assert "okular" in installs[1] and "krita" not in installs[1]
    assert project.state["desktop"]["edition"] == "full_apps"


def test_eduka_desktop_is_listed_but_not_the_default():
    assert dsk.desktop("eduka")["eduka_desktop"]
    edu = dict((k, s) for k, _l, s in profiles.recommendations("education"))
    assert edu["desktop"]["id"] != "eduka"


# ISO editions --------------------------------------------------------------------------------

def test_iso_editions():
    assert [e["id"] for e in profiles.iso_editions()] == ["minimal", "full", "full_apps"]
    mini = dict((k, s) for k, _l, s in profiles.recommendations("education", "minimal"))
    assert mini["desktop"]["edition"] == "mini" and "flatpak" not in mini and "plymouth" not in mini
    assert "apps" not in mini
    full = dict((k, s) for k, _l, s in profiles.recommendations("education", "full"))
    assert full["desktop"]["edition"] == "full" and "apps" in full and "flatpak" not in full
    rich = dict((k, s) for k, _l, s in profiles.recommendations("education", "full_apps"))
    assert rich["desktop"]["edition"] == "full_apps" and "flatpak" in rich
    server = dict((k, s) for k, _l, s in profiles.recommendations("server", "minimal"))
    assert server["apps"]["packages"] == ["openssh-server", "ufw", "unattended-upgrades"]
    with pytest.raises(KeyError):
        profiles.recommendations("home", "gigantic")


# Replacing default applications ---------------------------------------------------------------

def _pkg(rootfs, name, files, desktop=None):
    info = rootfs / "var/lib/dpkg/info"
    info.mkdir(parents=True, exist_ok=True)
    (info / (name + ".list")).write_text("\n".join(files) + "\n")
    st = rootfs / "var/lib/dpkg/status"
    st.write_text(st.read_text().rstrip("\n") + "\n\nPackage: {}\nStatus: install ok installed\nVersion: 1\n"
                  .format(name))
    if desktop:
        apps = rootfs / "usr/share/applications"
        apps.mkdir(parents=True, exist_ok=True)
        for fname, text in desktop.items():
            (apps / fname).write_text(text)


def test_roles_catalog():
    ids = [r["id"] for r in replace.roles()]
    for wanted in ("browser", "mail", "office", "editor", "files", "terminal", "images", "video", "music",
                   "pdf", "archive", "calculator"):
        assert wanted in ids
    with pytest.raises(KeyError):
        replace.role("toaster")


def test_alternative_paths(tmp_path):
    alt = tmp_path / "var/lib/dpkg/alternatives"
    alt.mkdir(parents=True)
    (alt / "x-www-browser").write_text("auto\n/usr/bin/x-www-browser\n\n/usr/bin/firefox-esr\n70\n"
                                       "/usr/bin/chromium\n40\n\n")
    assert replace.alternative_paths(tmp_path, "x-www-browser") == ["/usr/bin/firefox-esr", "/usr/bin/chromium"]
    (alt / "x-terminal-emulator").write_text(
        "auto\n/usr/bin/x-terminal-emulator\nx-terminal-emulator.1.gz\n/usr/share/man/man1/x-terminal-emulator.1.gz\n"
        "\n/usr/bin/xterm\n20\n/usr/share/man/man1/xterm.1.gz\n/usr/bin/konsole\n40\n\n\n")
    assert replace.alternative_paths(tmp_path, "x-terminal-emulator") == ["/usr/bin/xterm", "/usr/bin/konsole"]
    assert replace.alternative_paths(tmp_path, "nothing") == []


def test_replace_browser(project, nochroot):
    r = project.rootfs
    _pkg(r, "firefox-esr", ["/usr/bin/firefox-esr", "/usr/share/applications/firefox-esr.desktop"],
         {"firefox-esr.desktop": "[Desktop Entry]\nType=Application\nName=Firefox\nMimeType=text/html;\n"})
    _pkg(r, "chromium", ["/usr/bin/chromium", "/usr/share/applications/chromium.desktop"],
         {"chromium.desktop": "[Desktop Entry]\nType=Application\nName=Chromium\nMimeType=text/html;x-scheme-handler/http;\n"})
    alt = r / "var/lib/dpkg/alternatives"
    alt.mkdir(parents=True)
    (alt / "x-www-browser").write_text("auto\n/usr/bin/x-www-browser\n\n/usr/bin/firefox-esr\n70\n"
                                       "/usr/bin/chromium\n40\n\n")
    gnome = r / "etc/xdg/gnome-mimeapps.list"
    gnome.parent.mkdir(parents=True, exist_ok=True)
    gnome.write_text("[Default Applications]\ntext/html=firefox-esr.desktop;\n")
    replace.Replacer(project).replace("browser", "chromium", ["firefox-esr"])
    assert ["update-alternatives", "--set", "x-www-browser", "/usr/bin/chromium"] in nochroot
    assert ["remove", "firefox-esr"] in nochroot
    assert not any(c[0] == "install" for c in nochroot)  # chromium was installed already
    assert replace.read_defaults(r)["x-scheme-handler/https"] == "chromium.desktop;"
    assert "text/html=chromium.desktop;" in gnome.read_text()
    st = {x["role"]: x for x in replace.status(r)}
    assert st["browser"]["default"] == "chromium.desktop"
    assert set(st["browser"]["installed"]) == {"firefox-esr", "chromium"}
    assert project.state["default_apps"]["browser"] == "chromium"


def test_removal_keeps_the_desktop(project, monkeypatch):
    from eduka_customizer.core import apt, chroot
    calls = []
    sim = "Remv firefox-esr [1]\nRemv gnome-core [1]\nRemv task-gnome-desktop [3]\n"
    deps = ("gnome-core\n  Depends: gnome-shell\n  Depends: nautilus\n |Depends: firefox-esr\n"
            "  Recommends: <gnome-www-browser>\n    epiphany-browser\ntask-gnome-desktop\n  Depends: gnome-core\n")
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, cmd, **k: sim if cmd[:2] == ["apt-get", "-s"] else deps)
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, **k: calls.append(list(cmd)) or 0)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    for name in ("gnome-shell", "nautilus", "firefox-esr", "epiphany-browser"):
        _pkg(project.rootfs, name, [])
    apt.Packages(project).remove(["firefox-esr"])
    assert ["apt-mark", "manual", "epiphany-browser", "gnome-shell", "nautilus"] in calls
    assert calls.index(["apt-mark", "manual", "epiphany-browser", "gnome-shell", "nautilus"]) < \
        next(i for i, c in enumerate(calls) if "purge" in c)


# Checks before building ----------------------------------------------------------------------

def test_preflight_on_a_bare_rootfs(project):
    results = preflight.run(project)
    by = {x.title: x for x in results}
    assert by["Distribution"].level == "ok"
    assert by["Kernel"].level == "warn"  # the build installs one
    assert by["Live boot support"].level == "warn"  # live-config missing
    assert by["Identity"].level == "ok"
    assert by["Free disk space"].level in ("ok", "fail")
    assert all(x.level in preflight.LEVELS for x in results)


def test_preflight_finds_problems(blank_project):
    r = blank_project.rootfs
    st = r / "var/lib/dpkg/status"
    st.write_text(st.read_text() + "\nPackage: broken\nStatus: install ok half-configured\nVersion: 1\n")
    (r / "usr/sbin").mkdir(parents=True, exist_ok=True)
    (r / "usr/sbin/policy-rc.d").write_text("#!/bin/sh\nexit 101\n")
    (r / "home/teacher").mkdir(parents=True)
    by = {}
    for x in preflight.run(blank_project):
        by.setdefault(x.title, []).append(x)
    assert by["Package database"][0].level == "fail" and "broken" in by["Package database"][0].detail
    assert by["Identity"][0].level == "warn"  # no name: the image's own name is used
    assert by["Services"][0].level == "warn"
    assert any("teacher" in x.detail for x in by["Private data"])
    assert preflight.summary(preflight.run(blank_project))[0] >= 1


def test_preflight_without_system(tmp_path):
    p = Project.create(tmp_path / "empty")
    import shutil
    shutil.rmtree(p.rootfs)
    p.rootfs.mkdir()
    res = preflight.run(p)
    assert res[0].level == "fail" and res[0].page == "ProjectPage"


# Steps ---------------------------------------------------------------------------------------

def test_steps_state(tmp_path):
    p = Project.create(tmp_path / "s")
    assert p.state["steps_done"] == [] and not p.step_done("sources")
    p.mark_step("sources")
    assert Project.open(p.path).step_done("sources")
    p.mark_step("sources", False)
    assert not Project.open(p.path).step_done("sources")
    p.mark_all_steps()
    assert Project.open(p.path).step_done("anything")
    # Projects made before 0.15 keep every menu open.
    data = json.loads(p.state_file.read_text())
    del data["steps_done"]
    p.state_file.write_text(json.dumps(data))
    assert Project.open(p.path).step_done("desktop")


GUI_STEPS = """
import sys
from eduka_customizer.qt.widgets import QApplication
app = QApplication([])
from eduka_customizer.core.project import Project
from eduka_customizer.gui.main_window import MainWindow, SECTIONS
w = MainWindow()
keys = [s.key for s in w.sections]
assert keys == [s[0] for s in SECTIONS]
assert [s.step for s in w.steps] == list(range(1, 15))
assert not w.section_open(w.sections[keys.index("sources")])
w.project = Project.open(sys.argv[1])
w.update_state()
open_ = [s.key for s in w.sections if w.section_open(s)]
assert open_ == ["start", "wizard", "sources", "settings", "about"], open_
w.next_step(w.steps[1], w.steps[2])
assert w.section_open(w.sections[keys.index("identity")])
assert not w.section_open(w.sections[keys.index("users")])
w.go("UsersPage")
assert w.stack.currentWidget().key == "identity"
w.go("BrandingPage")
sec = w.stack.currentWidget()
assert sec.key == "identity" and sec.current().__class__.__name__ == "BrandingPage"
w.project.mark_all_steps()
w.update_state()
w.go("ReplaceAppsPage")
assert w.stack.currentWidget().key == "software"
print("ok", len(w.pages), len(w.sections))
"""


def test_gui_steps_and_merged_menus(tmp_path):
    p = Project.create(tmp_path / "gui")
    from tests.conftest import make_rootfs_into
    make_rootfs_into(p.rootfs)
    p.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", GUI_STEPS, str(p.path)], capture_output=True, text=True,
                         env=env, timeout=120)
    assert res.returncode == 0, res.stderr[-3000:]
    assert res.stdout.startswith("ok 25 17")


def test_cli_check_and_apps(project):
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    project.save()
    res = subprocess.run([sys.executable, "-m", "eduka_customizer", "--project", str(project.path), "check"],
                         capture_output=True, text=True, env=env, timeout=120)
    assert "Distribution" in res.stdout and "problem(s)" in res.stdout, res.stderr
    res = subprocess.run([sys.executable, "-m", "eduka_customizer", "apps", "roles"], capture_output=True,
                         text=True, env=env, timeout=60)
    assert res.returncode == 0 and "browser" in res.stdout
    res = subprocess.run([sys.executable, "-m", "eduka_customizer", "desktop", "catalog"], capture_output=True,
                         text=True, env=env, timeout=60)
    assert "full_apps" in res.stdout and "hyprland" in res.stdout


def test_old_edukasaun_settings_section(tmp_path):
    from eduka_customizer.core.config import Settings
    conf = tmp_path / "old.conf"
    conf.write_text("[edukasaun]\nrepo = /srv/eduka-desktop\nref = v2\n")
    s = Settings(conf)
    assert s.get("eduka_desktop", "repo") == "/srv/eduka-desktop" and s.get("eduka_desktop", "ref") == "v2"
    conf.write_text("[edukasaun]\nrepo = /old\n[eduka_desktop]\nrepo = /new\n")
    assert Settings(conf).get("eduka_desktop", "repo") == "/new"
