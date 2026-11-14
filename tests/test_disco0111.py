"""D!sco 0.11.1: startup, easy branding, user folders, internet check, the new flow."""

import os
import pwd
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def unit(root, name, text, wanted_by=None):
    p = Path(root, "lib/systemd/system", name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    if wanted_by:
        d = Path(root, "etc/systemd/system", wanted_by + ".wants")
        d.mkdir(parents=True, exist_ok=True)
        (d / name).symlink_to("/lib/systemd/system/" + name)


def test_startup_services(project, monkeypatch):
    from disco.core import runner, startup
    monkeypatch.setattr(runner, "which", lambda name: None)       # the links are set directly
    r = project.rootfs
    (r / "var/lib/dpkg/status").write_text("Package: systemd-sysv\nStatus: install ok installed\n\n")
    unit(r, "ssh.service", "[Unit]\nDescription=SSH\n[Install]\nWantedBy=multi-user.target\n", "multi-user.target")
    unit(r, "cups.service", "[Unit]\nDescription=CUPS\n[Install]\nWantedBy=multi-user.target printer.target\n")
    unit(r, "dbus.service", "[Unit]\nDescription=D-Bus\n[Install]\nWantedBy=multi-user.target\n", "multi-user.target")
    unit(r, "static.service", "[Unit]\nDescription=started by others\n")
    sv = {s["unit"]: s for s in startup.services(project)}
    assert sv["ssh.service"]["enabled"] and not sv["cups.service"]["enabled"]
    assert sv["ssh.service"]["description"] == "SSH server (remote login)"
    assert "static.service" not in sv and sv["dbus.service"]["essential"]
    startup.set_service(project, "cups.service", True)
    assert (r / "etc/systemd/system/multi-user.target.wants/cups.service").is_symlink()
    assert (r / "etc/systemd/system/printer.target.wants/cups.service").is_symlink()
    startup.set_service(project, "ssh.service", False)
    assert not (r / "etc/systemd/system/multi-user.target.wants/ssh.service").exists()
    with pytest.raises(ValueError, match="needed"):
        startup.set_service(project, "dbus.service", False)
    with pytest.raises(ValueError):
        startup.set_service(project, "bad;name", True)


def test_startup_sysv(project, nochroot_calls):
    from disco.core import startup
    r = project.rootfs
    (r / "var/lib/dpkg/status").write_text("Package: sysvinit-core\nStatus: install ok installed\n\n")
    (r / "etc/init.d").mkdir(parents=True, exist_ok=True)
    (r / "etc/init.d/cron").write_text("#!/bin/sh\n# Short-Description: Regular background program processing\n")
    (r / "etc/rc2.d").mkdir(parents=True, exist_ok=True)
    (r / "etc/rc2.d/S01cron").symlink_to("../init.d/cron")
    sv = startup.services(project)
    assert [s["unit"] for s in sv] == ["cron"] and sv[0]["enabled"]
    startup.set_service(project, "cron", False)
    assert ["update-rc.d", "cron", "disable"] in nochroot_calls


@pytest.fixture
def nochroot_calls(monkeypatch):
    from disco.core import chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(list(cmd)) or 0)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    return calls


def test_startup_applications(project):
    from disco.core import startup
    d = project.rootfs / "etc/xdg/autostart"
    d.mkdir(parents=True)
    (d / "nm-applet.desktop").write_text("[Desktop Entry]\nName=Network\nExec=nm-applet\nOnlyShowIn=XFCE;\n\n"
                                         "[Desktop Action Foo]\nName=foo\n")
    startup.set_application(project, "nm-applet.desktop", False)
    text = (d / "nm-applet.desktop").read_text()
    assert "Hidden=true" in text and text.index("Hidden=true") < text.index("[Desktop Action Foo]")
    apps = {a["file"]: a for a in startup.applications(project)}
    assert not apps["nm-applet.desktop"]["enabled"] and apps["nm-applet.desktop"]["where"] == "only in XFCE"
    startup.set_application(project, "nm-applet.desktop", True)
    assert "Hidden" not in (d / "nm-applet.desktop").read_text()
    f = startup.add_application(project, "Welcome page", "firefox-esr https://example.org")
    assert f == "disco-welcome-page.desktop" and (d / f).exists()
    with pytest.raises(ValueError):
        startup.remove_application(project, "nm-applet.desktop")
    startup.remove_application(project, f)
    assert not (d / f).exists()
    with pytest.raises(ValueError):
        startup.set_application(project, "../../etc/passwd", False)


def png(path, color="#3f51b5"):
    from disco.core import imaging
    from disco.qt import gui
    imaging._qt()
    img = gui.QImage(64, 64, gui.QImage.Format.Format_ARGB32)
    img.fill(gui.QColor(color))
    img.save(str(path))
    return path


def test_quickbrand(project, tmp_path, monkeypatch):
    from disco.core import quickbrand
    from disco.core.branding import Branding
    calls = []
    monkeypatch.setattr(Branding, "set_wallpaper", lambda self, image: calls.append(("wallpaper", image)))
    monkeypatch.setattr(Branding, "set_login_screen", lambda self, **k: calls.append(("login", k)))
    pic = png(tmp_path / "w.png")
    with pytest.raises(ValueError):
        quickbrand.apply(project, "wallpaper")             # nothing chosen yet
    stored = quickbrand.store(project, "wallpaper", pic)
    assert stored == project.path / "branding/pictures/wallpaper.png" and stored.exists()
    quickbrand.apply(project, "wallpaper")
    assert calls[-1] == ("wallpaper", stored)
    project.state["quickbrand"]["wallpaper"]["default"] = False
    out = quickbrand.apply(project, "wallpaper")
    assert out.parent == project.rootfs / "usr/share/backgrounds/edukasaun"   # only added, not the default
    quickbrand.store(project, "user", pic)
    quickbrand.apply(project, "user")
    assert (project.rootfs / "etc/skel/.face").exists()
    with pytest.raises(ValueError):
        quickbrand.store(project, "wallpaper", tmp_path / "missing.png")


def test_quickbrand_logo(project, tmp_path, monkeypatch):
    from disco.core import quickbrand
    from disco.core.branding import Branding
    monkeypatch.setattr(Branding, "set_login_screen", lambda self, **k: None)
    monkeypatch.setattr(Branding, "plymouth_current", lambda self: "custom-theme")   # a theme was chosen: keep it
    (project.rootfs / "usr/lib/os-release").write_text('NAME="Edukasaun OS"\nID=edukasaun\n')
    quickbrand.store(project, "logo", png(tmp_path / "l.png"))
    quickbrand.apply(project, "logo")
    r = project.rootfs
    assert (r / "usr/share/icons/hicolor/48x48/apps/edukasaun-logo.png").exists()
    assert (r / "usr/share/pixmaps/edukasaun-logo.png").exists()
    assert "LOGO=edukasaun-logo" in (r / "usr/lib/os-release").read_text()


def test_permissions(project, monkeypatch):
    from disco.core import permissions
    monkeypatch.delenv("PKEXEC_UID", raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)
    assert permissions.real_user() is None
    assert permissions.give_to_user(project.path) == 0      # nobody to give it to
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("no user 'nobody'")
    monkeypatch.setenv("PKEXEC_UID", str(nobody.pw_uid))
    assert permissions.real_user()[2] == "nobody"
    folders = permissions.share_user_folders(project)
    assert [f.name for f in folders] == permissions.USER_FOLDERS
    if os.geteuid() == 0:
        assert (project.path / "overlay").stat().st_uid == nobody.pw_uid
        assert project.rootfs.stat().st_uid == 0          # the system stays root's


def test_net_check(monkeypatch):
    from disco.core import net
    import urllib.error
    import urllib.request

    def refused(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", refused)
    assert net.online(timeout=1) is False

    def missing(req, timeout=0):
        raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
    monkeypatch.setattr(urllib.request, "urlopen", missing)
    assert net.online(timeout=1) is True                   # a server answered

    def offline(req, timeout=0):
        raise urllib.error.URLError("no route")
    monkeypatch.setattr(urllib.request, "urlopen", offline)
    assert net.online(timeout=1) is False


def test_old_step_names(project):
    project.state["steps_done"] = ["start", "sources", "identity", "users", "language", "desktop", "software",
                                   "advanced"]
    assert project.step_done("system") and project.step_done("software")
    assert project.step_done("startup") and project.step_done("files")
    project.state["steps_done"] = ["software"]
    assert not project.step_done("startup")          # a new project must really pass Startup
