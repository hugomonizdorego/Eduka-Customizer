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
