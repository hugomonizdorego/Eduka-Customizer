"""0.16: system sounds, welcome screen, identity from the ISO, editions in each
desktop's own words, Flathub by category, kernel repositories, themes per
desktop, Calamares slides and checks, GRUB themes and boot loaders."""

import json
import struct
from pathlib import Path

import pytest

from eduka_customizer.core import gsettings, sounds


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
    monkeypatch.setattr(apt.Packages, "available", lambda self, names: set(names))
    monkeypatch.setattr(apt.Packages, "update", lambda self, *a, **k: None)
    return calls


def wav(path, seconds=0.1):
    rate, n = 8000, int(8000 * seconds)
    data = b"\x00\x00" * n
    path.write_bytes(b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVEfmt " +
                     struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16) + b"data" +
                     struct.pack("<I", len(data)) + data)
    return path


def schema(rootfs, sid, keys):
    d = rootfs / gsettings.SCHEMAS
    d.mkdir(parents=True, exist_ok=True)
    body = "".join('<key name="{}" type="s"><default>\'\'</default></key>'.format(k) for k in keys)
    (d / (sid + ".gschema.xml")).write_text('<schemalist><schema id="{}" path="/x/">{}</schema></schemalist>'
                                            .format(sid, body))


# Sounds ---------------------------------------------------------------------------------------

def test_match_and_sniff(tmp_path):
    assert sounds.match_event("login.ogg") == "desktop-login"
    assert sounds.match_event("Boot.wav") == "system-bootup"
    assert sounds.match_event("system-shutdown.oga") == "system-shutdown"
    assert sounds.match_event("my_error_sound.ogg") == "dialog-error"
    assert sounds.match_event("holiday.ogg") is None
    assert sounds.sniff(wav(tmp_path / "a.wav")) == "wav"
    (tmp_path / "b.ogg").write_bytes(b"OggS" + b"\0" * 40)
    assert sounds.sniff(tmp_path / "b.ogg") == "ogg"
    (tmp_path / "c.txt").write_text("hello")
    assert sounds.sniff(tmp_path / "c.txt") == ""


def test_gsettings_override_only_known_keys(project, nochroot):
    r = project.rootfs
    schema(r, "org.gnome.desktop.sound", ["theme-name", "event-sounds"])
    written = gsettings.write_override(r, "99_test", {"org.gnome.desktop.sound": {"theme-name": "x", "nope": 1},
                                                      "org.mate.sound": {"theme-name": "x"}})
    assert written == {"org.gnome.desktop.sound": ["theme-name"]}
    text = (r / gsettings.SCHEMAS / "99_test.gschema.override").read_text()
    assert "theme-name='x'" in text and "nope" not in text and "mate" not in text
    gsettings.write_override(r, "99_test", {})
    assert not (r / gsettings.SCHEMAS / "99_test.gschema.override").exists()


def test_sounds_theme_and_services(project, nochroot, tmp_path):
    r = project.rootfs
    schema(r, "org.gnome.desktop.sound", ["theme-name", "event-sounds"])
    schema(r, "org.cinnamon.sounds", ["login-enabled", "login-file"])
    folder = tmp_path / "pack"
    folder.mkdir()
    for name in ("boot.wav", "login.wav", "shutdown.wav", "error.wav", "readme.wav"):
        wav(folder / name)
    s = sounds.Sounds(project)
    found = s.add_folder(folder)
    assert set(found) == {"system-bootup", "desktop-login", "system-shutdown", "dialog-error"}
    s.apply()
    theme = project.os_id()
    base = r / "usr/share/sounds" / theme
    assert "Inherits=freedesktop" in (base / "index.theme").read_text()
    assert (base / "stereo/dialog-error.wav").exists()
    unit = (r / sounds.UNIT).read_text()
    assert "play-sound system-bootup" in unit and "ExecStop=/usr/lib/eduka-customizer-sounds/play-sound " \
                                                  "system-shutdown" in unit
    assert (r / "etc/systemd/system/multi-user.target.wants/eduka-system-sounds.service").is_symlink()
    assert "desktop-login" in (r / sounds.AUTOSTART).read_text()
    assert (r / sounds.LIB / "theme").read_text().strip() == theme
    over = (r / gsettings.SCHEMAS / (sounds.OVERRIDE + ".gschema.override")).read_text()
    assert "theme-name='{}'".format(theme) in over and "login-file='/usr/share/sounds/" in over
    assert "gtk-sound-theme-name={}".format(theme) in (r / "etc/gtk-3.0/settings.ini").read_text()
    assert "Theme={}".format(theme) in (r / "etc/xdg/plasmarc").read_text()
    assert any(c[:1] == ["install"] and "alsa-utils" in c for c in nochroot)
    st = s.state()
    assert st["boot"] and st["login"] and len(st["files"]) == 4
    s.remove()
    assert not (r / sounds.UNIT).exists() and not base.exists() and not (r / sounds.AUTOSTART).exists()


def test_sounds_reject_non_audio(project, tmp_path):
    bad = tmp_path / "x.ogg"
    bad.write_text("not a sound")
    with pytest.raises(ValueError):
        sounds.Sounds(project).set_sound("dialog-error", bad)
    with pytest.raises(KeyError):
        sounds.Sounds(project).set_sound("nonsense", wav(tmp_path / "a.wav"))


# Welcome screen ------------------------------------------------------------------------------

def test_welcome_markup_and_validation(project):
    from eduka_customizer.core import welcome
    assert welcome.to_markup("Hi **you** & *me* [site](https://e.org) <x>") == \
        'Hi <b>you</b> &amp; <i>me</i> <a href="https://e.org">site</a> &lt;x&gt;'
    d = welcome.default_design(project)
    assert len(d["pages"]) == 4 and welcome.validate(d) == []
    d["pages"][1]["buttons"] = [{"label": "Web", "action": "url", "target": "example.org"}]
    d["colors"]["accent"] = "green"
    problems = welcome.validate(d)
    assert any("web address" in p for p in problems) and any("Color" in p for p in problems)
    for p in d["pages"]:
        p["enabled"] = False
    assert any("at least one page" in p for p in welcome.validate(d))


def test_welcome_apply_and_remove(project, nochroot, tmp_path):
    from eduka_customizer.core import welcome
    from tests.test_v012 import png
    r = project.rootfs
    d = welcome.default_design(project)
    d["logo"] = str(png(tmp_path / "logo.png"))
    d["pages"][2]["image"] = str(png(tmp_path / "pic.png", "#336699"))
    d["pages"][3]["enabled"] = False
    welcome.Welcome(project).apply(d)
    data = json.loads((r / welcome.DATA / "welcome.json").read_text())
    assert data["logo"] == "logo.png" and (r / welcome.DATA / "logo.png").exists()
    assert data["pages"][2]["image"] == "page3.png" and (r / welcome.DATA / "page3.png").exists()
    assert data["pages"][0]["title_markup"].startswith("Welcome to")
    assert (r / welcome.APP).stat().st_mode & 0o111
    assert "--autostart" in (r / welcome.AUTOSTART).read_text()
    assert any(c[:1] == ["install"] and "python3-gi" in c for c in nochroot)
    assert project.state["welcome"]["pages"][3]["enabled"] is False
    d["show"] = "menu"
    welcome.Welcome(project).apply(d, install_packages=False)
    assert not (r / welcome.AUTOSTART).exists() and (r / welcome.DESKTOP).exists()
    welcome.Welcome(project).remove()
    assert not (r / welcome.APP).exists() and not (r / welcome.DATA).exists()


def test_welcome_program_compiles():
    import py_compile
    from eduka_customizer.core import welcome
    py_compile.compile(str(welcome.app_source()), doraise=True)


# Identity from the ISO -------------------------------------------------------------------------

def test_identity_and_artwork_from_image(blank_project, tmp_path):
    from eduka_customizer.core import imageinfo
    from tests.test_v012 import png
    p = blank_project
    r = p.rootfs
    rel = r / "usr/lib/os-release"
    rel.write_text(rel.read_text() + 'HOME_URL="https://www.debian.org/"\nBUG_REPORT_URL="https://bugs.debian.org/"\n')
    (r / "etc/hostname").write_text("debian\n")
    p.state.setdefault("source", {})["volume_id"] = "d-live 13.1.0 xf amd64"
    (r / "etc/live/config.conf.d").mkdir(parents=True)
    (r / "etc/live/config.conf.d/10-user.conf").write_text('LIVE_USERNAME="user"\n')
    ident = imageinfo.identity(p)
    assert ident["name"] == "Debian GNU/Linux" and ident["id"] == "debian" and ident["version"] == "13"
    assert ident["codename"] == "trixie" and ident["home_url"] == "https://www.debian.org/"
    assert ident["hostname"] == "debian" and ident["volume_label"] == "d-live 13.1.0 xf amd64"
    assert ident["live_user"] == "user"
    images = r / "usr/share/images/desktop-base"
    images.mkdir(parents=True)
    png(images / "real-wall.png", "#123456")
    (images / "default").symlink_to("real-wall.png")
    (r / "usr/share/pixmaps").mkdir(parents=True)
    png(r / "usr/share/pixmaps/debian-logo.png")
    art = imageinfo.copy_artwork(p)
    assert Path(art["logo"]).parent == p.path / "from-iso" and Path(art["wallpaper"]).is_file()
    assert Path(art["wallpaper"]).name == "wallpaper.png"


# Editions in each desktop's own words ----------------------------------------------------------

def test_edition_names_per_desktop(project):
    from eduka_customizer.core import desktop as dsk
    assert dsk.edition_name("kde", "full_apps")[0] == "KDE Plasma with KDE Gear"
    assert dsk.edition_name("xfce", "full_apps")[0] == "Xfce with Goodies"
    assert dsk.edition_name("gnome", "compact")[0] == "GNOME Core"
    assert dsk.edition_name("i3", "mini")[0] == "i3 only"
    for d in dsk.catalog()["desktops"]:
        assert set(d["edition_names"]) == set(dsk.EDITIONS), d["id"]
    lists = project.rootfs / "var/lib/apt/lists"
    lists.mkdir(parents=True, exist_ok=True)
    (lists / "deb.debian.org_debian_dists_trixie_main_binary-amd64_Packages").write_text(
        "Package: kde-standard\nVersion: 5:150\nDescription: KDE Plasma Desktop and standard set of applications\n\n"
        "Package: other\nVersion: 1\nDescription: x\n")
    assert dsk.package_descriptions(project.rootfs, ["kde-standard", "nope"]) == {
        "kde-standard": "KDE Plasma Desktop and standard set of applications"}


# Flathub by category ---------------------------------------------------------------------------

def test_flathub_api_by_category(monkeypatch):
    import io
    from eduka_customizer.core import flathub
    pages = {"Office": [{"app_id": "org.libreoffice.LibreOffice", "name": "LibreOffice", "summary": "Office",
                         "main_categories": "Office"}],
             "AudioVideo": [{"app_id": "org.videolan.VLC", "name": "VLC", "summary": "Media player",
                             "main_categories": ["AudioVideo"]},
                            {"id": "org_libreoffice_LibreOffice", "name": "dup", "summary": ""}]}
    seen = []

    def fake(req, timeout=0):
        url = req.full_url
        seen.append(url)
        cat = url.split("/category/")[1].split("?")[0]
        return io.BytesIO(json.dumps({"hits": pages.get(cat, []), "totalPages": 1}).encode())
    monkeypatch.setattr(flathub.urllib.request, "urlopen", fake)
    apps = flathub.from_api()
    assert apps["org.videolan.VLC"]["category"] == "AudioVideo"
    assert apps["org.libreoffice.LibreOffice"]["category"] == "Office"
    assert len(seen) == len(flathub.CATEGORIES) and "/collection/category/Office?page=1" in seen[0]
    rows = flathub.Catalog.by_category(apps, "AudioVideo")
    assert rows == [("org.videolan.VLC", "VLC", "Media player", "AudioVideo")]
    assert flathub.Catalog.by_category(apps, None, "media")[0][0] == "org.videolan.VLC"
    assert flathub.Catalog.counts(apps)["Office"] == 1


def test_flathub_appstream(tmp_path):
    import gzip
    from eduka_customizer.core import flathub
    xml = """<?xml version="1.0"?>
<components origin="flathub">
  <component type="desktop-application"><id>org.gimp.GIMP</id><name>GNU Image Manipulation Program</name>
    <name xml:lang="id">GIMP id</name><summary>Create images and edit photographs</summary>
    <categories><category>Graphics</category><category>2DGraphics</category></categories></component>
  <component type="desktop"><id>org.kde.gcompris.desktop</id><name>GCompris</name><summary>Kids</summary>
    <categories><category>Education</category><category>Game</category></categories></component>
  <component type="runtime"><id>org.freedesktop.Platform</id><name>Runtime</name></component>
</components>"""
    f = tmp_path / "flathub/x86_64/active/appstream.xml.gz"
    f.parent.mkdir(parents=True)
    with gzip.open(f, "wb") as fh:
        fh.write(xml.encode())
    apps = flathub.from_appstream(f)
    assert set(apps) == {"org.gimp.GIMP", "org.kde.gcompris"}
    assert apps["org.gimp.GIMP"]["name"] == "GNU Image Manipulation Program"
    assert apps["org.gimp.GIMP"]["category"] == "Graphics"
    assert apps["org.kde.gcompris"]["category"] == "Education"
    root = tmp_path / "root"
    (root / "var/lib/flatpak/appstream").mkdir(parents=True)
    import shutil
    shutil.copytree(tmp_path / "flathub", root / "var/lib/flatpak/appstream/flathub")
    assert flathub.appstream_file(root).name == "appstream.xml.gz"


# Replace apps for everyone ---------------------------------------------------------------------

def test_replace_terminal_for_everyone(project, nochroot):
    from eduka_customizer.core import replace
    from tests.test_v015 import _pkg
    r = project.rootfs
    _pkg(r, "tilix", ["/usr/bin/tilix", "/usr/share/applications/com.gexperts.Tilix.desktop"],
         {"com.gexperts.Tilix.desktop": "[Desktop Entry]\nType=Application\nName=Tilix\nExec=tilix\n"})
    helpers = r / "usr/share/xfce4/helpers"
    helpers.mkdir(parents=True)
    (helpers / "tilix.desktop").write_text("[Desktop Entry]\nX-XFCE-Category=TerminalEmulator\n"
                                           "X-XFCE-Binaries=tilix;\n")
    (r / "etc/xdg/xfce4").mkdir(parents=True)
    (r / "etc/xdg/xfce4/helpers.rc").write_text("WebBrowser=firefox\nTerminalEmulator=xfce4-terminal\n")
    skel = r / "etc/skel/.config"
    skel.mkdir(parents=True)
    (skel / "mimeapps.list").write_text("[Default Applications]\n")
    schema(r, "org.gnome.desktop.default-applications.terminal", ["exec"])
    replace.Replacer(project).replace("terminal", "tilix")
    assert (r / "etc/xdg/xfce4/helpers.rc").read_text() == "WebBrowser=firefox\nTerminalEmulator=tilix\n"
    assert "TerminalApplication=tilix" in (r / "etc/xdg/kdeglobals").read_text()
    assert "TERM=tilix" in (r / "etc/xdg/lxqt/session.conf").read_text()
    over = (r / gsettings.SCHEMAS / "93_eduka-default-apps.gschema.override").read_text()
    assert "exec='tilix'" in over
    replace.Replacer(project).replace("browser", "tilix")  # any package works the same way
    assert "BrowserApplication=com.gexperts.Tilix.desktop" in (r / "etc/xdg/kdeglobals").read_text()
    assert "x-scheme-handler/http=com.gexperts.Tilix.desktop;" in (skel / "mimeapps.list").read_text()


# Kernel repositories from the terminal ---------------------------------------------------------

def test_kernel_console_temporary_repositories(project, monkeypatch):
    from eduka_customizer.core import chroot
    from eduka_customizer.core.kernel import Kernels
    r = project.rootfs
    (r / "etc/apt/keyrings").mkdir(parents=True, exist_ok=True)

    def fake_output(self, cmd, **k):
        text = cmd[-1]
        if "xanmod" in text:
            (r / "etc/apt/keyrings/xanmod.gpg").write_bytes(b"key")
            (r / "etc/apt/sources.list.d/xanmod.list").write_text(
                "deb [signed-by=/etc/apt/keyrings/xanmod.gpg] http://deb.xanmod.org releases main\n")
        if "liquorix" in text:
            (r / "etc/apt/sources.list").write_text("deb http://liquorix.net/debian trixie main\n")
        return "ok\n"
    monkeypatch.setattr(chroot.Chroot, "output", fake_output)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    k = Kernels(project)
    assert k.console("add xanmod") == "ok\n"
    k.console("add liquorix")
    temp = k.temp_files()
    assert "etc/apt/sources.list.d/xanmod.list" in temp and "etc/apt/keyrings/xanmod.gpg" in temp
    assert "etc/apt/sources.list.d/kernel-console-1.list" in temp
    assert "liquorix" not in (r / "etc/apt/sources.list").read_text()
    assert Kernels.list_prefix("https://user@liquorix.net/debian/") == "liquorix.net_debian_"
    lists = r / "var/lib/apt/lists"
    lists.mkdir(parents=True, exist_ok=True)
    (lists / "deb.xanmod.org_dists_releases_main_binary-amd64_Packages").write_text(
        "Package: linux-image-6.15.0-x64v3-xanmod1\nVersion: 6.15.0-x64v3-xanmod1-0~1\n\n"
        "Package: linux-xanmod-x64v3\nVersion: 6.15.0-1\n")
    (lists / "liquorix.net_debian_dists_trixie_main_binary-amd64_Packages").write_text(
        "Package: linux-image-liquorix-amd64\nVersion: 6.14-1\n")
    repos = {x["file"]: x for x in k.temp_repos()}
    assert "linux-xanmod-x64v3" in repos["etc/apt/sources.list.d/xanmod.list"]["kernels"]
    st = r / "var/lib/dpkg/status"
    st.write_text(st.read_text() + "\nPackage: linux-xanmod-x64v3\nStatus: install ok installed\nVersion: 6.15.0-1\n")
    kept, removed = k.finalize_temp_repos()
    assert set(kept) == {"etc/apt/sources.list.d/xanmod.list", "etc/apt/keyrings/xanmod.gpg"}
    assert removed == ["etc/apt/sources.list.d/kernel-console-1.list"]
    assert not (lists / "liquorix.net_debian_dists_trixie_main_binary-amd64_Packages").exists()
    assert (r / "etc/apt/sources.list.d/xanmod.list").exists() and k.temp_files() == []


# Look & Feel per desktop -----------------------------------------------------------------------

def test_theme_packs_fit_the_desktop():
    from eduka_customizer.core import desktop as dsk
    from eduka_customizer.core import themes
    packs = {p["package"]: p for p in themes.packs_catalog()}
    kde, xfce, gnome, sway = (dsk.desktop(i) for i in ("kde", "xfce", "gnome", "sway"))
    fits = lambda pkg, de: themes.pack_fits(packs[pkg], de)  # noqa: E731
    assert fits("papirus-icon-theme", kde) and fits("papirus-icon-theme", sway)
    assert fits("qt-style-kvantum", kde) and not fits("qt-style-kvantum", xfce)
    assert fits("greybird-gtk-theme", xfce) and not fits("greybird-gtk-theme", kde)
    assert fits("breeze-gtk-theme", kde) and not fits("breeze-gtk-theme", gnome)
    assert fits("xfwm4-themes", xfce) and not fits("xfwm4-themes", gnome)
    assert fits("picom", xfce) and not fits("picom", gnome) and not fits("picom", sway)
    assert all(themes.pack_fits(p, None) for p in packs.values())
    opts = themes.look_options(kde)
    assert opts["plasma"] and opts["kvantum"] and opts["gtk_apps_only"] and not opts["xfwm4"]
    assert themes.look_options(xfce)["xfwm4"] and not themes.look_options(xfce)["plasma"]


def test_window_themes(project, nochroot):
    from eduka_customizer.core.themes import Themes
    r = project.rootfs
    for name, sub in (("Greybird", "xfwm4"), ("Numix", "openbox-3"), ("Arc", "cinnamon")):
        (r / "usr/share/themes" / name / sub).mkdir(parents=True)
    xf = r / "etc/xdg/xfce4/xfconf/xfce-perchannel-xml"
    xf.mkdir(parents=True)
    (xf / "xfwm4.xml").write_text('<channel><property name="theme" type="string" value="Default"/></channel>')
    (r / "etc/xdg/openbox").mkdir(parents=True)
    (r / "etc/xdg/openbox/rc.xml").write_text("<openbox_config><theme>\n  <name>Clearlooks</name></theme>")
    schema(r, "org.cinnamon.theme", ["name"])
    th = Themes(project)
    assert th.xfwm4_themes() == ["Greybird"] and th.openbox_themes() == ["Numix"] and th.cinnamon_themes() == ["Arc"]
    th.apply_extra(xfwm4="Greybird", openbox="Numix", cinnamon="Arc", plasma="org.kde.breezedark.desktop")
    assert 'value="Greybird"' in (xf / "xfwm4.xml").read_text()
    assert "<name>Numix</name>" in (r / "etc/xdg/openbox/rc.xml").read_text()
    assert "name='Arc'" in (r / gsettings.SCHEMAS / "91_eduka-wm-theme.gschema.override").read_text()
    assert "LookAndFeelPackage=org.kde.breezedark.desktop" in (r / "etc/xdg/kdeglobals").read_text()
    with pytest.raises(ValueError):
        th.apply_extra(xfwm4="../../etc")


# Calamares: careful checks, text slides ----------------------------------------------------------

DEBIAN_SETTINGS = """---
modules-search: [ local, /usr/lib/calamares/modules ]

instances:
- id:       before_bootloader
  module:   contextualprocess
  config:   before_bootloader_context.conf
- id:       logs
  module:   shellprocess
  config:   shellprocess_logs.conf

sequence:
- show:
  - welcome
  - locale
  - partition
  - users
  - summary
- exec:
  - partition
  - mount
  - unpackfs
  - users
  - displaymanager
  - contextualprocess@before_bootloader
  - bootloader
  - packages
  - shellprocess@logs
  - umount
- show:
  - finished

branding: debian
prompt-install: true
"""


@pytest.fixture
def cal(project):
    r = project.rootfs
    mods = r / "usr/lib/x86_64-linux-gnu/calamares/modules"
    for m in ("welcome", "locale", "partition", "users", "summary", "mount", "unpackfs", "displaymanager",
              "contextualprocess", "bootloader", "packages", "shellprocess", "umount", "finished"):
        (mods / m).mkdir(parents=True)
        (mods / m / "module.desc").write_text("---\ntype: job\nname: {}\n".format(m))
    etc = r / "etc/calamares"
    (etc / "modules").mkdir(parents=True)
    (etc / "settings.conf").write_text(DEBIAN_SETTINGS)
    b = etc / "branding/debian"
    b.mkdir(parents=True)
    (b / "branding.desc").write_text("---\ncomponentName: debian\nstrings:\n    productName: Debian\n"
                                     "    bootloaderEntryName: Debian\nimages:\n    productLogo: \"logo.png\"\n"
                                     "slideshowAPI: 2\nslideshow: \"show.qml\"\nstyle:\n    SidebarBackground: \"#2c3133\"\n")
    (b / "logo.png").write_bytes(b"png")
    (b / "show.qml").write_text('import QtQuick 2.0;\nimport calamares.slideshow 1.0;\nPresentation { Slide { } }\n')
    (etc / "modules/unpackfs.conf").write_text("---\nunpack:\n    - source: \"/run/live/medium/live/filesystem.squashfs\"\n"
                                               "      sourcefs: \"squashfs\"\n      destination: \"\"\n")
    (etc / "modules/before_bootloader_context.conf").write_text("---\ndontChroot: false\n")
    (etc / "modules/shellprocess_logs.conf").write_text("---\nscript:\n    - command: \"/usr/sbin/calamares-logs-helper @@ROOT@@\"\n")
    (etc / "modules/bootloader.conf").write_text("---\nefiBootLoader: \"grub\"\nefiBootloaderId: \"debian\"\n")
    (etc / "modules/packages.conf").write_text("---\nbackend: apt\noperations:\n  - remove:\n      - live-boot\n"
                                               "  - try_remove:\n      - calamares\n")
    (etc / "modules/displaymanager.conf").write_text("---\ndisplaymanagers:\n  - lightdm\n  - sddm\n")
    (etc / "modules/partition.conf").write_text("---\ndefaultFileSystemType: \"ext4\"\n"
                                                "availableFileSystemTypes: [\"ext4\", \"btrfs\"]\n")
    for f in ("usr/bin/calamares", "usr/sbin/grub-install", "usr/sbin/grub-mkconfig", "usr/bin/efibootmgr",
              "usr/sbin/lightdm", "usr/sbin/mkfs.ext4", "usr/sbin/mkfs.btrfs", "usr/sbin/calamares-logs-helper"):
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        (r / f).write_text("")
    st = r / "var/lib/dpkg/status"
    st.write_text(st.read_text() + "\nPackage: calamares\nStatus: install ok installed\nVersion: 3.3.14-1\n")
    return project


def test_calamares_check_clean(cal):
    from eduka_customizer.core import calamares_check as cc
    res = cc.check(cal)
    fails = [x for x in res if x[0] == "fail"]
    assert not fails, fails
    assert any("branding 'debian' is complete" in x[2] for x in res)
    assert cc.loaders_for((3, 2)) == ["grub", "sb-shim", "systemd-boot"]
    assert "refind" in cc.loaders_for((3, 3))


def test_calamares_check_finds_problems(cal):
    from eduka_customizer.core import calamares_check as cc
    r = cal.rootfs
    etc = r / "etc/calamares"
    desc = etc / "branding/debian/branding.desc"
    desc.write_text(desc.read_text().replace("componentName: debian", "componentName: mylinux")
                    .replace("logo.png", "missing.png"))
    (etc / "branding/debian/show.qml").write_text("import QtQuick 2.0;\nPresentation { Slide { }\n")
    (etc / "settings.conf").write_text(DEBIAN_SETTINGS.replace("  - umount", "  - umount\n  - nosuchmodule"))
    (etc / "modules/unpackfs.conf").write_text("---\nunpack:\n    - source: \"/cdrom/casper/filesystem.squashfs\"\n")
    (etc / "modules/bootloader.conf").write_text("---\nefiBootLoader: \"refind\"\n")
    (etc / "modules/packages.conf").write_text("---\nbackend: apt\noperations:\n  - remove:\n      - not-there\n")
    (etc / "modules/displaymanager.conf").write_text("---\ndisplaymanagers:\n  - gdm\n")
    (etc / "modules/partition.conf").write_text("---\ndefaultFileSystemType: \"xfs\"\n")
    (r / "usr/sbin/calamares-logs-helper").unlink()
    text = " | ".join(x[2] for x in cc.check(cal) if x[0] == "fail")
    for needle in ("componentName 'mylinux'", "missing.png", "'{' and '}'", "nosuchmodule",
                   "not a live-boot path", "refind needs /usr/sbin/refind-install", "not-there",
                   "displaymanagers gdm", "mkfs.xfs", "calamares-logs-helper"):
        assert needle in text, needle
    assert cc.summary(cc.check(cal))[0] >= 10


def test_calamares_text_slides(cal, tmp_path):
    from eduka_customizer.core.calamares import Calamares
    from tests.test_v012 import png
    c = Calamares(cal)
    c.set_branding(slides=[{"title": 'Say "hello"', "text": "Line one\n**Bold** and [web](https://e.org)",
                            "background": "#112233", "color": "#ffffff"},
                           str(png(tmp_path / "s.png"))], slide_seconds=5)
    qml = (cal.rootfs / "etc/calamares/branding/debian/show.qml").read_text()
    assert 'text: "Say \\"hello\\""' in qml and "<b>Bold</b>" in qml and "<br>" in qml
    assert 'source: "slide-02.png"' in qml and "interval: 5000" in qml
    assert (cal.rootfs / "etc/calamares/branding/debian/slide-02.png").exists()
    data = c.slide_data()
    assert data[0]["title"] == 'Say "hello"' and data[1]["image"].endswith("slide-02.png")
    from eduka_customizer.core import calamares_check as cc
    assert not [x for x in cc.check(cal) if x[0] == "fail"]
    # Applying the same slides again (their images are the current files) keeps them.
    c.set_branding(slides=data, slide_seconds=5)
    assert (cal.rootfs / "etc/calamares/branding/debian/slide-02.png").exists()


# GRUB themes, menu designer, boot loaders --------------------------------------------------------

DEBIAN_GRUB = """source /boot/grub/config.cfg

# Live boot
menuentry "Live system (amd64)" --hotkey=l {
\tlinux\t/live/vmlinuz boot=live components quiet splash findiso=${iso_path}
\tinitrd\t/live/initrd.img
}
menuentry "Live system (amd64) (fail-safe mode)" {
\tlinux\t/live/vmlinuz boot=live components memtest noapic noapm nodma nomce nosmp nosplash vga=788
\tinitrd\t/live/initrd.img
}

submenu 'Utilities...' --hotkey=u {
\tsource /boot/grub/theme.cfg
\tif [ $grub_platform = "efi" ]; then
\t\tmenuentry "UEFI Firmware Settings" {
\t\t\tfwsetup
\t\t}
\tfi
}
"""


def _grub(project):
    cfg = project.isodir / "boot/grub/grub.cfg"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    cfg.write_text(DEBIAN_GRUB)
    (project.isodir / "boot/grub/config.cfg").write_text("set default=0\n")
    return cfg


def _theme(base, name="Vimix", **extra):
    d = base / name
    d.mkdir(parents=True)
    from tests.test_v012 import png
    png(d / "background.png")
    png(d / "select_c.png")
    (d / "theme.txt").write_text('desktop-image: "background.png"\ntitle-text: ""\n+ boot_menu {\n'
                                 '  item_font = "Terminus Regular 16"\n  selected_item_pixmap_style = "select_*.png"\n}\n')
    (d / "terminus-16.pf2").write_bytes(b"PFF2")
    for k, v in extra.items():
        (d / k).write_bytes(v)
    return d


def test_grub_theme_check_and_use(project, tmp_path):
    from eduka_customizer.core import grubtheme
    cfg = _grub(project)
    good = _theme(tmp_path / "good")
    problems, warnings, info = grubtheme.check(good)
    assert problems == [] and info["fonts"] == ["terminus-16.pf2"]
    g = grubtheme.GrubThemes(project)
    name, _w, _i = g.add(good, installed_system=True)
    assert name == "Vimix" and g.installed() == ["Vimix"]
    g.use(name, installed_system=True)
    text = cfg.read_text()
    assert text.startswith("source /boot/grub/config.cfg") and text.count(grubtheme.BEGIN) == 1
    assert "set theme=/boot/grub/themes/Vimix/theme.txt" in text and "loadfont /boot/grub/themes/Vimix/terminus-16.pf2" in text
    assert 'GRUB_THEME="/boot/grub/themes/Vimix/theme.txt"' in (project.rootfs / grubtheme.GRUB_D).read_text()
    assert (project.rootfs / "boot/grub/themes/Vimix/theme.txt").exists()
    g.reapply()
    assert cfg.read_text().count(grubtheme.BEGIN) == 1
    g.remove()
    assert grubtheme.BEGIN not in cfg.read_text() and "menuentry" in cfg.read_text()


def test_grub_theme_rejected(project, tmp_path):
    from eduka_customizer.core import grubtheme
    _grub(project)
    bad = _theme(tmp_path / "bad", "Svg")
    (bad / "theme.txt").write_text('desktop-image: "background.svg"\n+ boot_menu { item_font = "Noto 12" '
                                   'selected_item_pixmap_style = "sel_*.png" }\n')
    (bad / "terminus-16.pf2").unlink()
    (bad / "Noto.ttf").write_bytes(b"x")
    with pytest.raises(grubtheme.ThemeRejected) as e:
        grubtheme.GrubThemes(project).add(bad)
    msg = str(e.value)
    assert "PNG, JPEG and TGA" in msg and "sel_*.png" in msg and "grub-mkfont" in msg
    (tmp_path / "notheme").mkdir()
    with pytest.raises(grubtheme.ThemeRejected):
        grubtheme.GrubThemes(project).add(tmp_path / "notheme")
    assert grubtheme.GrubThemes(project).installed() == []


def test_grub_menu_designer(project):
    from eduka_customizer.core import grubmenu
    cfg = _grub(project)
    gm = grubmenu.GrubMenu(project)
    d = gm.design()
    assert [e["title"] for e in d["entries"]] == ["Live system (amd64)", "Live system (amd64) (fail-safe mode)",
                                                  "Utilities..."]
    live, failsafe, utils = d["entries"]
    live["title"] = 'My Linux "Live"'
    safe = grubmenu.preset_entry(cfg.read_text(), "safe")
    assert "nomodeset" in safe["body"] and safe["title"] == "Live system (safe graphics)"
    verbose = grubmenu.preset_entry(cfg.read_text(), "verbose")
    assert "quiet" not in verbose["body"] and "splash" not in verbose["body"].split("findiso")[0].split()
    off = grubmenu.preset_entry(cfg.read_text(), "poweroff")
    text = gm.save([live, safe, utils, off], default="Live system (safe graphics)", timeout=7,
                   normal="white/black", highlight="black/light-gray")
    titles = [e["title"] for e in grubmenu.entries(text)]
    assert titles == ["My Linux 'Live'", "Live system (safe graphics)", "Utilities...", "Power off"]
    assert 'set default="Live system (safe graphics)"' in text and "set timeout=7" in text
    assert text.index("set timeout=7") > text.index("source /boot/grub/config.cfg")
    assert "fail-safe" not in text and "UEFI Firmware Settings" in text
    assert "boot/grub/grub.cfg" in project.state["boot"]["overrides"]
    with pytest.raises(ValueError):
        gm.save([live], default="nope")
    with pytest.raises(ValueError):
        gm.save([live], normal="pink/black")


def test_boot_loader_choice(cal, nochroot):
    from eduka_customizer.core import bootchoice
    r = cal.rootfs
    b = bootchoice.BootChoice(cal)
    opts = {o[0]: o for o in b.options()}
    assert opts["refind"][3] and not opts["lilo"][3] and not opts["burg"][3]
    for f in ("usr/bin/bootctl", "usr/bin/kernel-install"):
        (r / f).write_text("")
    b.apply("systemd-boot", timeout=4)
    conf = (r / "etc/calamares/modules/bootloader.conf").read_text()
    assert 'efiBootLoader: "systemd-boot"' in conf or "efiBootLoader: systemd-boot" in conf
    assert b.current() == "systemd-boot"
    assert any(c[:1] == ["install"] and "systemd-boot" in c for c in nochroot)
    with pytest.raises(RuntimeError):
        b.apply("refind")  # refind-install is not in the image (nothing was really installed)
    st = r / "var/lib/dpkg/status"
    st.write_text(st.read_text().replace("Version: 3.3.14-1", "Version: 3.2.61-1"))
    assert not {o[0]: o for o in b.options()}["refind"][3]
    with pytest.raises(ValueError):
        b.apply("refind")
