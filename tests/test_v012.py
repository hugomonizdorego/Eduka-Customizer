import os
import shutil
import subprocess
import tarfile
import zipfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eduka_customizer.core import bootedit, bootloader, language, yamlconf  # noqa: E402
from eduka_customizer.core.calamares import Calamares  # noqa: E402
from eduka_customizer.core.kernel import Kernels  # noqa: E402
from eduka_customizer.core.plymouth import Plymouth  # noqa: E402

needs_mtools = pytest.mark.skipif(not (shutil.which("mcopy") and shutil.which("mkfs.vfat")),
                                  reason="mtools/dosfstools missing")


@pytest.fixture
def nochroot(monkeypatch):
    from eduka_customizer.core import apt, chroot
    calls = {"install": [], "remove": [], "run": []}
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls["run"].append(cmd) or 0)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "install", lambda self, names, **k: calls["install"].append(list(names)))
    monkeypatch.setattr(apt.Packages, "remove", lambda self, names, **k: calls["remove"].append(list(names)))
    return calls


def png(path, color="#00a879"):
    from eduka_customizer.core import imaging
    from eduka_customizer.qt import gui
    imaging._qt()
    img = gui.QImage(64, 48, gui.QImage.Format.Format_ARGB32)
    img.fill(gui.QColor(color))
    img.save(str(path))
    return path


# YAML ---------------------------------------------------------------------------

def test_yaml_column0_comment_inside_block():
    # As in Debian's calamares branding.desc
    text = ('images:\n#    productBanner: "x.png"\n    productLogo: "debian-logo.png"\n'
            '#    productWallpaper: ""\n\nslideshow: "show.qml"\n\nstyle:\n   SidebarBackground: "#010027"\n')
    out = yamlconf.update(text, {"images": {"productLogo": "logo.png"}, "style": {"SidebarBackground": "#0f2f27"}})
    data = yamlconf.load(out)
    assert data == {"images": {"productLogo": "logo.png"}, "slideshow": "show.qml",
                    "style": {"SidebarBackground": "#0f2f27"}}
    assert "productBanner" in out and "productWallpaper" in out


def test_yaml_set_keeps_comments_and_replaces_blocks():
    text = ("---\n# Who may log in\ndoAutologin: false\n\n# Rules\npasswordRequirements:\n"
            "    nonempty: true\n    minLength: -1  # no minimum\n\n# Groups\ndefaultGroups:\n- users\n- sudo\n"
            "setRootPassword: true\n")
    out = yamlconf.update(text, {"doAutologin": True, "passwordRequirements": {"nonempty": True, "minLength": 8},
                                 "defaultGroups": ["users", "audio"], "newKey": "x"})
    data = yamlconf.load(out)
    assert data["doAutologin"] is True and data["passwordRequirements"]["minLength"] == 8
    assert data["defaultGroups"] == ["users", "audio"] and data["setRootPassword"] is True
    assert data["newKey"] == "x"
    assert "# Who may log in" in out and "# Groups" in out and "# Rules" in out
    assert yamlconf.load(yamlconf.set_key(out, "newKey", None)).get("newKey") is None


# Calamares ---------------------------------------------------------------------------

USERS = """---
# Debian users module
defaultGroups:
    - cdrom
    - name: sudo
      must_exist: true
    - audio
autoLoginGroup: autologin
doAutologin: false
sudoersGroup: sudo
setRootPassword: false
doReusePassword: true
passwordRequirements:
    nonempty: true
    minLength: -1
    maxLength: -1
allowWeakPasswords: false
user:
  shell: /bin/bash
"""


@pytest.fixture
def cal_project(project):
    r = project.rootfs
    (r / "etc/calamares/modules").mkdir(parents=True)
    (r / "usr/share/calamares/modules").mkdir(parents=True)
    (r / "etc/calamares/branding/debian").mkdir(parents=True)
    (r / "usr/bin/calamares").write_text("")
    (r / "etc/calamares/settings.conf").write_text("---\n# sequence\nsequence:\n- show:\n  - welcome\n"
                                                  "branding: debian\n")
    (r / "etc/calamares/modules/users.conf").write_text(USERS)
    (r / "usr/share/calamares/modules/partition.conf").write_text(
        "# upstream defaults\nefi:\n    mountPoint: \"/boot/efi\"\n    recommendedSize: 300MiB\n"
        "userSwapChoices:\n    - none\n    - small\ninitialSwapChoice: none\ndefaultFileSystemType: \"ext4\"\n")
    (r / "etc/calamares/modules/welcome.conf").write_text(
        "requirements:\n    requiredStorage: 9\n    requiredRam: 1.0\n    check: [storage, ram, power, internet, root]\n"
        "    required: [storage, ram, root, internet]\n")
    (r / "etc/calamares/modules/packages.conf").write_text(
        "backend: apt\noperations:\n  - remove:\n      - live-boot\n  - try_install:\n      - foo\n")
    (r / "etc/calamares/branding/debian/branding.desc").write_text(
        "---\ncomponentName: debian\n# Strings\nstrings:\n    productName: Debian\n    version: 13\n"
        "images:\n    productLogo: \"logo.png\"\nstyle:\n    sidebarBackground: \"#2c3133\"\n"
        "slideshow: \"show.qml\"\n")
    (r / "usr/share/applications").mkdir(parents=True)
    (r / "usr/share/applications/install-debian.desktop").write_text(
        "[Desktop Entry]\nType=Application\nName=Install Debian\nName[pt]=Instalar Debian\n"
        "Exec=install-debian\n")
    return project


def test_calamares_users_partition_requirements(cal_project):
    c = Calamares(cal_project)
    assert c.installed() and c.branding_name() == "debian"
    c.set_users(autologin=True, root_password=True, min_length=8, weak=True, weak_default=True,
                groups=["sudo", "audio", "video"], shell="/usr/bin/zsh", hostname="${first}-edukasaun")
    text = (cal_project.rootfs / "etc/calamares/modules/users.conf").read_text()
    assert "# Debian users module" in text
    s = c.summary()["users"]
    assert s["autologin"] and s["root_password"] and s["min_length"] == 8 and s["weak_default"]
    assert s["groups"] == ["sudo", "audio", "video"] and s["shell"] == "/usr/bin/zsh"
    assert s["hostname"] == "${first}-edukasaun"
    # The dict form of a group that stays is kept.
    assert {"name": "sudo", "must_exist": True} in c.read("users")["defaultGroups"]

    c.set_partition(efi_size="512MiB", fs="btrfs", filesystems=["ext4"], swap=["none", "file"],
                    initial_swap="file", initial="erase", luks=True, luks2=True)
    part = c.read("partition")
    assert (cal_project.rootfs / "etc/calamares/modules/partition.conf").exists()
    assert part["efi"] == {"mountPoint": "/boot/efi", "recommendedSize": "512MiB"}
    assert part["defaultFileSystemType"] == "btrfs" and part["availableFileSystemTypes"] == ["ext4", "btrfs"]
    assert part["luksGeneration"] == "luks2" and part["initialPartitioningChoice"] == "erase"
    with pytest.raises(ValueError):
        c.set_partition(efi_size="huge")

    c.set_requirements(storage=20, ram=2, internet=False, power=True)
    req = c.read("welcome")["requirements"]
    assert req["requiredStorage"] == 20 and "internet" not in req["required"] and "power" in req["required"]

    c.set_removed_packages(["live-boot", "calamares"])
    ops = c.read("packages")["operations"]
    assert ops[0] == {"try_remove": ["live-boot", "calamares"]} and {"try_install": ["foo"]} in ops
    assert c.summary()["remove"] == ["live-boot", "calamares"]
    c.set_finished("always")
    assert c.read("finished")["restartNowMode"] == "always"


def test_calamares_branding_images_slides_launcher(cal_project, tmp_path, nochroot):
    c = Calamares(cal_project)
    logo, s1, s2 = png(tmp_path / "logo.png"), png(tmp_path / "a.png", "#ff0000"), png(tmp_path / "b.png")
    c.set_branding(strings={"productName": "Edukasaun OS", "version": "1.0"},
                   colors={"sidebarBackground": "#0f2f27"}, images={"productLogo": logo, "productIcon": logo},
                   slides=[s1, s2], slide_seconds=5)
    br = c.branding()
    d = c.branding_dir()
    assert br["strings"]["productName"] == "Edukasaun OS" and br["style"]["sidebarBackground"] == "#0f2f27"
    assert c.style()["sidebarBackground"] == "#0f2f27"
    assert br["images"]["productIcon"] == "icon.png" and (d / "icon.png").exists()
    assert len(c.slides()) == 2 and "interval: 5000" in (d / "show.qml").read_text()
    assert "# Strings" in (d / "branding.desc").read_text()
    with pytest.raises(ValueError):
        c.set_branding(colors={"sidebarText": "red"})
    c.set_launcher_name("Install Edukasaun OS")
    text = (cal_project.rootfs / "usr/share/applications/install-debian.desktop").read_text()
    assert "Name=Install Edukasaun OS" in text and "Install Debian" not in text


@pytest.mark.skipif(not shutil.which("openssl"), reason="openssl missing")
def test_live_password(cal_project):
    c = Calamares(cal_project)
    c.set_live_password("geheim")
    script = c._live_script()
    text = script.read_text()
    assert "$6$" in text and "geheim" not in text and os.access(script, os.X_OK)
    subprocess.run(["sh", "-n", str(script)], check=True)
    c.set_live_password("")
    assert not script.exists()


# Language -------------------------------------------------------------------------------

def test_language_catalog_and_packs():
    cat = language.catalog()
    assert {"pt_PT.UTF-8", "id_ID.UTF-8", "en_US.UTF-8"} <= {l["locale"] for l in cat}
    pt = language.info("pt_PT.UTF-8")
    assert pt["native"] == "Português" and pt["keyboard"] == "pt"
    # The time zone stays Asia/Dili whatever the language.
    assert language.boot_params("pt_PT.UTF-8") == "locales=pt_PT.UTF-8 keyboard-layouts=pt timezone=Asia/Dili"
    names = language.pack_candidates(["pt_PT.UTF-8", "ja_JP.UTF-8"], {"libreoffice-core", "firefox-esr"})
    assert "libreoffice-l10n-pt" in names and "firefox-esr-l10n-pt-pt" in names and "hunspell-pt-pt" in names
    assert "thunderbird-l10n-pt-pt" not in names  # Thunderbird is not installed
    assert "fcitx5-mozc" in names and len(names) == len(set(names))
    # Unknown locales fall back gracefully.
    assert language.info("xx_YY.UTF-8")["keyboard"] == "us"


def test_language_apply(project, nochroot, monkeypatch):
    from eduka_customizer.core.branding import Branding
    seen = {}
    monkeypatch.setattr(Branding, "apply_locale", lambda self, *a: seen.setdefault("locale", a))
    monkeypatch.setattr(language.Language, "install_packs", lambda self, locales: ["hunspell-pt-pt"])
    out = language.Language(project).apply("pt_PT.UTF-8", ["en_US.UTF-8"], boot_menu=["pt_PT.UTF-8", "en_US.UTF-8"])
    assert out == ["hunspell-pt-pt"]
    assert seen["locale"] == ("pt_PT.UTF-8", ["en_US.UTF-8"], "Asia/Dili", "pt", "")
    st = project.state["language"]
    assert st["boot_menu"] == ["pt_PT.UTF-8", "en_US.UTF-8"] and st["keyboard"] == "pt"
    entries = language.Language(project).boot_entries("Edukasaun OS")
    assert entries[0] == ("Edukasaun OS (Português)",
                          "locales=pt_PT.UTF-8 keyboard-layouts=pt timezone=Asia/Dili")
    assert entries[1][1].startswith("locales=en_US.UTF-8 keyboard-layouts=us")


# Boot menu ----------------------------------------------------------------------------------

GRUB = """set timeout=10
menuentry "Live system (amd64)" --hotkey=l {
\tlinux\t/live/vmlinuz-6.12.38+deb13-amd64 boot=live components quiet splash findiso=${iso_path}
\tinitrd\t/live/initrd.img-6.12.38+deb13-amd64
}
menuentry "Live system (amd64 fail-safe mode)" {
\tlinux\t/live/vmlinuz boot=live components memtest noapic
\tinitrd\t/live/initrd.img
}
"""

ISOLINUX = """label live-amd64
\tmenu label ^Live system (amd64)
\tmenu default
\tlinux /live/vmlinuz
\tinitrd /live/initrd.img
\tappend boot=live components quiet splash

label live-amd64-failsafe
\tmenu label Live system (fail-safe)
\tlinux /live/vmlinuz
\tinitrd /live/initrd.img
\tappend boot=live components memtest
"""


@pytest.fixture
def isotree(project):
    iso = project.isodir
    (iso / "boot/grub").mkdir(parents=True)
    (iso / "isolinux").mkdir(parents=True)
    (iso / "live").mkdir(parents=True)
    (iso / "boot/grub/grub.cfg").write_text(GRUB)
    (iso / "isolinux/live.cfg").write_text(ISOLINUX)
    return project


def test_language_entries_grub_and_isolinux(isotree):
    iso = isotree.isodir
    entries = [("Edukasaun OS (Português)", "locales=pt_PT.UTF-8 keyboard-layouts=pt timezone=Europe/Lisbon"),
               ("Edukasaun OS (English)", "locales=en_US.UTF-8 keyboard-layouts=us")]
    assert bootloader.set_language_entries(iso, entries)
    grub = (iso / "boot/grub/grub.cfg").read_text()
    assert grub.count('submenu "Language"') == 1 and 'menuentry "Edukasaun OS (Português)"' in grub
    assert "--hotkey" not in grub.split("submenu", 1)[1].split("menuentry \"Live system (amd64 fail")[0]
    assert "quiet splash findiso=${iso_path} locales=pt_PT.UTF-8 keyboard-layouts=pt" in grub
    if shutil.which("grub-script-check"):
        subprocess.run(["grub-script-check"], input=grub, text=True, check=True)
    iso_text = (iso / "isolinux/live.cfg").read_text()
    assert "menu begin languages" in iso_text and "label lang2" in iso_text
    assert "append boot=live components quiet splash locales=en_US.UTF-8 keyboard-layouts=us" in iso_text
    assert iso_text.count("menu default") == 1
    # Idempotent, and removable.
    assert not bootloader.set_language_entries(iso, entries)
    bootloader.set_language_entries(iso, [])
    assert (iso / "boot/grub/grub.cfg").read_text() == GRUB
    assert (iso / "isolinux/live.cfg").read_text() == ISOLINUX
    # The build adds the common options to every live entry, the language copies included.
    bootloader.set_language_entries(iso, entries)
    bootloader.append_params(iso, "quiet splash toram")
    grub = (iso / "boot/grub/grub.cfg").read_text()
    assert grub.count("submenu") == 1 and grub.count("toram") == 4


def test_append_params_handles_tabs(isotree):
    bootloader.append_params(isotree.isodir, "quiet splash toram")
    grub = (isotree.isodir / "boot/grub/grub.cfg").read_text()
    assert grub.count("toram") == 2


def test_bootedit_overrides_and_revert(isotree):
    p = isotree
    assert "boot/grub/grub.cfg" in bootedit.files(p) and "isolinux/live.cfg" in bootedit.files(p)
    new = GRUB.replace("set timeout=10", "set timeout=3")
    bootedit.save(p, "boot/grub/grub.cfg", new)
    assert bootedit.overrides(p) == ["boot/grub/grub.cfg"]
    # A regenerated menu loses the edit until the overrides are applied again.
    (p.isodir / "boot/grub/grub.cfg").write_text(GRUB)
    assert bootedit.apply_overrides(p) == 1
    assert "timeout=3" in bootedit.read(p, "boot/grub/grub.cfg")
    bootedit.revert(p, "boot/grub/grub.cfg")
    assert bootedit.read(p, "boot/grub/grub.cfg") == GRUB and not bootedit.overrides(p)
    with pytest.raises(ValueError):
        bootedit.read(p, "../../etc/passwd")
    problems = bootedit.validate(p, "boot/grub/grub.cfg", "menuentry x {\n linux /boot/missing\n")
    assert any("{" in pr for pr in problems) and any("/boot/missing" in pr for pr in problems)
    assert bootedit.validate(p, "isolinux/live.cfg", "include nothere.cfg\n")


@needs_mtools
def test_bootedit_efi_image(isotree, tmp_path):
    p = isotree
    img = p.isodir / "boot/grub/efi.img"
    subprocess.run(["mkfs.vfat", "-C", str(img), "2048"], check=True, capture_output=True)
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    cfg = tmp_path / "grub.cfg"
    cfg.write_text("search --file --set=root /.disk/id/abc\nset prefix=($root)/boot/grub\n")
    for cmd in (["mmd", "-i", str(img), "::/EFI"], ["mmd", "-i", str(img), "::/EFI/boot"],
                ["mcopy", "-i", str(img), str(cfg), "::/EFI/boot/grub.cfg"]):
        subprocess.run(cmd, check=True, env=env, capture_output=True)
    key = "efi.img:EFI/boot/grub.cfg"
    assert key in bootedit.files(p)
    assert "search --file" in bootedit.read(p, key)
    bootedit.save(p, key, "set prefix=($root)/boot/grub\nconfigfile $prefix/grub.cfg\n")
    assert "configfile" in bootedit.read(p, key)
    bootedit.revert(p, key)
    assert "search --file" in bootedit.read(p, key)


# Plymouth ------------------------------------------------------------------------------------

def _theme(base, name, module="script"):
    d = base / name
    d.mkdir(parents=True)
    (d / (name + ".plymouth")).write_text(
        "[Plymouth Theme]\nName={0} theme\nDescription=Test {0}\nModuleName={1}\n\n[script]\n"
        "ImageDir=/somewhere/else\nScriptFile=/somewhere/else/{0}.script\n".format(name, module))
    (d / (name + ".script")).write_text("// script\n")
    return d


def test_plymouth_themes_install_remove(project, tmp_path, nochroot, monkeypatch):
    r = project.rootfs
    base = r / "usr/share/plymouth/themes"
    _theme(base, "spinner", "two-step")
    png(base / "spinner/watermark.png")
    (r / "var/lib/dpkg/info").mkdir(parents=True, exist_ok=True)
    (r / "var/lib/dpkg/info/plymouth-themes.list").write_text(
        "/usr/share/plymouth/themes/spinner\n/usr/share/plymouth/themes/spinner/spinner.plymouth\n")
    (r / "etc/plymouth").mkdir(parents=True)
    (r / "etc/plymouth/plymouthd.conf").write_text("[Daemon]\nTheme=spinner\n")
    ply = Plymouth(project)
    themes = {t["name"]: t for t in ply.themes()}
    assert themes["spinner"]["owner"] == "plymouth-themes" and themes["spinner"]["current"]
    assert themes["spinner"]["preview"].endswith("watermark.png")

    src = _theme(tmp_path / "src", "edu")
    archive = tmp_path / "edu.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for f in src.iterdir():
            zf.write(f, "edu-theme/" + f.name)
    assert ply.install(archive) == "edu"
    text = (base / "edu/edu.plymouth").read_text()
    assert "ImageDir=/usr/share/plymouth/themes/edu" in text and "ScriptFile=/usr/share/plymouth/themes/edu/edu.script" in text

    src2 = _theme(tmp_path / "src2", "tarred")
    with tarfile.open(tmp_path / "t.tar.xz", "w:xz") as tf:
        tf.add(src2, arcname="tarred")
    assert ply.install(tmp_path / "t.tar.xz") == "tarred"
    src3 = _theme(tmp_path / "src3", "single")
    assert ply.install(src3 / "single.plymouth") == "single"
    with pytest.raises(ValueError):
        ply.install(tmp_path / "logo.txt") if (tmp_path / "logo.txt").write_text("x") else None

    with pytest.raises(ValueError):
        ply.remove("spinner")  # current theme
    (r / "etc/plymouth/plymouthd.conf").write_text("[Daemon]\nTheme=edu\n")
    with pytest.raises(ValueError):
        ply.remove("spinner")  # part of plymouth-themes, which holds other themes
    ply.remove("tarred")
    assert not (base / "tarred").exists()

    ply.set_settings(show_delay=2, device_scale="2")
    assert ply.settings() == {"show_delay": "2", "device_scale": "2"}
    ply.set_settings(show_delay=0, device_scale="auto")
    assert ply.settings()["device_scale"] == "auto"


@pytest.mark.skipif(not shutil.which("dpkg-deb"), reason="dpkg-deb missing")
def test_plymouth_theme_in_deb(project, tmp_path):
    root = tmp_path / "pkg"
    _theme(root / "usr/share/plymouth/themes", "debtheme")
    (root / "DEBIAN").mkdir()
    (root / "DEBIAN/control").write_text("Package: plymouth-theme-debtheme\nVersion: 1\nArchitecture: all\n"
                                        "Maintainer: x <x@example.org>\nDescription: test\n")
    subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(root), str(tmp_path / "t.deb")],
                   check=True, capture_output=True)
    assert Plymouth(project)._theme_in_deb(tmp_path / "t.deb") == "debtheme"


# Kernel ------------------------------------------------------------------------------------------

STATUS_KERNELS = """
Package: linux-image-6.12.38+deb13-amd64
Status: install ok installed
Maintainer: Debian Kernel Team <debian-kernel@lists.debian.org>
Version: 6.12.38-1
Installed-Size: 400000
Description: Linux 6.12 for 64-bit PCs (signed)

Package: linux-image-amd64
Status: hold ok installed
Maintainer: Debian Kernel Team <debian-kernel@lists.debian.org>
Version: 6.12.38-1
Description: Linux for 64-bit PCs (meta-package)

Package: linux-headers-6.12.38+deb13-amd64
Status: install ok installed
Version: 6.12.38-1
Description: headers
"""


@pytest.fixture
def kproject(project):
    r = project.rootfs
    with open(r / "var/lib/dpkg/status", "a") as fh:
        fh.write(STATUS_KERNELS)
    (r / "boot").mkdir()
    for v in ("6.12.38+deb13-amd64", "6.14.2-custom"):
        (r / "boot" / ("vmlinuz-" + v)).write_bytes(b"k" * 1024)
        (r / "boot" / ("initrd.img-" + v)).write_bytes(b"i")
    (r / "lib/modules/6.14.2-custom").mkdir(parents=True)
    return project


def test_kernels_list_remove_iso(kproject, nochroot):
    k = Kernels(kproject)
    kernels, meta = k.installed()
    assert [x["version"] for x in kernels] == ["6.12.38+deb13-amd64", "6.14.2-custom"]
    assert kernels[0]["package"] == "linux-image-6.12.38+deb13-amd64" and kernels[0]["origin"] == "Debian"
    assert kernels[1]["origin"] == "copied by hand" and kernels[1]["iso"]
    assert meta == [{"package": "linux-image-amd64", "version": "6.12.38-1", "held": True}]
    k.use_for_iso("6.12.38+deb13-amd64")
    assert k.installed()[0][0]["iso"]
    k.copy_to_iso("6.12.38+deb13-amd64")
    assert (kproject.isodir / "live/vmlinuz").read_bytes() == b"k" * 1024
    k.remove("6.12.38+deb13-amd64")
    assert nochroot["remove"] == [["linux-image-6.12.38+deb13-amd64", "linux-headers-6.12.38+deb13-amd64"]]
    assert kproject.state["boot"]["kernel"] == ""
    k.remove("6.14.2-custom")  # not a package: files are deleted
    assert not (kproject.rootfs / "boot/vmlinuz-6.14.2-custom").exists()
    assert not (kproject.rootfs / "lib/modules/6.14.2-custom").exists()
    with pytest.raises(ValueError):
        k.remove("../../etc")


def test_kernel_only_one_cannot_be_removed(kproject, nochroot):
    (kproject.rootfs / "boot/vmlinuz-6.14.2-custom").unlink()
    with pytest.raises(ValueError, match="only kernel"):
        Kernels(kproject).remove("6.12.38+deb13-amd64")


def test_grub_defaults(kproject):
    k = Kernels(kproject)
    (kproject.rootfs / "etc/default").mkdir(parents=True, exist_ok=True)
    (kproject.rootfs / "etc/default/grub").write_text('GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n'
                                                     'GRUB_CMDLINE_LINUX_DEFAULT="quiet"\n')
    k.set_grub_defaults({"GRUB_TIMEOUT": "2", "GRUB_CMDLINE_LINUX_DEFAULT": "quiet splash",
                         "GRUB_DISABLE_OS_PROBER": "false", "GRUB_GFXMODE": ""})
    g = k.grub_defaults()
    assert g["GRUB_TIMEOUT"] == "2" and g["GRUB_CMDLINE_LINUX_DEFAULT"] == "quiet splash"
    assert g["GRUB_DEFAULT"] == "0" and "GRUB_GFXMODE" not in g
    with pytest.raises(ValueError):
        k.set_grub_defaults({"GRUB_CMDLINE_LINUX_DEFAULT": 'x" ; rm -rf /'})
    assert not k.update_grub()  # live images have no installed GRUB menu


def test_third_party_kernel_repository(kproject, nochroot, monkeypatch):
    from eduka_customizer.core import apt
    monkeypatch.setattr(apt.Sources, "install_key", lambda self, name, key: self.rootfs / "etc/apt/keyrings/x.gpg")
    k = Kernels(kproject)
    k.install_third_party("liquorix", headers=False)
    text = (kproject.rootfs / "etc/apt/sources.list.d/liquorix.sources").read_text()
    assert "URIs: https://liquorix.net/debian" in text and "Suites: trixie" in text
    assert nochroot["install"][-1] == ["linux-image-liquorix-amd64"]
    k.install_third_party("backports")
    bp = (kproject.rootfs / "etc/apt/sources.list.d/debian-backports.sources").read_text()
    assert "Suites: trixie-backports" in bp
    assert any("-t" in cmd and "trixie-backports" in cmd for cmd in nochroot["run"])
    with pytest.raises(ValueError):
        k.install_third_party("nonsense")


# GUI smoke --------------------------------------------------------------------------------------

GUI_SMOKE = """
import sys
from eduka_customizer.qt.widgets import QApplication
app = QApplication([])
from eduka_customizer.core.project import Project
from eduka_customizer.gui.main_window import MainWindow
w = MainWindow()
w.project = Project.open(sys.argv[1])
names = [p.__class__.__name__ for p in w.pages]
for wanted in ("LanguagePage", "CalamaresPage", "PlymouthPage", "BootMenuPage", "KernelPage", "UsersPage"):
    w.pages[names.index(wanted)].refresh()
assert w.pages[names.index("BootMenuPage")].files.count() >= 2
assert w.pages[names.index("CalamaresPage")].s["productName"].text() == "Debian"
print("ok", len(names))
"""


def test_new_pages_build_and_refresh(cal_project, isotree):
    import sys
    cal_project.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen",
               PYTHONPATH=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    res = subprocess.run([sys.executable, "-c", GUI_SMOKE, str(cal_project.path)], capture_output=True,
                         text=True, env=env, timeout=120)
    assert res.returncode == 0, res.stderr[-3000:]
    assert res.stdout.startswith("ok 24")


def test_every_data_file_is_installed():
    """Each data_file("x") used by the code must be installed by the Makefile."""
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    used = set()
    for py in (root / "eduka_customizer").rglob("*.py"):
        used |= set(re.findall(r'data_file\("([^"]+)"\)', py.read_text()))
    makefile = (root / "Makefile").read_text()
    missing = [f for f in sorted(used) if "data/" + f not in makefile]
    assert used and not missing, missing
