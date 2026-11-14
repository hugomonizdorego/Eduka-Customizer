"""D!sco 0.11: platforms, SD-card images, package lists, presets, the build pipeline,
live-build, system files, terminal and browser branding, the desktop document,
and the fixes of the code review."""

import json
import os
import shutil
import struct
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from disco.core import platforms  # noqa: E402

has = shutil.which


@pytest.fixture
def nochroot(monkeypatch):
    from disco.core import apt, chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(list(cmd)) or 0)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "install", lambda self, *a, **k: None)
    return calls


# Platforms --------------------------------------------------------------------------------------------
def test_platforms():
    ids = [p.id for p in platforms.PLATFORMS]
    assert ids[:4] == ["pc64", "pc32", "arm64-efi", "rpi-arm64"]
    assert platforms.get("rpi-arm64").output == "img" and platforms.get("pc64").output == "iso"
    assert platforms.kernel_package("i386") == "linux-image-686-pae"
    assert platforms.kernel_package("armhf") == "linux-image-armmp"
    assert platforms.for_arch("arm64", "iso").id == "arm64-efi"
    ok, why = platforms.release_ok(platforms.get("pc32"), "trixie")
    assert not ok and "32-bit" in why
    assert platforms.release_ok(platforms.get("pc32"), "bookworm")[0]
    assert "raspi-firmware" in platforms.get("rpi-arm64").packages
    with pytest.raises(KeyError):
        platforms.get("ppc64el")


def test_packages_for():
    from disco.core.bootstrap import packages_for
    pc = packages_for(platforms.get("pc64"))
    assert "live-boot" in pc and "linux-image-amd64" in pc and "firmware-iwlwifi" in pc
    pi = packages_for(platforms.get("rpi-arm64"))
    assert "live-boot" not in pi and "raspi-firmware" in pi and "firmware-iwlwifi" not in pi
    dev = packages_for(platforms.get("pc64"), devuan=True)
    assert "sysvinit-core" in dev and "systemd-sysv" not in dev and "elogind" in dev
    assert len(pc) == len(set(pc))


def test_dpkg_and_elf_arch(tmp_path):
    from disco.core.distro import dpkg_arch, elf_arch
    r = tmp_path / "r"
    (r / "var/lib/dpkg").mkdir(parents=True)
    (r / "var/lib/dpkg/status").write_text("Package: dpkg\nStatus: install ok installed\nArchitecture: arm64\n\n")
    assert dpkg_arch(r) == "arm64" and elf_arch(r) == "arm64"
    # Without dpkg: the ELF header of /usr/bin/env (32-bit ARM, hard float: e_flags 0x400)
    r2 = tmp_path / "r2"
    (r2 / "usr/bin").mkdir(parents=True)
    head = b"\x7fELF" + bytes([1, 1, 1]) + bytes(9) + struct.pack("<HHI", 2, 40, 1) + bytes(12) + \
        struct.pack("<I", 0x05000400) + bytes(16)
    (r2 / "usr/bin/env").write_bytes(head)
    assert elf_arch(r2) == "armhf"
    (r2 / "usr/bin/env").write_bytes(head[:36] + struct.pack("<I", 0x05000200) + head[40:])
    assert elf_arch(r2) == "armel"


def test_forget_build_host(project):
    from disco.core.bootstrap import forget_build_host
    (project.rootfs / "etc/hostname").write_text("buildhost\n")
    (project.rootfs / "etc/resolv.conf").write_text("nameserver 10.0.0.1\n")
    forget_build_host(project, "debian")
    assert (project.rootfs / "etc/hostname").read_text() == "edukasaun\n"
    assert (project.rootfs / "etc/resolv.conf").read_text() == ""
    assert "127.0.1.1\tedukasaun" in (project.rootfs / "etc/hosts").read_text()


# SD-card images ------------------------------------------------------------------------------------------
needs_img = pytest.mark.skipif(not all(has(t) for t in ("sfdisk", "mkfs.vfat", "mcopy", "mkfs.ext4", "mdir")),
                               reason="sfdisk, dosfstools, mtools or e2fsprogs missing")


@needs_img
def test_image_assemble(project):
    from disco.core import imgbuild
    project.state.setdefault("builder", {})["platform"] = "rpi-arm64"
    r = project.rootfs
    fw = r / "boot/firmware"
    fw.mkdir(parents=True)
    (fw / "config.txt").write_text("arm_64bit=1\n")
    (fw / "start4.elf").write_bytes(b"x" * 1000)
    (r / "etc/fstab").write_text("x\n")
    b = imgbuild.ImageBuilder(project, imgbuild.ImageOptions(boot_mb=64, compress="none"))
    target = b.assemble(project.output / "t.img")
    table = subprocess.run(["sfdisk", "-d", str(target)], capture_output=True, text=True).stdout
    assert "start=        8192, size=      131072, type=c, bootable" in table
    assert "type=83" in table
    env = dict(os.environ, MTOOLS_SKIP_CHECK="1")
    listing = subprocess.run(["mdir", "-b", "-i", "{}@@4M".format(target), "::/"], capture_output=True, text=True,
                             env=env).stdout
    assert "::/start4.elf" in listing and "::/sysconf.txt" in listing and "::/config.txt" in listing
    assert (r / "boot/firmware/start4.elf").exists()          # the boot folder is back in the system
    assert not (project.cache / "img").exists()
    root = subprocess.run(["dd", "if={}".format(target), "bs=1M", "skip=68", "status=none"], capture_output=True)
    part = project.cache / "root.ext4"
    part.write_bytes(root.stdout)
    label = subprocess.run(["e2label", str(part)], capture_output=True, text=True).stdout.strip()
    assert label == "RASPIROOT"


def test_image_configure(project, nochroot, monkeypatch):
    from disco.core import imgbuild, initsystem
    monkeypatch.setattr(initsystem, "sync_services", lambda *a, **k: None)
    project.state.setdefault("builder", {})["platform"] = "rpi-arm64"
    b = imgbuild.ImageBuilder(project, imgbuild.ImageOptions(config_txt="dtparam=audio=on", cmdline="quiet"))
    b.configure()
    r = project.rootfs
    assert "LABEL=RASPIROOT\t/\text4" in (r / "etc/fstab").read_text()
    assert "ROOTPART=LABEL=RASPIROOT" in (r / "etc/default/raspi-firmware").read_text()
    assert "dtparam=audio=on" in (r / "etc/default/raspi-firmware-custom").read_text()
    assert (r / "etc/default/raspi-extra-cmdline").read_text() == "quiet\n"
    assert os.access(r / imgbuild.FIRSTBOOT, os.X_OK)
    assert (r / "etc/systemd/system/multi-user.target.wants/disco-firstboot.service").is_symlink()
    with pytest.raises(ValueError):
        imgbuild.check_lines("dtparam=$(reboot)", "config.txt")


def test_flash_command():
    from disco.core.imgbuild import flash_command
    assert flash_command("/x/a.img.xz") == "xzcat a.img.xz | sudo dd of=/dev/sdX bs=4M status=progress conv=fsync"
    assert flash_command("/x/a.img", "/dev/mmcblk0").startswith("sudo dd if=a.img of=/dev/mmcblk0")


def test_firstboot_script_syntax():
    from disco.core.config import data_file
    assert subprocess.run(["sh", "-n", str(data_file("board", "disco-firstboot"))]).returncode == 0


# Boot and QEMU for ARM ------------------------------------------------------------------------------------
def test_efi_formats(project):
    from disco.core.bootloader import BootGenerator
    project.state["distro"]["arch"] = "arm64"
    g = BootGenerator(project)
    assert g.arch == "arm64" and g.efi_format() == ("arm64-efi", "bootaa64.efi")
    project.state["distro"]["arch"] = "riscv64"
    assert BootGenerator(project).efi_format() == ("riscv64-efi", "bootriscv64.efi")
    assert BootGenerator(project)._bios({}, "T", "", 5) is False     # no BIOS on RISC-V


def test_qemu_arm_command(project, monkeypatch, tmp_path):
    from disco.core import qemu, runner
    monkeypatch.setattr(runner, "which", lambda name: "/usr/bin/" + name)
    iso = tmp_path / "a,b.iso"
    iso.write_bytes(b"")
    fw = tmp_path / "AAVMF_CODE.fd"
    fw.write_bytes(b"")
    monkeypatch.setitem(qemu.ARM_EFI, "arm64", [str(fw)])
    cmd = qemu.arm_command(project, iso, "arm64", memory=2048, cpus=2, display="none")
    assert cmd[0].endswith("qemu-system-aarch64") and "virt" in cmd and "-bios" in cmd
    assert any("a,,b.iso" in c for c in cmd)                   # commas doubled inside -drive
    project.state["distro"]["arch"] = "armel"
    project.state["last_iso"] = str(iso)
    with pytest.raises(RuntimeError, match="ARMv6"):
        qemu.start(project)


# Package lists and presets ---------------------------------------------------------------------------------
def test_lists(project):
    from disco.core.pkglists import Lists, friendly_section
    lst = Lists(project)
    assert lst.ensure_defaults(platforms.get("pc64"), "education", "calamares")
    assert not lst.ensure_defaults(platforms.get("pc64"))
    names = [l.name for l in lst.all()]
    assert names == ["10-kernel-and-firmware.list", "20-system-tools.list", "30-applications.list",
                     "40-installer.list", "50-my-packages.list"]
    apps = lst.get("applications")
    assert "gcompris-qt" in apps.packages() and apps.title == "Applications"
    mine = lst.get("50-my-packages.list")
    lst.add(mine, ["gparted", "-nano"])
    inst, rem = lst.plan()
    assert "gparted" in inst and rem == ["nano"] and "nano" not in inst
    lst.set_on(lst.get("installer"), False)
    assert "calamares" not in lst.plan()[0]
    moved = lst.move(mine, -1)
    assert [l.name for l in lst.all()][3] == moved.name and moved.slug == "my-packages"
    assert not lst.is_on(lst.get("installer"))              # switched off stays off after renumbering
    new = lst.create("Games for kids", ["supertuxkart"])
    assert new.name.endswith("-games-for-kids.list")
    with pytest.raises(ValueError):
        new.write(["good", "bad name"])
    renamed = lst.rename(new, "Fun")
    assert renamed.slug == "fun" and renamed.title == "Fun"
    assert friendly_section("contrib/net") == "Internet" and friendly_section("libs") == "Libraries"


def test_catalog_names_are_debian_names():
    from disco.core.pkglists import PACKAGE, catalog
    cats = catalog()
    assert len(cats) >= 10
    for c in cats:
        for pkg, name, desc in c["apps"]:
            assert PACKAGE.match(pkg) and name and desc, pkg


def test_presets(project, monkeypatch, tmp_path):
    from disco.core import presets
    from disco.core.config import settings
    monkeypatch.setattr(settings(), "get", lambda s, k, _orig=settings().get: str(tmp_path / "projects")
                        if (s, k) == ("general", "projects_dir") else _orig(s, k))
    names = [n for n, _p, b in presets.available() if b]
    assert "Raspberry Pi desktop (Pi 3, 4, 400)" in names and len(names) >= 10
    pi = presets.find("Raspberry Pi desktop (Pi 3, 4, 400)")
    presets.apply(project, pi)
    assert project.state["builder"]["platform"] == "rpi-arm64"
    from disco.core.pkglists import Lists
    lst = Lists(project)
    assert "35-remote-access.list" in [l.name for l in lst.all()]
    assert "10-kernel-and-firmware.list" in [l.name for l in lst.all()]    # completed from the platform
    assert "40-installer.list" not in [l.name for l in lst.all()]         # SD cards have no installer
    saved = presets.save(presets.from_project(project, "My Pi"))
    assert saved.parent == tmp_path / "projects/presets"
    assert presets.find("My Pi")["builder"]["platform"] == "rpi-arm64"
    presets.delete("My Pi")
    with pytest.raises(PermissionError):
        presets.delete(names[0])
    with pytest.raises(ValueError):
        presets.normalize({"name": "x", "builder": {"platform": "pc64", "family": "ubuntu"}})
    dev = presets.normalize({"name": "x", "builder": {"family": "devuan", "init": "systemd"}})
    assert dev["builder"]["init"] == "sysvinit"


# Pipeline, overlay and live-build ---------------------------------------------------------------------------
def test_pipeline_check_and_prepare(project, monkeypatch):
    from disco.core import pipeline
    monkeypatch.setattr(platforms, "host_requirements", lambda p, m="": [("lb", "live-build", "the live-build route")])
    project.state["builder"] = {"platform": "rpi-arm64", "method": "live-build", "family": "devuan",
                                "desktop": "gnome", "init": "sysvinit"}
    text = " ".join(t for ok, t in pipeline.Pipeline(project).check() if not ok)
    assert "ISO images only" in text and "Debian's tool" in text and "needs systemd" in text
    project.state["builder"] = {"platform": "pc64", "desktop": "xfce"}
    monkeypatch.setattr(platforms, "host_requirements", lambda p, m="": [])
    problems = pipeline.Pipeline(project).prepare()
    assert problems == []
    for d in ("lists", "overlay", "hooks", "debs"):
        assert (project.path / d).is_dir()
    assert pipeline.Pipeline(project).status()["prepare"]


def test_copy_overlay(project, tmp_path):
    from disco.core.pipeline import copy_overlay
    src = tmp_path / "overlay"
    (src / "etc/skel").mkdir(parents=True)
    (src / "etc/skel/.hello").write_text("hi")
    (src / "README.txt").write_text("not copied")
    (src / "usr/local/bin").mkdir(parents=True)
    (src / "usr/local/bin/tool").write_text("#!/bin/sh\n")
    (src / "usr/local/bin/tool").chmod(0o755)
    os.symlink("tool", src / "usr/local/bin/tool2")
    n = copy_overlay(src, project.rootfs)
    assert n == 3
    r = project.rootfs
    assert (r / "etc/skel/.hello").read_text() == "hi" and not (r / "README.txt").exists()
    assert os.access(r / "usr/local/bin/tool", os.X_OK) and os.readlink(r / "usr/local/bin/tool2") == "tool"
    # A link in the system that points outside is never followed.
    os.symlink("/tmp", r / "escape")
    bad = tmp_path / "bad"
    (bad / "escape").mkdir(parents=True)
    (bad / "escape/x").write_text("x")
    with pytest.raises(RuntimeError):
        copy_overlay(bad, project.rootfs)


def test_livebuild_config(project, tmp_path):
    from disco.core import livebuild, presets
    presets.apply(project, presets.find("Debian Xfce with live-build (PC 64-bit)"))
    (project.path / "hooks").mkdir(exist_ok=True)
    (project.path / "hooks/10-hello.sh").write_text("#!/bin/sh\necho hello\n")
    d = livebuild.write_config(project)
    cfg = (d / "auto/config").read_text()
    for opt in ("--distribution trixie", "--architecture amd64", "--bootloaders syslinux,grub-efi",
                "--debian-installer none", "--linux-flavours amd64"):
        assert opt in cfg, opt
    assert subprocess.run(["sh", "-n", str(d / "auto/config")]).returncode == 0
    assert "task-xfce-desktop" in (d / "config/package-lists/05-desktop.list.chroot").read_text()
    hook = (d / "config/hooks/normal/8100-disco-identity.hook.chroot").read_text()
    assert "ID=edukasaun" in hook and "Welcome to Edukasaun OS" in hook
    assert (d / "config/hooks/normal/8000-disco-10-hello.hook.chroot").exists()
    assert livebuild.usable("3.0~a57-1")[0] is False and livebuild.usable("1:20230502")[0]
    project.state["builder"]["platform"] = "rpi-arm64"
    with pytest.raises(ValueError):
        livebuild.config_args(project)


# System files, terminal, browser, document ---------------------------------------------------------------------
def test_sysfiles(project):
    from disco.core import sysfiles
    osr = sysfiles.template(project, "etc/os-release")
    assert 'NAME="Edukasaun OS"' in osr and "ID=edukasaun" in osr and "LOGO=edukasaun-logo" in osr
    assert sysfiles.template(project, "etc/issue").startswith("Welcome to Edukasaun OS 1.0 (Kameli) - \\n \\l")
    sysfiles.write(project, "etc/os-release", osr)
    assert "ID=edukasaun" in (project.rootfs / "usr/lib/os-release").read_text()   # through the link
    assert (project.rootfs / "etc/os-release").is_symlink()
    sysfiles.write(project, "etc/hostname", "lab1\n")
    assert "127.0.1.1\tlab1" in (project.rootfs / "etc/hosts").read_text()
    with pytest.raises(ValueError):
        sysfiles.check("etc/hostname", "Bad Name")
    with pytest.raises(ValueError):
        sysfiles.check("etc/os-release", "NAME=x\nnot a line\n")
    with pytest.raises(ValueError):
        sysfiles.write(project, "etc/shadow", "x")
    # An absolute link must lead into the image, never to this computer.
    (project.rootfs / "etc/motd").symlink_to("/etc/passwd")
    sysfiles.write(project, "etc/motd", "hello")
    assert (project.rootfs / "etc/passwd").read_text() == "hello\n"


def test_skel_import(project, tmp_path):
    from disco.core import sysfiles
    src = tmp_path / "xfce4"
    (src / "xfconf").mkdir(parents=True)
    (src / "xfconf/panel.xml").write_text("<panel/>")
    (src / "sessions").mkdir()
    (src / "sessions/x").write_text("private")
    dest = sysfiles.import_config(project, src)
    assert (dest / "xfconf/panel.xml").exists() and not (dest / "sessions").exists()
    with pytest.raises(ValueError):
        sysfiles.import_config(project, src, "../etc")


def test_motd_and_prompt(project):
    from disco.core import shellbrand
    r = project.rootfs
    shellbrand.set_motd(project, "Hello 'world'", dynamic=True)
    script = (r / shellbrand.MOTD_SCRIPT).read_text()
    assert "Hello world" in script and os.access(r / shellbrand.MOTD_SCRIPT, os.X_OK)
    assert subprocess.run(["sh", "-n", str(r / shellbrand.MOTD_SCRIPT)]).returncode == 0
    shellbrand.set_motd(project, "Static")
    assert (r / "etc/motd").read_text() == "Static\n" and not (r / shellbrand.MOTD_SCRIPT).exists()
    (r / "etc/skel").mkdir(parents=True, exist_ok=True)
    (r / "etc/skel/.bashrc").write_text("PS1='x'\n")
    ps1 = shellbrand.set_prompt(project, "brand")
    assert "(Edukasaun OS)" in ps1
    shellbrand.set_prompt(project, "color")
    text = (r / "etc/skel/.bashrc").read_text()
    assert text.count(shellbrand.BEGIN) == 1 and text.startswith("PS1='x'")
    with pytest.raises(ValueError):
        shellbrand.prompt_text("custom", project, "it's")
    shellbrand.remove_prompt(project)
    assert shellbrand.BEGIN not in (r / "etc/bash.bashrc").read_text()


def test_browser_policies(project):
    from disco.core import browserpolicy as bp
    files = bp.apply(project, "https://edukasaun.org", True, "Debian | https://www.debian.org\nhttps://x.org",
                     search="DuckDuckGo")
    assert "/etc/firefox-esr/policies/policies.json" in files
    ff = json.loads((project.rootfs / "etc/firefox-esr/policies/policies.json").read_text())["policies"]
    assert ff["Homepage"] == {"URL": "https://edukasaun.org", "Locked": True, "StartPage": "homepage"}
    assert ff["Bookmarks"][0] == {"Title": "Debian", "URL": "https://www.debian.org", "Placement": "toolbar"}
    assert ff["DisableTelemetry"] and ff["SearchEngines"] == {"Default": "DuckDuckGo"}
    ch = json.loads((project.rootfs / bp.CHROMIUM_PATH).read_text())
    assert ch["HomepageLocation"] == "https://edukasaun.org" and ch["MetricsReportingEnabled"] is False
    with pytest.raises(ValueError):
        bp.parse_bookmarks("Bad | javascript:alert(1)")
    bp.remove(project)
    assert not (project.rootfs / bp.CHROMIUM_PATH).exists()


def test_desktop_document(project, tmp_path):
    from disco.core import readmedoc
    assert readmedoc.file_name("Tentang Edukasaun: panduan/1") == "Tentang Edukasaun panduan1.pdf"
    html = readmedoc.default_html(project)
    assert "Edukasaun OS" in html
    pdf = readmedoc.make_pdf("Tentang Edukasaun", html, tmp_path / "t.pdf")
    assert pdf.read_bytes()[:5] == b"%PDF-"
    out = readmedoc.install(project, pdf, "Tentang Edukasaun")
    r = project.rootfs
    assert out == r / "usr/share/doc/edukasaun-guide/Tentang Edukasaun.pdf"
    script = r / "usr/share/edukasaun-guide/put-on-desktop"
    assert subprocess.run(["sh", "-n", str(script)]).returncode == 0
    assert "xdg-user-dir DESKTOP" in script.read_text()
    assert (r / "etc/xdg/autostart/edukasaun-guide-desktop.desktop").exists()
    # The script puts it on the desktop once.
    home = tmp_path / "home"
    home.mkdir()
    fake = tmp_path / "doc"
    fake.mkdir()
    shutil.copy2(out, fake / out.name)
    text = script.read_text().replace("/usr/share/doc/edukasaun-guide", str(fake))
    (tmp_path / "put").write_text(text)
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"), PATH="/usr/bin:/bin")
    subprocess.run(["sh", str(tmp_path / "put")], env=env, check=True)
    assert (home / "Desktop/Tentang Edukasaun.pdf").exists()
    (home / "Desktop/Tentang Edukasaun.pdf").unlink()
    subprocess.run(["sh", str(tmp_path / "put")], env=env, check=True)
    assert not (home / "Desktop/Tentang Edukasaun.pdf").exists()     # only once
    readmedoc.remove(project)
    assert not out.exists()


# Fixes of the code review ----------------------------------------------------------------------------------------
def test_grub_menu_keeps_nested_entries():
    from disco.core import grubmenu
    cfg = ('menuentry "Live" {\n linux /live/vmlinuz\n}\nif [ "$grub_platform" = "efi" ]; then\n'
           'menuentry "UEFI" {\n fwsetup\n}\nfi\nmenuentry "Safe" {\n linux /live/vmlinuz nomodeset\n}\n')
    ents = grubmenu.entries(cfg)
    assert [e["title"] for e in ents] == ["Live", "Safe"]
    out = grubmenu.build(cfg, list(reversed(ents)))
    assert out.index('"Safe"') < out.index('"Live"') and "fwsetup" in out and out.count("fi\n") == 1
    if has("grub-script-check"):
        p = Path(os.environ.get("DISCO_LOG_DIR", "/tmp")) / "g.cfg"
        p.write_text(out)
        assert subprocess.run(["grub-script-check", str(p)]).returncode == 0


def test_mksquashfs_exclude_last(project, monkeypatch):
    from disco.core import isobuild, runner
    seen = []

    def fake_run(cmd, **k):
        cmd = [str(c) for c in cmd]
        seen.append(cmd)
        if "mksquashfs" in " ".join(cmd):
            Path(cmd[cmd.index("-noappend") - 1]).write_bytes(b"hsqs")
        return 0
    monkeypatch.setattr(runner, "run", fake_run)
    target = project.isodir / "live/filesystem.squashfs"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x")
    b = isobuild.Builder(project)
    b.squashfs()
    cmd = [c for c in seen if "mksquashfs" in " ".join(c)][0]
    assert cmd[-2:] == ["-e", "boot/efi"] and "-comp" in cmd


def test_runner_cleanup_after_cancel():
    from disco.core import runner
    runner.CANCEL.set()
    try:
        with pytest.raises(runner.Canceled):
            runner.run(["true"])
        assert runner.run(["true"], cancellable=False) == 0
    finally:
        runner.CANCEL.clear()


def test_titles_with_backslash(tmp_path):
    from disco.core import bootloader
    (tmp_path / "boot/grub").mkdir(parents=True)
    (tmp_path / "isolinux").mkdir()
    (tmp_path / "boot/grub/grub.cfg").write_text('menuentry "Live system (amd64)" {\n}\nset timeout=5\n')
    (tmp_path / "isolinux/menu.cfg").write_text("menu title Debian GNU/Linux\ntimeout 50\n")
    bootloader.set_titles(tmp_path, r"Edu\o/")
    bootloader.set_timeout(tmp_path, 0)
    assert 'menuentry "Edu\\o/ Live (amd64)"' in (tmp_path / "boot/grub/grub.cfg").read_text()
    assert "timeout 1\n" in (tmp_path / "isolinux/menu.cfg").read_text()


def test_sources_keep_third_party(trixie):
    from disco.core.apt import Sources
    (trixie / "etc/apt/sources.list").write_text(
        "deb http://deb.debian.org/debian bookworm main\n"
        "deb [arch=amd64] https://dl.google.com/linux/chrome/deb/ stable main\n")
    Sources(trixie).set_debian("stable")
    text = (trixie / "etc/apt/sources.list").read_text()
    assert "dl.google.com" in text and "deb.debian.org" not in text


def test_lsb_release_escaped(project, nochroot):
    from disco.core.branding import Branding
    from disco.core.distro import parse_os_release
    ident = dict(project.state["identity"], name='Edu "$(id)" OS', id="edu")
    Branding(project).apply_identity(ident, protect=False)
    lsb = (project.rootfs / "etc/lsb-release").read_text()
    assert parse_os_release(lsb)["DISTRIB_ID"] == 'Edu "$(id)" OS'
    assert "\\$(id)" in lsb
    assert (project.rootfs / "etc/issue").read_text().startswith("Welcome to Edu")
    assert project.state["identity"]["id"] == "edu"


def test_reserved_branding_id(project):
    from disco.core.distrobrand import BrandingSpec
    with pytest.raises(ValueError, match="base system"):
        BrandingSpec(name="X", os_id="debian", version="1.0").validate()
    with pytest.raises(ValueError, match="package version"):
        BrandingSpec(name="X", os_id="mylinux", version="v1 beta").validate()


def test_snapshot_dist_locks_root(tmp_path):
    from disco.core.snapshot import _lock_root
    r = tmp_path / "r"
    (r / "etc").mkdir(parents=True)
    (r / "etc/shadow").write_text("root:$6$abc:19000:0:99999:7:::\nadmin:$y$xyz:19000::::::\nbin:*:19000::::::\n")
    _lock_root(r)
    lines = (r / "etc/shadow").read_text().splitlines()
    assert lines[0].startswith("root:!:") and lines[1].startswith("admin:*:") and lines[2].startswith("bin:*:")


def test_sysv_script_skips_live(project):
    from disco.core.initsystem import sysv_from_unit
    unit = project.rootfs / "etc/systemd/system/eduka-flatpak-firstboot.service"
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text("[Unit]\nConditionKernelCommandLine=!boot=live\n[Service]\nExecStart=/usr/bin/true\n")
    sysv_from_unit(project, unit)
    script = (project.rootfs / "etc/init.d/eduka-flatpak-firstboot").read_text()
    assert "grep -qw 'boot=live' /proc/cmdline && exit 0" in script


def test_cli_shell_and_run_arguments():
    from disco.cli import NO_ROOT, build_parser
    a = build_parser().parse_args(["run", "apt-get", "update"])
    assert a.command == "run" and a.argv == ["apt-get", "update"]
    assert "about" in NO_ROOT and "platforms" in NO_ROOT


def test_cli_platforms_and_presets(capsys):
    from disco.cli import main
    assert main(["platforms"]) == 0
    assert "rpi-arm64" in capsys.readouterr().out
    assert main(["presets"]) == 0
    assert "Raspberry Pi Lite" in capsys.readouterr().out
