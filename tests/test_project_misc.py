import json

import pytest

from eduka_customizer.core import cleanup, isobuild, recipe
from eduka_customizer.core.branding import Branding
from eduka_customizer.core.desktop import DesktopManager, catalog, sessions
from eduka_customizer.core.eduka_desktop import EdukaDesktop, parse_defaults
from eduka_customizer.core.flatpak import Flatpak, check_ids
from eduka_customizer.core.project import Project, ProjectLocked

COMMON = '''
from pathlib import Path
VERSION = "0.9.10"
SETTINGS_REVISION = "0.9.6-transparency"
START_ICON = str(Path("/x")/"StartMenu.png")
THEME_DEFAULT = "Eduka-Default-Theme"
DEFAULT_PANEL = {"height": 42, "transparency": 0.54, "menu_icon": START_ICON, "theme_style": THEME_DEFAULT, "autohide": False}
DEFAULT_MENU = {"mode": "Eduka-Desktop", "language": "system"}
DEFAULT_DESKTOP = {"layout": "Grid", "corner_radius": 24}
'''


def test_project_state_and_lock(tmp_path):
    p = Project.create(tmp_path / "p", name="Test")
    p.lock()
    q = Project.open(tmp_path / "p")
    with pytest.raises(ProjectLocked):
        q.lock()
    p.record("x", "y")
    assert Project.open(tmp_path / "p").state["history"][-1]["action"] == "x"
    p.unlock()
    q.lock()
    q.unlock()


def test_iso_filename(project):
    project.state["identity"].update({"id": "edukasaun", "version": "1.0"})
    project.state["distro"] = {"suite": "stable", "arch": "amd64", "id": "debian"}
    name = isobuild.iso_filename("{id}-{version}-{suite}-{arch}.iso", project)
    assert name == "edukasaun-1.0-stable-amd64.iso"
    assert isobuild.iso_filename("{bogus}", project).endswith(".iso")
    assert isobuild.iso_filename("a b/../c", project) == "a-b-..-c.iso"


def test_squashfs_args():
    o = isobuild.BuildOptions(compression="xz")
    assert isobuild.squashfs_args(o, "amd64")[:4] == ["-comp", "xz", "-b", "1M"]
    assert "-Xbcj" in isobuild.squashfs_args(o, "amd64")
    o = isobuild.BuildOptions(compression="zstd", level=99)
    assert isobuild.squashfs_args(o, "amd64")[-1] == "22"
    assert isobuild.sanitize_label("Edukasaun OS 1.0 (Kameli) amd64 longer label") == "Edukasaun OS 1.0 _Kameli_ amd64 "[:32]


def test_eduka_defaults(project, tmp_path):
    common = project.rootfs / "usr/lib/edukasaun-desktop/eduka_common.py"
    common.parent.mkdir(parents=True)
    common.write_text(COMMON)
    d = parse_defaults(common)
    assert d["SETTINGS_REVISION"] == "0.9.6-transparency"
    assert "menu_icon" not in d["DEFAULT_PANEL"] and d["DEFAULT_PANEL"]["theme_style"] == "Eduka-Default-Theme"
    ed = EdukaDesktop(project)
    ed.write_defaults(panel={"height": 48, "theme_style": "Liquid Glass"}, desktop={"layout": "List"})
    panel = json.loads((project.rootfs / "etc/skel/.config/eduka-desktop/panel/settings.json").read_text())
    assert panel["height"] == 48 and panel["transparency"] == 0.54
    assert panel["_settings_revision"] == "0.9.6-transparency"
    cur = ed.current_defaults()
    assert cur["desktop"]["layout"] == "List" and "_settings_revision" not in cur["panel"]


def test_eduka_build_tree(project, tmp_path):
    import shutil
    src = tmp_path / "eduka-src"
    (src / "DEBIAN").mkdir(parents=True)
    (src / "usr/bin").mkdir(parents=True)
    (src / "DEBIAN/control").write_text("Package: edukasaun-desktop-menu\nVersion: 0.9.10\nArchitecture: all\n"
                                        "Maintainer: x <x@y>\nInstalled-Size: 1\nDescription: test\n")
    (src / "DEBIAN/postinst").write_text("#!/bin/sh\nexit 0\n")
    (src / "usr/bin/eduka-panel").write_text("#!/usr/bin/env python3\n")
    (src / "README.md").write_text("x")
    if not shutil.which("dpkg-deb"):
        pytest.skip("dpkg-deb missing")
    ed = EdukaDesktop(project)
    ed.fetch(str(src))
    deb = ed.build()
    assert deb.name == "edukasaun-desktop-menu_0.9.10_all.deb"
    import subprocess
    listing = subprocess.check_output(["dpkg-deb", "-c", str(deb)], text=True)
    assert "./usr/bin/eduka-panel" in listing and "README" not in listing
    assert "-rwxr-xr-x root/root" in [l for l in listing.splitlines() if "eduka-panel" in l][0]


def test_catalog_and_sessions(project):
    ids = [d["id"] for d in catalog()["desktops"]]
    assert ids[0] == "eduka" and "kde" in ids and "i3" in ids
    xs = project.rootfs / "usr/share/xsessions"
    xs.mkdir(parents=True)
    (xs / "edukasaun-desktop.desktop").write_text("[Desktop Entry]\nName=Edukasaun Desktop\nExec=startlxqt\n"
                                                  "DesktopNames=LXQt;Edukasaun\n")
    s = sessions(project.rootfs)
    assert s[0]["id"] == "edukasaun-desktop" and s[0]["exec"] == "startlxqt"


def test_lightdm_conf(project):
    dm = DesktopManager(project)
    dm._lightdm_conf({"user-session": "edukasaun-desktop"})
    text = (project.rootfs / "etc/lightdm/lightdm.conf.d/50-eduka-customizer.conf").read_text()
    assert "[Seat:*]" in text and "user-session = edukasaun-desktop" in text


def test_flatpak_ids_and_firstboot(project):
    check_ids(["org.kde.gcompris", "org.geogebra.GeoGebra"])
    with pytest.raises(ValueError):
        check_ids(["gcompris"])
    with pytest.raises(ValueError):
        check_ids(["org.x.y; rm"])
    (project.rootfs / "usr/bin/flatpak").write_text("")
    fp = Flatpak(project)
    fp.set_firstboot(["org.kde.gcompris"])
    assert fp.firstboot_list() == ["org.kde.gcompris"]
    unit = (project.rootfs / "etc/systemd/system/eduka-flatpak-firstboot.service").read_text()
    assert "ConditionKernelCommandLine=!boot=live" in unit
    assert (project.rootfs / "etc/systemd/system/multi-user.target.wants/eduka-flatpak-firstboot.service").is_symlink()
    fp.set_firstboot([])
    assert fp.firstboot_list() == []


def test_plymouth_generate_and_import(project, tmp_path):
    b = Branding(project)
    logo = tmp_path / "logo.png"
    logo.write_bytes(b"\x89PNG\r\n\x1a\n")
    b.generate_plymouth("edukasaun", logo)
    t = project.rootfs / "usr/share/plymouth/themes/edukasaun"
    assert (t / "edukasaun.plymouth").exists() and (t / "bar.png").read_bytes().startswith(b"\x89PNG")
    assert b.plymouth_themes() == ["edukasaun"]
    with pytest.raises(ValueError):
        b.generate_plymouth("../evil", logo)
    src = tmp_path / "theme/mytheme"
    src.mkdir(parents=True)
    (src / "mytheme.plymouth").write_text("[Plymouth Theme]\nModuleName=script\n[script]\n"
                                          "ImageDir=/old\nScriptFile=/old/mytheme.script\n")
    assert b.import_plymouth(src) == "mytheme"
    text = (project.rootfs / "usr/share/plymouth/themes/mytheme/mytheme.plymouth").read_text()
    assert "ImageDir=/usr/share/plymouth/themes/mytheme" in text
    assert "ScriptFile=/usr/share/plymouth/themes/mytheme/mytheme.script" in text


def test_identity_files(project, monkeypatch):
    b = Branding(project)
    monkeypatch.setattr(b, "_divert", lambda path: None)
    ident = dict(project.state["identity"])
    b.apply_identity(ident)
    osr = (project.rootfs / "etc/os-release").read_text()
    assert "ID=edukasaun" in osr and "ID_LIKE=debian" in osr and "VERSION_CODENAME=trixie" in osr
    assert (project.rootfs / "etc/hostname").read_text() == "edukasaun\n"
    assert 'LIVE_USERNAME="live"' in (project.rootfs / "etc/live/config.conf.d/50-eduka-customizer.conf").read_text()
    with pytest.raises(ValueError):
        b.set_hostname("Bad_Host")


def test_cleanup_files(project, monkeypatch):
    from eduka_customizer.core import chroot
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, *a, **k: 0)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    r = project.rootfs
    (r / "etc/machine-id").write_text("abc\n")
    (r / "root").mkdir()
    (r / "root/.bash_history").write_text("secret")
    (r / "var/log").mkdir(parents=True)
    (r / "var/log/syslog").write_text("log")
    (r / "var/log/syslog.1.gz").write_text("x")
    (r / "etc/ssh").mkdir()
    (r / "etc/ssh/ssh_host_rsa_key").write_text("k")
    cleanup.run(project)
    assert (r / "etc/machine-id").read_text() == ""
    assert not (r / "root/.bash_history").exists()
    assert (r / "var/log/syslog").read_text() == "" and not (r / "var/log/syslog.1.gz").exists()
    assert not (r / "etc/ssh/ssh_host_rsa_key").exists()


def test_kernels_sorted(tmp_path):
    (tmp_path / "boot").mkdir()
    for v in ("6.12.9+deb13-amd64", "6.12.38+deb13-amd64", "6.1.0-30-amd64"):
        (tmp_path / "boot" / ("vmlinuz-" + v)).write_text("")
    assert cleanup.kernels(tmp_path)[-1] == "6.12.38+deb13-amd64"


def test_recipe_export_and_unknown_action(project, tmp_path):
    project.record("apt-install", "vlc gimp")
    project.record("apt-remove", "gimp")
    data = recipe.export(project)
    actions = [s["action"] for s in data["steps"]]
    assert actions[0] == "identity" and actions[-1] == "build"
    inst = [s for s in data["steps"] if s["action"] == "apt-install"][0]
    assert inst["packages"] == ["vlc"]
    f = tmp_path / "r.json"
    f.write_text(json.dumps({"steps": [{"action": "nope"}]}))
    with pytest.raises(ValueError):
        recipe.apply(project, f)
