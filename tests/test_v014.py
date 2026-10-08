import gzip
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eduka_customizer.core import assets, catalog, desktop as dsk, distro, profiles  # noqa: E402


def png(path, color="#00a879"):
    from eduka_customizer.core import imaging
    from eduka_customizer.qt import gui
    imaging._qt()
    img = gui.QImage(32, 18, gui.QImage.Format.Format_ARGB32)
    img.fill(gui.QColor(color))
    img.save(str(path))
    return path


@pytest.fixture
def nochroot(monkeypatch):
    from eduka_customizer.core import apt, chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(cmd) or 0)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "install", lambda self, names, **k: calls.append(["install"] + list(names)))
    monkeypatch.setattr(apt.Packages, "install_debs", lambda self, files, **k: calls.append(["debs"] + [str(f) for f in files]))
    return calls


def _themes(base):
    gtk = base / "Nordic"
    (gtk / "gtk-3.0").mkdir(parents=True)
    (gtk / "index.theme").write_text("[X-GNOME-Metatheme]\nName=Nordic\n")
    (gtk / "gtk-3.0/gtk.css").write_text("* {}\n")
    icons = base / "pack/Tela"
    (icons / "48x48/apps").mkdir(parents=True)
    (icons / "index.theme").write_text("[Icon Theme]\nName=Tela\nDirectories=48x48/apps\n")
    cur = base / "pack/Bibata"
    (cur / "cursors").mkdir(parents=True)
    (cur / "index.theme").write_text("[Icon Theme]\nName=Bibata\n")
    sddm = base / "sugar"
    sddm.mkdir()
    (sddm / "metadata.desktop").write_text("[SddmGreeterTheme]\nName=Sugar\n")
    (sddm / "Main.qml").write_text("import QtQuick 2.0\n")
    return gtk, base / "pack", sddm


def test_assets_recognized_and_placed(project, tmp_path, nochroot):
    src = tmp_path / "src"
    gtk, pack, sddm = _themes(src)
    archive = tmp_path / "pack.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        tf.add(pack, arcname="pack")
    zipped = tmp_path / "gtk.zip"
    with zipfile.ZipFile(zipped, "w") as zf:
        for f in gtk.rglob("*"):
            zf.write(f, f.relative_to(src))
    font = tmp_path / "Edu Sans.ttf"
    font.write_bytes(b"\x00\x01\x00\x00fake")
    wall = png(tmp_path / "beach.png")
    deb = tmp_path / "theme.deb"
    deb.write_bytes(b"!<arch>\n")
    kinds = sorted(k for k, _n, _s in assets.Assets(project).scan([src]))
    assert kinds == ["cursor-theme", "gtk-theme", "icon-theme", "sddm-theme"]
    added = assets.Assets(project).add([archive, zipped, font, wall, sddm, deb])
    r = project.rootfs
    assert (r / "usr/share/icons/Tela/index.theme").exists() and (r / "usr/share/icons/Bibata/cursors").is_dir()
    assert (r / "usr/share/themes/Nordic/gtk-3.0/gtk.css").exists()
    assert (r / "usr/share/sddm/themes/sugar/Main.qml").exists()
    assert (r / "usr/share/fonts/truetype/eduka-custom/Edu-Sans.ttf").exists()
    assert ("wallpaper", "beach.png") in added and ("deb", "theme.deb") in added
    assert nochroot and nochroot[-1][0] == "debs"
    with pytest.raises(ValueError):
        assets.Assets(project).add([tmp_path / "Edu Sans.ttf".replace("ttf", "txt")] if False else
                                   [_text(tmp_path / "notes.txt")])


def _text(p):
    p.write_text("hello")
    return p


def test_wallpaper_gallery(project, tmp_path, nochroot):
    w = assets.Wallpapers(project)
    names = w.add([png(tmp_path / "a.png"), png(tmp_path / "b.jpg", "#ff0000")])
    folder = tmp_path / "more"
    folder.mkdir()
    png(folder / "a.png", "#0000ff")
    names += w.add([folder])
    assert names == ["a.png", "b.jpg", "a-2.png"]
    assert w.default() == "a.png"  # the first one becomes the default
    w.set_default("b.jpg")
    assert w.default() == "b.jpg"
    conf = project.rootfs / "etc/xdg/pcmanfm-qt/lxqt/settings.conf"
    assert "/usr/share/backgrounds/edukasaun/b.jpg" in conf.read_text()
    xml = (project.rootfs / "usr/share/gnome-background-properties/edukasaun.xml").read_text()
    assert xml.count("<wallpaper ") == 3
    assert (project.rootfs / "usr/share/cinnamon-background-properties/edukasaun.xml").exists()
    w.remove("b.jpg")
    assert w.default() in ("a.png", "a-2.png") and len(w.list()) == 2


def _lists(rootfs):
    lists = rootfs / "var/lib/apt/lists"
    lists.mkdir(parents=True)
    (lists / "deb.debian.org_debian_dists_trixie_main_binary-amd64_Packages").write_text(
        "Package: gcompris-qt\nVersion: 25.0-1\nSection: games\nInstalled-Size: 9000\n"
        "Description: educational games for small children\n\n"
        "Package: libfoo1\nVersion: 1\nSection: libs\nDescription: a library\n\n")
    with gzip.open(lists / "deb.debian.org_debian_dists_trixie_contrib_binary-amd64_Packages.gz", "wt") as fh:
        fh.write("Package: vlc\nVersion: 3.0\nSection: video\nInstalled-Size: 100\nDescription: media player\n"
                 " long description\n\n")


def test_catalog_lists_and_desktop_apps(project):
    r = project.rootfs
    _lists(r)
    cat = catalog.Catalog(r)
    avail = cat.available()
    assert set(avail) == {"gcompris-qt", "libfoo1", "vlc"} and avail["vlc"]["section"] == "video"
    assert catalog.is_app("gcompris-qt", "games") and not catalog.is_app("libfoo1", "libs")
    (r / "usr/share/applications").mkdir(parents=True)
    (r / "usr/share/applications/vlc.desktop").write_text("[Desktop Entry]\nType=Application\nName=VLC\n")
    (r / "usr/share/applications/hidden.desktop").write_text("[Desktop Entry]\nType=Application\nNoDisplay=true\n")
    (r / "var/lib/dpkg/info").mkdir(parents=True, exist_ok=True)
    (r / "var/lib/dpkg/info/vlc.list").write_text("/usr/share/applications/vlc.desktop\n")
    with open(r / "var/lib/dpkg/status", "a") as fh:
        fh.write("\nPackage: vlc\nStatus: install ok installed\nVersion: 3.0\nPriority: optional\n"
                 "Installed-Size: 100\nDescription: media player\n")
    apps = cat.desktop_apps()
    assert apps == [{"package": "vlc", "names": ["VLC"], "comment": "", "protected": False, "size": 100,
                     "name": "VLC"}]


PACKAGE_BROWSER = """
import sys
from eduka_customizer.qt.widgets import QApplication
app = QApplication([])
from eduka_customizer.qt.core import Qt
from eduka_customizer.gui.package_browser import PackageBrowser
b = PackageBrowser()
b.load(sys.argv[1])
assert len(b.model.rows) == 5, len(b.model.rows)  # 3 available + bash and live-boot (installed)
b.show_combo.setCurrentIndex(1)
b.search.setText("media")
b._apply_filter()
assert [b.model.rows[i]["name"] for i in b.model.visible] == ["vlc"]
b.model.setData(b.model.index(0, 0), 2, Qt.ItemDataRole.CheckStateRole)
assert b.changes() == (["vlc"], [])
b.select(["gcompris-qt", "nonexistent"])
assert b.changes() == (["gcompris-qt", "vlc"], [])
b.reset()
assert b.changes() == ([], [])
print("ok")
"""


def test_package_browser(project):
    _lists(project.rootfs)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", PACKAGE_BROWSER, str(project.rootfs)], capture_output=True,
                         text=True, env=env, timeout=120)
    assert res.returncode == 0 and res.stdout.strip() == "ok", res.stderr[-2000:]


def test_native_compositors():
    choices, best = dsk.compositors_for("gnome")
    ids = [c["id"] for c in choices]
    assert best == "mutter" and "mutter" in ids and "picom" not in ids and "xfwm4" not in ids
    choices, best = dsk.compositors_for("xfce")
    assert best == "xfwm4" and {"picom", "xfwm4"} <= {c["id"] for c in choices}
    assert dsk.compositors_for("cinnamon")[1] == "muffin" and dsk.compositors_for("kde")[1] == "kwin"
    assert dsk.compositors_for("eduka")[1] == "picom" and dsk.compositors_for("lxqt", "wayland")[1] == "labwc"
    # On Wayland KDE and GNOME are their own compositor
    assert [c["id"] for c in dsk.compositors_for("kde", "wayland")[0]] == ["kwin"]
    assert dsk.compositors_for("gnome", "wayland")[1] == "mutter"


def test_set_compositor_native_and_conflict(project, nochroot):
    r = project.rootfs
    (r / "etc/xdg/autostart").mkdir(parents=True)
    (r / "etc/xdg/autostart/picom.desktop").write_text("[Desktop Entry]\nType=Application\nName=picom\nExec=picom\n"
                                                      "OnlyShowIn=GNOME;\n")
    m = dsk.DesktopManager(project)
    project.state.setdefault("desktop", {})["id"] = "gnome"
    with pytest.raises(ValueError, match="Mutter"):
        m.set_compositor("picom")
    m.set_compositor("auto")
    assert project.state["desktop"]["compositor"]["id"] == "mutter"
    text = (r / "etc/xdg/autostart/picom.desktop").read_text()
    assert "NotShowIn=GNOME;" in text and "X-Cinnamon" in text and "OnlyShowIn" not in text
    project.state["desktop"]["id"] = "xfce"
    m.set_compositor("xfwm4")
    assert 'name="use_compositing" type="bool" value="true"' in \
        (r / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml").read_text()
    project.state["desktop"]["id"] = "kde"
    m.set_compositor("builtin")
    assert "Enabled=true" in (r / "etc/xdg/kwinrc").read_text()


def test_profiles():
    ids = [p["id"] for p in profiles.catalog()]
    assert ids == ["education", "server", "professional", "home", "other"]
    keys = [k for k, _l, _s in profiles.recommendations("education")]
    assert keys[:4] == ["desktop", "session", "compositor", "look"] and "apps" in keys
    edu = dict((k, s) for k, _l, s in profiles.recommendations("education"))
    assert edu["desktop"] == {"action": "desktop", "id": "xfce", "dm": "lightdm", "edition": "full"}
    assert edu["compositor"]["id"] == "xfwm4"
    home = dict((k, s) for k, _l, s in profiles.recommendations("home"))
    assert home["compositor"]["id"] == "muffin"  # Cinnamon's own, never picom
    server = [k for k, _l, _s in profiles.recommendations("server")]
    assert "desktop" not in server and "apps" in server
    assert profiles.recommendations("other") == []


def test_profiles_apply_selected_steps(project, monkeypatch):
    from eduka_customizer.core import recipe
    seen = []
    monkeypatch.setattr(recipe, "run_step", lambda proj, step, base, build=True: seen.append(step["action"]))
    done = profiles.apply(project, "professional", keys={"desktop", "apps"})
    assert done == ["desktop", "apps"] and seen == ["desktop", "apt-install"]
    assert project.state["purpose"] == "professional"


def _info(**kw):
    base = dict(id="debian", id_like=[], name="Debian GNU/Linux", pretty_name="Debian", debian_version="13.1",
                debian_codename="trixie", suite="stable", arch="amd64")
    base.update(kw)
    return distro.DistroInfo(**base)


def test_lmde_and_derivatives_accepted():
    assert distro.validate(_info(id="linuxmint", id_like=["debian"], name="LMDE", pretty_name="LMDE 7 (Gigi)"))
    assert distro.validate(_info(id="kali", id_like=["debian"], name="Kali GNU/Linux"))
    with pytest.raises(distro.UnsupportedDistro):
        distro.validate(_info(id="linuxmint", id_like=["ubuntu", "debian"], name="Linux Mint"))
    with pytest.raises(distro.UnsupportedDistro):
        distro.validate(_info(id="fedora", id_like=[], name="Fedora"))


def test_live_defaults(project):
    from eduka_customizer.core.users import SUGGESTED_USER, Users
    assert SUGGESTED_USER == ("live", "Live")
    assert project.state["identity"]["live_user"] == "live" and project.state["identity"]["live_fullname"] == "Live"
    assert Users(project).live()["username"] == "user"  # nothing configured: Debian's default


def test_menu_icons_exist_for_every_page():
    from eduka_customizer.core.config import data_file
    root = Path(__file__).resolve().parents[1]
    src = (root / "eduka_customizer/gui/main_window.py").read_text()
    import re
    keys = re.findall(r'"(\w+Page)": "(\w+)"', src)
    assert len(keys) == 24
    for _page, key in keys:
        assert data_file("icons", "menu", key + ".svg").exists(), key
    assert "GPL-3.0" in (root / "data/icons/menu/README.md").read_text()
    for size in (16, 32, 48, 256):
        assert (root / "icons/hicolor/{0}x{0}/apps/eduka-customizer.png".format(size)).exists()


def test_archive_links():
    from eduka_customizer.core.fsutil import link_stays_inside
    assert link_stays_inside("Tela/48x48/apps/a.svg", "../../scalable/apps/a.svg")
    assert link_stays_inside("ePapirus/64x64", "../Papirus/64x64")
    assert not link_stays_inside("theme/x", "../../etc/passwd")
    assert not link_stays_inside("x", "/etc/passwd")
    assert not link_stays_inside("x", "..")


def test_new_projects_are_not_edukasaun(blank_project, tmp_path):
    """0.15: nothing about Edukasaun OS is preset; names fall back to the image's os-release."""
    p = blank_project
    ident = p.state["identity"]
    assert ident["name"] == "" and ident["id"] == "" and ident["volume_label"] == "" and ident["hostname"] == ""
    from eduka_customizer.core import distro, legacy
    p.state["distro"] = distro.detect(p.rootfs).to_dict()
    assert p.display_name() == "Debian GNU/Linux" and p.os_id() == "debian"
    assert p.volume_label() == "DEBIAN_GNU_LINUX"
    from eduka_customizer.core.isobuild import BuildOptions
    o = BuildOptions.from_project(p)
    assert o.title == "Debian GNU/Linux" and o.volume_label == "DEBIAN_GNU_LINUX"
    from eduka_customizer.core.branding import Branding
    with pytest.raises(ValueError, match="name"):
        Branding(p).apply_identity(dict(ident))
    old = p.rootfs / "etc/live/config.conf.d/50-edukasaun.conf"
    old.parent.mkdir(parents=True)
    old.write_text('LIVE_USERNAME="live"\n')
    assert legacy.migrate(p.rootfs) == 1
    assert (p.rootfs / "etc/live/config.conf.d/50-eduka-customizer.conf").exists() and not old.exists()
