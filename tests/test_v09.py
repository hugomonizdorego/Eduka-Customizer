"""0.9 Beta: boot loaders, opener, clean up keeping the ISO, feedback, merged menus."""

import os

import pytest

from eduka_customizer.core import bootchoice, calamares_check as cc, yamlconf
from tests.test_v016 import cal, nochroot  # noqa: F401 (fixtures)


def _seq(r):
    data = yamlconf.load((r / "etc/calamares/settings.conf").read_text())
    exec_ = [m for st in data["sequence"] if "exec" in st for m in st["exec"]]
    return data, exec_


def _tools(r, *files):
    for f in files:
        (r / f).parent.mkdir(parents=True, exist_ok=True)
        (r / f).write_text("")


def test_efistub_replaces_the_calamares_boot_loader(cal, nochroot):  # noqa: F811
    r = cal.rootfs
    b = bootchoice.BootChoice(cal)
    _tools(r, "usr/bin/efibootmgr")
    b.configure("efistub", {"CMDLINE": "quiet splash mitigations=auto", "LABEL": "My Linux"})
    b.use("efistub")
    data, exec_ = _seq(r)
    assert "bootloader" not in exec_ and exec_.count(bootchoice.STEP) == 1
    assert exec_.index(bootchoice.STEP) == exec_.index("contextualprocess@before_bootloader") + 1
    assert any(i["id"] == bootchoice.INSTANCE and i["module"] == "shellprocess" for i in data["instances"])
    assert len(data["instances"]) == 3  # Debian's two stay
    conf = (r / "etc/calamares/modules" / bootchoice.STEP_CONF).read_text()
    assert "/usr/sbin/distroforge-bootloader install" in conf and "dontChroot: false" in conf
    script = r / bootchoice.SCRIPT
    assert script.exists() and os.access(script, os.X_OK)
    for hook in bootchoice.HOOKS:
        assert os.access(r / hook, os.X_OK)
    text = (r / bootchoice.CONF).read_text()
    assert "LOADER=efistub" in text and "CMDLINE='quiet splash mitigations=auto'" in text
    assert "LABEL='My Linux'" in text and "INSTALLED=0" in text
    res = cc.check(cal)
    assert not [x for x in res if x[0] == "fail"], res
    assert any("efistub is set up by the installer" in x[2] for x in res)
    assert b.current() == "efistub"
    # Back to GRUB: the Calamares module returns where the own step was.
    b.use("grub")
    data, exec_ = _seq(r)
    assert bootchoice.STEP not in exec_ and exec_.index("bootloader") == exec_.index("packages") - 1
    assert not any(i["id"] == bootchoice.INSTANCE for i in data["instances"])
    assert 'efiBootLoader: "grub"' in (r / "etc/calamares/modules/bootloader.conf").read_text() or \
        "efiBootLoader: grub" in (r / "etc/calamares/modules/bootloader.conf").read_text()
    assert (r / "etc/default/grub.d/95-eduka-customizer.cfg").exists()


def test_systemd_boot_adds_its_settings_after_calamares(cal, nochroot):  # noqa: F811
    r = cal.rootfs
    _tools(r, "usr/bin/bootctl", "usr/bin/kernel-install")
    b = bootchoice.BootChoice(cal)
    b.configure("systemd-boot", {"TIMEOUT": 2, "SDBOOT_EDITOR": False, "SDBOOT_DEFAULT": "saved",
                                 "SDBOOT_CONSOLE": "max", "CMDLINE": "quiet"})
    b.use("systemd-boot")
    _data, exec_ = _seq(r)
    assert exec_[exec_.index("bootloader") + 1] == bootchoice.STEP
    bl = yamlconf.load((r / "etc/calamares/modules/bootloader.conf").read_text())
    assert bl["efiBootLoader"] == "systemd-boot" and bl["timeout"] == "2" and bl["kernelParams"] == ["quiet"]
    text = (r / bootchoice.CONF).read_text()
    assert "SDBOOT_DEFAULT=saved" in text and "SDBOOT_EDITOR=no" in text and "TIMEOUT=2" in text
    # Using it again does not add the step twice.
    b.use("systemd-boot")
    assert _seq(r)[1].count(bootchoice.STEP) == 1


def test_syslinux_and_checks(cal, nochroot):  # noqa: F811
    r = cal.rootfs
    b = bootchoice.BootChoice(cal)
    with pytest.raises(RuntimeError):
        b.use("syslinux")  # extlinux was not really installed
    _tools(r, "usr/bin/extlinux", "usr/lib/syslinux/mbr/mbr.bin")
    b.use("syslinux")
    assert any(x[2].endswith("is set up by the installer") for x in cc.check(cal))
    (r / "usr/bin/extlinux").unlink()
    fails = [x for x in cc.check(cal) if x[0] == "fail"]
    assert any("syslinux needs /usr/bin/extlinux" in x[2] for x in fails)
    (r / bootchoice.CONF).unlink()
    fails = [x for x in cc.check(cal) if x[0] == "fail"]
    assert any("choose the boot loader again" in x[2] for x in fails)
    from eduka_customizer.core import fixes
    label, _f = fixes.find("/etc/distroforge-bootloader.conf: missing: choose the boot loader again")
    assert "boot loader" in label.lower()


def test_settings_are_checked():
    with pytest.raises(ValueError):
        bootchoice.validate("efistub", {"CMDLINE": "quiet; rm -rf /"})
    with pytest.raises(ValueError):
        bootchoice.validate("efistub", {"CMDLINE": "root=/dev/sda1 quiet"})
    with pytest.raises(ValueError):
        bootchoice.validate("syslinux", {"TIMEOUT": "soon"})
    with pytest.raises(ValueError):
        bootchoice.validate("syslinux", {"SYSLINUX_TITLE": 'My "Linux"'})
    with pytest.raises(ValueError):
        bootchoice.validate("refind", {"REFIND_RESOLUTION": "huge"})
    with pytest.raises(ValueError):
        bootchoice.validate("systemd-boot", {"SDBOOT_CONSOLE": "tiny"})
    v = bootchoice.validate("refind", {"REFIND_RESOLUTION": "1920 1080", "TIMEOUT": "7", "REFIND_TEXTONLY": "yes"})
    assert v["TIMEOUT"] == 7 and v["REFIND_TEXTONLY"] is True and v["CMDLINE"] == "quiet splash"
    assert {x.id for x in bootchoice.LOADERS} == {"grub", "grub-secureboot", "systemd-boot", "refind", "efistub",
                                                  "syslinux"}


def test_remove_never_takes_the_chosen_loader_or_other_packages(cal, nochroot, monkeypatch):  # noqa: F811
    from eduka_customizer.core import apt, chroot
    b = bootchoice.BootChoice(cal)
    with pytest.raises(ValueError):
        b.remove("grub")
    monkeypatch.setattr(apt.Packages, "is_installed", lambda self, n: n in ("extlinux",))
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "Purg extlinux\nPurg calamares-settings-x\n")
    with pytest.raises(RuntimeError):
        b.remove("syslinux")
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "Purg extlinux\n")
    assert b.remove("syslinux") == ["extlinux"]
    assert ["remove", "extlinux"] in nochroot


def test_grub_settings_go_to_the_grub_drop_in(cal, nochroot):  # noqa: F811
    b = bootchoice.BootChoice(cal)
    b.configure("grub", {"TIMEOUT": 3, "CMDLINE": "quiet", "GRUB_TIMEOUT_STYLE": "hidden", "GRUB_DEFAULT": "saved",
                         "GRUB_OS_PROBER": True, "GRUB_RECOVERY": False, "GRUB_GFXMODE": "1920x1080"})
    text = (cal.rootfs / "etc/default/grub.d/95-eduka-customizer.cfg").read_text()
    for line in ('GRUB_TIMEOUT="3"', 'GRUB_TIMEOUT_STYLE="hidden"', 'GRUB_DEFAULT="saved"', 'GRUB_SAVEDEFAULT="true"',
                 'GRUB_DISABLE_OS_PROBER="false"', 'GRUB_DISABLE_RECOVERY="true"', 'GRUB_GFXMODE="1920x1080"'):
        assert line in text
    assert bootchoice.BootChoice(cal).settings("grub-secureboot")["TIMEOUT"] == 3


def test_setup_script_is_valid_shell():
    import subprocess
    from eduka_customizer.core.config import data_file
    script = data_file("bootloader", "distroforge-bootloader")
    assert subprocess.run(["sh", "-n", str(script)]).returncode == 0
    out = subprocess.run(["sh", str(script), "nothing"], capture_output=True, text=True)
    assert out.returncode == 2 and "Usage" in out.stderr


def test_opener_finds_runuser_outside_path(monkeypatch, tmp_path):
    from eduka_customizer.gui import opener
    sbin = tmp_path / "sbin"
    sbin.mkdir()
    (sbin / "runuser").write_text("#!/bin/sh\n")
    (sbin / "runuser").chmod(0o755)
    monkeypatch.setenv("PATH", "/nonexistent")
    monkeypatch.setattr(opener, "SEARCH_PATH", str(sbin))
    cmd = opener.user_command("alice", ["/usr/bin/xdg-open", "https://example.org"])
    assert cmd[0] == str(sbin / "runuser") and cmd[1:4] == ["-u", "alice", "--"]
    monkeypatch.setattr(opener, "SEARCH_PATH", "/nonexistent")
    assert opener.user_command("alice", ["x"]) is None or opener.user_command("alice", ["x"])[0].endswith("sudo")


def test_keep_only_iso(tmp_path, monkeypatch):
    from eduka_customizer.core import chroot, projectfiles
    from eduka_customizer.core.project import Project
    p = Project.create(tmp_path / "proj")
    assert (p.path / "README.txt").read_text().startswith("This is a DistroForge project folder")
    (p.rootfs / "etc").mkdir(parents=True)
    (p.rootfs / "etc/hostname").write_text("x\n")
    (p.path / "hooks").mkdir()
    (p.path / "notes.txt").write_text("mine")
    with pytest.raises(RuntimeError):
        projectfiles.keep_only_iso(p)  # no ISO yet: nothing is deleted
    assert (p.rootfs / "etc/hostname").exists()
    (p.output / "my-1.0.iso").write_bytes(b"iso")
    (p.output / "my-1.0.iso.sha256").write_text("abc  my-1.0.iso\n")
    monkeypatch.setattr(chroot.Chroot, "force_release", lambda self: None)
    monkeypatch.setattr(chroot, "mounts_under", lambda path: ["/x/rootfs/proc"])
    monkeypatch.setattr(chroot, "unmount_all", lambda path: None)
    with pytest.raises(RuntimeError):
        projectfiles.keep_only_iso(p)  # still mounted: nothing is deleted
    assert (p.rootfs / "etc/hostname").exists() and (p.output / "my-1.0.iso").exists()
    monkeypatch.setattr(chroot, "mounts_under", lambda path: [])
    isos, own = projectfiles.keep_only_iso(p)
    assert sorted(x.name for x in p.path.iterdir()) == ["my-1.0.iso", "my-1.0.iso.sha256", "notes.txt"]
    assert own == ["notes.txt"] and [x.name for x in isos] == ["my-1.0.iso", "my-1.0.iso.sha256"]
    with pytest.raises(RuntimeError):
        projectfiles.keep_only_iso(p)  # not a project folder any more
