import os
import shutil
import subprocess

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eduka_customizer.core import debpkg, desktop, imaging  # noqa: E402
from eduka_customizer.core.distrobrand import BrandingSpec, DistroBranding  # noqa: E402
from eduka_customizer.core.themes import Themes  # noqa: E402

needs_dpkg = pytest.mark.skipif(not shutil.which("dpkg-deb"), reason="dpkg-deb missing")


@pytest.fixture
def nochroot(monkeypatch):
    from eduka_customizer.core import apt, chroot
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, *a, **k: 0)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "install", lambda self, *a, **k: None)


def png(path, w=64, h=64, color="#00a879"):
    from eduka_customizer.qt import gui
    imaging._qt()
    img = gui.QImage(w, h, gui.QImage.Format.Format_ARGB32)
    img.fill(gui.QColor(color))
    img.save(str(path))
    return path


def test_bump_version():
    assert debpkg.bump_version("13.8", "edukasaun") == "13.8+edukasaun1"
    assert debpkg.bump_version("13.8+edukasaun4", "edukasaun") == "13.8+edukasaun5"


@needs_dpkg
def test_tree_build(tmp_path):
    tree = tmp_path / "pkg"
    (tree / "files/usr/share/x").mkdir(parents=True)
    (tree / "files/usr/share/x/a.txt").write_text("hi")
    (tree / "files/etc").mkdir()
    (tree / "files/etc/x.conf").write_text("k=v")
    debpkg.write_tree(tree, "x-test", "Dev <d@e.org>",
                      [{"Package": "x-test", "Depends": "dpkg", "Description": "Test\n Long text.",
                        "install": ["files/usr /", "files/etc /"],
                        "scripts": {"postinst": "#!/bin/sh\nset -e\n#DEBHELPER#\nexit 0\n"}}],
                      "1.0+1", ["first"])
    for f in ("control", "changelog", "copyright", "rules", "source/format", "x-test.install"):
        assert (tree / "debian" / f).exists()
    debs = debpkg.build_tree(tree, tmp_path / "out")
    assert [d.name for d in debs] == ["x-test_1.0+1_all.deb"]
    info = subprocess.check_output(["dpkg-deb", "-I", str(debs[0])], text=True)
    assert "Depends: dpkg" in info and "${misc:Depends}" not in info
    listing = subprocess.check_output(["dpkg-deb", "-c", str(debs[0])], text=True)
    assert "./usr/share/x/a.txt" in listing and "./etc/x.conf" in listing
    conf = subprocess.check_output(["dpkg-deb", "-f", str(debs[0]), "Package"], text=True)
    assert conf.strip() == "x-test"
    ctrl = subprocess.check_output(["dpkg-deb", "--ctrl-tarfile", str(debs[0])])
    assert b"conffiles" in ctrl and b"#DEBHELPER#" not in ctrl


def test_install_path_escape(tmp_path):
    tree = tmp_path / "pkg"
    debpkg.write_tree(tree, "x-test", "D <d@e.org>", [{"Package": "x-test", "Description": "t",
                                                       "install": ["../../etc /"]}], "1", ["x"])
    if shutil.which("dpkg-deb"):
        with pytest.raises(ValueError):
            debpkg.build_tree(tree, tmp_path / "out")


@needs_dpkg
def test_distro_branding_generate(project, tmp_path):
    from eduka_customizer.core import distro
    project.state["distro"] = distro.detect(project.rootfs).to_dict()
    r = project.rootfs
    (r / "usr/share/pixmaps").mkdir(parents=True)
    png(r / "usr/share/pixmaps/debian-logo.png", 48, 48, "#d70a53")
    (r / "etc/calamares/modules").mkdir(parents=True)
    (r / "etc/calamares/settings.conf").write_text("branding: debian\n")
    (r / "etc/calamares/modules/bootloader.conf").write_text("timeout: 5\n")
    spec = BrandingSpec.from_project(project)
    spec.logo, spec.wallpaper = str(png(tmp_path / "logo.png", 300, 300)), str(png(tmp_path / "w.png", 800, 450))
    db = DistroBranding(project)
    assert db.debian_logo_files() == ["/usr/share/pixmaps/debian-logo.png"]
    tree = db.generate(spec)
    data = tree / "files/usr/share/edukasaun-branding"
    diverts = dict(l.split("\t") for l in (data / "divert.list").read_text().splitlines())
    for target in ("/usr/lib/os-release", "/etc/issue", "/etc/issue.net", "/etc/lsb-release",
                   "/usr/share/pixmaps/debian-logo.png", "/etc/calamares/settings.conf",
                   "/etc/calamares/modules/bootloader.conf"):
        assert target in diverts
    osr = (tree / "files" / diverts["/usr/lib/os-release"].lstrip("/")).read_text()
    assert "ID=edukasaun" in osr and "ID_LIKE=debian" in osr and "VERSION_CODENAME=trixie" in osr
    assert imaging.image_size(tree / "files" / diverts["/usr/share/pixmaps/debian-logo.png"].lstrip("/")) == (48, 48)
    assert (tree / "files/usr/share/distro-info/edukasaun.csv").exists()
    assert (tree / "files/etc/calamares/branding/edukasaun/branding.desc").exists()
    assert "efiBootloaderId: \"debian\"" in (tree / "files" / diverts["/etc/calamares/modules/bootloader.conf"].lstrip("/")).read_text()
    grub = (tree / "files/etc/default/grub.d/90-edukasaun.cfg").read_text()
    assert 'GRUB_DISTRIBUTOR="Edukasaun OS"' in grub and "GRUB_BACKGROUND" in grub
    assert (data / "efi-sync").exists()
    debs = db.build()
    assert debs[0].name == "edukasaun-branding_1.0+1_all.deb"
    scripts = subprocess.check_output(["dpkg-deb", "--ctrl-tarfile", str(debs[0])])
    assert b"postinst" in scripts and b"prerm" in scripts


def test_branding_spec_validation():
    with pytest.raises(ValueError):
        BrandingSpec(os_id="Bad ID").validate()
    with pytest.raises(ValueError):
        BrandingSpec(accent="green").validate()


def test_themes_apply(project, nochroot):
    r = project.rootfs
    (r / "usr/share/themes/Arc/gtk-3.0").mkdir(parents=True)
    (r / "usr/share/icons/Papirus").mkdir(parents=True)
    (r / "usr/share/icons/Papirus/index.theme").write_text("[Icon Theme]\nName=Papirus\n")
    (r / "usr/share/icons/Breeze_Snow/cursors").mkdir(parents=True)
    (r / "usr/share/icons/Breeze_Snow/index.theme").write_text("[Icon Theme]\n")
    xs = r / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xsettings.xml"
    xs.parent.mkdir(parents=True)
    xs.write_text('<property name="ThemeName" type="string" value="Adwaita"/>')
    th = Themes(project)
    assert th.gtk_themes() == ["Arc"] and th.icon_themes() == ["Papirus"] and th.cursor_themes() == ["Breeze_Snow"]
    th.apply("Arc", "Papirus", "Breeze_Snow", "Noto Sans 10", dark=True)
    cur = th.current()
    assert cur == {"gtk": "Arc", "icons": "Papirus", "cursor": "Breeze_Snow", "font": "Noto Sans 10", "dark": True}
    assert 'value="Arc"' in xs.read_text()
    assert "icon_theme=Papirus" in (r / "etc/xdg/lxqt/lxqt.conf").read_text()
    assert "gtk-4.0" not in str(list((r / "etc/gtk-4.0").glob("*"))) or \
        "gtk-theme-name" not in (r / "etc/gtk-4.0/settings.ini").read_text()
    with pytest.raises(ValueError):
        th.apply("Arc; rm -rf /")


def test_theme_import_archive(project, nochroot, tmp_path):
    import tarfile
    src = tmp_path / "MyIcons"
    (src / "48x48").mkdir(parents=True)
    (src / "index.theme").write_text("[Icon Theme]\nName=MyIcons\n")
    arc = tmp_path / "icons.tar.gz"
    with tarfile.open(arc, "w:gz") as tf:
        tf.add(src, arcname="MyIcons")
    assert Themes(project).import_theme(arc) == ["MyIcons (icons)"]
    assert (project.rootfs / "usr/share/icons/MyIcons/index.theme").exists()


def test_compositor_and_session_type(project, nochroot):
    r = project.rootfs
    dm = desktop.DesktopManager(project)
    dm.set_compositor("picom", "glass")
    assert 'blur-method = "dual_kawase"' in (r / "etc/xdg/picom.conf").read_text()
    dm.set_compositor("none")
    assert "Hidden=true" in (r / "etc/skel/.config/autostart/picom.desktop").read_text()
    dm.set_compositor("labwc")
    assert "compositor=labwc" in (r / "etc/xdg/lxqt/session.conf").read_text().replace(" ", "")
    (r / "etc/gdm3").mkdir(parents=True)
    (r / "etc/gdm3/daemon.conf").write_text("[daemon]\n#WaylandEnable=false\n")
    dm.set_session_type("gnome", "x11")
    assert "WaylandEnable=false" in (r / "etc/gdm3/daemon.conf").read_text()
    assert project.state["desktop"]["session"] == "gnome-xorg"
    with pytest.raises(ValueError):
        dm.set_session_type("eduka", "wayland")


def test_catalog_login_screens():
    ids = [d["id"] for d in desktop.catalog()["display_managers"]]
    assert {"lightdm", "lightdm-slick", "sddm", "gdm3", "lxdm"} <= set(ids)
    assert desktop.display_manager("lightdm-slick")["greeter"] == "slick-greeter"


def test_workshop_verify_detects_missing(project):
    from eduka_customizer.core.workshop import Workshop
    r = project.rootfs
    info = r / "var/lib/dpkg/info"
    info.mkdir(parents=True)
    (info / "bash.list").write_text("/.\n/bin\n/usr/bin/bash\n")
    ws = Workshop(project)
    (ws.path("bash") / "DEBIAN").mkdir(parents=True)
    (ws.path("bash") / "usr/bin").mkdir(parents=True)
    (ws.path("bash") / "usr/bin/bash").write_text("")
    assert ws.verify("bash") == ["/bin"]
    with pytest.raises(RuntimeError, match="missing"):
        ws.build("bash", install=False)


def test_log_dir_safe(tmp_path, monkeypatch):
    from eduka_customizer.core import log
    d = tmp_path / "logs"
    assert log._safe_dir(str(d)) == str(d)
    assert oct(os.stat(d).st_mode & 0o7777) == "0o1777"
