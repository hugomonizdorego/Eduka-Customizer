"""Boot loaders of installed systems: install them into the image, remove them,
choose the one the installer puts on computers, and set each one up.

Five maintained boot loaders, all packaged by Debian:

  GRUB 2               BIOS and UEFI (also Secure Boot through shim); Calamares installs it.
  systemd-boot         UEFI; Calamares installs it, DistroForge adds its settings.
  rEFInd               UEFI, graphical; Calamares 3.3 installs it, DistroForge adds its settings.
  EFISTUB              UEFI; the firmware starts the kernel directly. Calamares has no module for
                       it, so DistroForge's own installer step does it.
  Syslinux/EXTLINUX    BIOS; also DistroForge's own installer step.

The installer step is a Calamares shellprocess instance (shellprocess@distroforge-bootloader)
that runs /usr/sbin/distroforge-bootloader in the new system. That script also keeps EFISTUB
and Syslinux working after kernel updates (kernel and initramfs hooks). When a boot loader
cannot work on a computer (Syslinux on UEFI, EFISTUB on BIOS, an encrypted /boot) the next
one that works is used, GRUB last, so the installation does not stop with an error.
"""

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from eduka_customizer.core import calamares_check
from eduka_customizer.core.log import log

SCRIPT = "usr/sbin/distroforge-bootloader"
CONF = "etc/distroforge-bootloader.conf"
HOOKS = {"etc/kernel/postinst.d/zz-distroforge-bootloader": "kernel",
         "etc/kernel/postrm.d/zz-distroforge-bootloader": "kernel",
         "etc/initramfs/post-update.d/zz-distroforge-bootloader": "initramfs"}
INSTANCE = "distroforge-bootloader"
STEP = "shellprocess@" + INSTANCE
STEP_CONF = "shellprocess-{}.conf".format(INSTANCE)
CMDLINE = re.compile(r"^[A-Za-z0-9_.,:=/@+\- ]*$")
TEXT = re.compile(r"^[^\"'`$\\\n]*$")
RESOLUTION = re.compile(r"^(|max|\d{3,4} \d{3,4}|\d{3,4}x\d{3,4})$")


@dataclass
class Loader:
    id: str
    name: str
    firmware: str
    description: str
    calamares: str            # efiBootLoader of Calamares' bootloader module, or "" for the own step
    packages: list
    files: list               # what must be in the image once it is installed
    remove: list = field(default_factory=list)   # what "Remove from the image" purges
    minimum: tuple = (3, 2)   # Calamares version
    fields: list = field(default_factory=list)   # (key, label, kind, default, choices)


COMMON = [("TIMEOUT", "Timeout (seconds)", "int", 5, None),
          ("CMDLINE", "Kernel options", "text", "quiet splash", None)]

LOADERS = [
    Loader("grub", "GRUB 2", "BIOS and UEFI",
           "Debian's standard boot loader and the most complete one: BIOS and UEFI, menus, themes, other "
           "operating systems (os-prober), recovery entries. Recommended.",
           "grub", ["grub2-common", "grub-pc-bin", "grub-efi-amd64-bin", "efibootmgr"],
           ["usr/sbin/grub-install"],
           ["grub-efi-amd64", "grub-efi-amd64-bin", "grub-efi-amd64-signed", "grub-pc", "grub-pc-bin",
            "shim-signed", "grub2-common"],
           fields=COMMON + [
               ("GRUB_TIMEOUT_STYLE", "Menu", "choice", "menu",
                [("menu", "Show the menu"), ("countdown", "Countdown"), ("hidden", "Hidden (Shift/Esc shows it)")]),
               ("GRUB_DEFAULT", "Default entry", "choice", "0", [("0", "First entry"), ("saved", "Last chosen entry")]),
               ("GRUB_OS_PROBER", "Find other systems (Windows, other Linux) for the menu", "bool", True, None),
               ("GRUB_RECOVERY", "Show recovery entries", "bool", True, None),
               ("GRUB_GFXMODE", "Resolution (auto, 1024x768, 1920x1080, ...)", "text", "", None)]),
    Loader("grub-secureboot", "GRUB 2 with Secure Boot", "BIOS and UEFI (Secure Boot on)",
           "GRUB signed by Debian, started by shim: computers with Secure Boot switched on start it. Same "
           "settings as GRUB 2.",
           "sb-shim", ["grub2-common", "grub-pc-bin", "grub-efi-amd64-bin", "grub-efi-amd64-signed",
                       "shim-signed", "efibootmgr"],
           ["usr/sbin/grub-install", "usr/lib/shim/shimx64.efi.signed"],
           ["grub-efi-amd64-signed", "shim-signed"], fields=[]),
    Loader("systemd-boot", "systemd-boot", "UEFI",
           "Small and fast boot manager from systemd, simple text files. UEFI only: BIOS computers get GRUB.",
           "systemd-boot", ["systemd-boot", "efibootmgr"], ["usr/bin/bootctl", "usr/bin/kernel-install"],
           ["systemd-boot", "systemd-boot-efi"],
           fields=COMMON + [
               ("SDBOOT_DEFAULT", "Default entry", "choice", "newest",
                [("newest", "Newest kernel"), ("saved", "Last chosen entry")]),
               ("SDBOOT_EDITOR", "Allow changing kernel options at boot (e key)", "bool", False, None),
               ("SDBOOT_CONSOLE", "Screen mode", "choice", "keep",
                [("keep", "Firmware default"), ("auto", "Automatic"), ("max", "Highest resolution")])]),
    Loader("refind", "rEFInd", "UEFI",
           "Graphical boot manager that finds every operating system by itself, good for several systems on "
           "one computer. UEFI only: BIOS computers get GRUB. Needs Calamares 3.3.",
           "refind", ["refind", "efibootmgr"], ["usr/sbin/refind-install"], ["refind"], minimum=(3, 3),
           fields=COMMON + [
               ("REFIND_RESOLUTION", "Resolution (max, or width height such as 1920 1080)", "text", "", None),
               ("REFIND_TEXTONLY", "Text mode instead of icons", "bool", False, None),
               ("REFIND_HIDE_TOOLS", "Hide the tools row (shell, firmware settings, ...)", "bool", False, None)]),
    Loader("efistub", "EFISTUB", "UEFI (Secure Boot off)",
           "No boot loader at all: the UEFI firmware starts the Linux kernel directly, the fastest start. "
           "Kernel updates are copied to the EFI partition by themselves. Secure Boot must be off. BIOS "
           "computers get Syslinux (if installed) or GRUB.",
           "", ["efibootmgr"], ["usr/bin/efibootmgr"], [],
           fields=[("CMDLINE", "Kernel options", "text", "quiet splash", None),
                   ("LABEL", "Name in the firmware boot menu (empty: the distribution name)", "text", "", None)]),
    Loader("syslinux", "Syslinux / EXTLINUX", "BIOS",
           "The small classic boot loader for BIOS computers (/boot must be ext2/3/4, not encrypted). UEFI "
           "computers get EFISTUB; otherwise GRUB is used.",
           "", ["extlinux", "syslinux-common", "fdisk", "efibootmgr"], ["usr/bin/extlinux", "usr/lib/syslinux/mbr/mbr.bin"],
           ["extlinux"],
           fields=COMMON + [("SYSLINUX_TITLE", "Menu title (empty: the distribution name)", "text", "", None),
                            ("SYSLINUX_GRAPHICAL", "Graphical menu (vesamenu)", "bool", True, None)]),
]
BY_ID = {x.id: x for x in LOADERS}
NOT_AVAILABLE = [
    ("lilo", "LILO", "Development stopped in 2015; no UEFI and no modern file systems. Not in Debian any more."),
    ("burg", "BURG", "A GRUB fork that is no longer developed (since 2012) and is not packaged by Debian."),
]
PRESEED = {"refind": "refind refind/install_to_esp boolean false\n"}
HOOK_TEXT = """#!/bin/sh
# Keeps the boot loader chosen in DistroForge up to date ({0} hook).
[ -x /usr/sbin/distroforge-bootloader ] || exit 0
exec /usr/sbin/distroforge-bootloader update
"""


def loader(loader_id):
    if loader_id not in BY_ID:
        raise KeyError("Unknown boot loader: {} (use {})".format(loader_id, ", ".join(BY_ID)))
    return BY_ID[loader_id]


def validate(loader_id, values):
    """Clean values of *loader_id*'s settings; ValueError for bad ones."""
    out = {}
    for key, label, kind, default, choices in loader(loader_id).fields:
        v = values.get(key, default)
        if kind == "int":
            try:
                v = int(v)
            except (TypeError, ValueError):
                raise ValueError("{}: a number is needed".format(label))
            if not 0 <= v <= 300:
                raise ValueError("{}: 0 to 300 seconds".format(label))
        elif kind == "bool":
            v = v in (True, "yes", "true", "1", 1, "on")
        elif kind == "choice":
            if v not in [c for c, _t in choices]:
                raise ValueError("{}: use {}".format(label, ", ".join(c for c, _t in choices)))
        else:
            v = " ".join(str(v or "").split())
            if key == "CMDLINE" and not CMDLINE.match(v):
                raise ValueError("Kernel options may only have letters, digits, spaces and _ . , : = / @ + -")
            if key == "REFIND_RESOLUTION" and not RESOLUTION.match(v):
                raise ValueError("Resolution: max, or width and height such as 1920 1080")
            if key == "CMDLINE" and re.search(r"(^| )(root|initrd)=", v):
                raise ValueError("root= and initrd= are set by the installer; leave them out")
            if not TEXT.match(v):
                raise ValueError("{}: quotes, $, ` and \\ are not allowed".format(label))
        out[key] = v
    return out


class BootChoice:
    def __init__(self, project):
        self.project = project
        self.rootfs = Path(project.rootfs)

    # State ------------------------------------------------------------------------------
    def calamares_version(self):
        return calamares_check._version(self.rootfs)

    def _boot(self):
        return self.project.state.setdefault("boot", {})

    def in_image(self, loader_id):
        return all((self.rootfs / f).exists() for f in loader(loader_id).files)

    def usable(self, loader_id):
        """(usable, reason) for the installer of this image."""
        lo = loader(loader_id)
        version = self.calamares_version()
        if lo.calamares and version and version < lo.minimum:
            return False, "needs Calamares {}.{} (the image has {}.{})".format(lo.minimum[0], lo.minimum[1],
                                                                              version[0], version[1])
        return True, ""

    def options(self):
        """[(id, name, firmware, description, usable, reason, in_image)] for the GUI and CLI."""
        out = []
        for lo in LOADERS:
            ok, why = self.usable(lo.id)
            out.append((lo.id, lo.name, lo.firmware, lo.description, ok, why, self.in_image(lo.id)))
        for lid, name, why in NOT_AVAILABLE:
            out.append((lid, name, "", why, False, why, False))
        return out

    def current(self):
        chosen = self._boot().get("installed_loader")
        if chosen in BY_ID:
            return chosen
        p = self.rootfs / "etc/calamares/modules/bootloader.conf"
        if p.exists():
            m = re.search(r'(?m)^efiBootLoader:\s*"?([a-z-]+)"?', p.read_text(errors="replace"))
            if m:
                return {"grub": "grub", "sb-shim": "grub-secureboot", "systemd-boot": "systemd-boot",
                        "refind": "refind"}.get(m.group(1), "grub")
        return "grub"

    def settings(self, loader_id):
        """The settings of *loader_id* (saved ones, or the defaults)."""
        lid = "grub" if loader_id == "grub-secureboot" else loader_id
        saved = self._boot().get("loaders", {}).get(lid, {})
        values = {key: default for key, _l, _k, default, _c in loader(lid).fields}
        if lid == "grub" and not saved:
            values.update(self._grub_from_image())
        values.update({k: v for k, v in saved.items() if k in values})
        return values

    def _grub_from_image(self):
        from eduka_customizer.core.kernel import Kernels
        g = Kernels(self.project).grub_defaults()
        out = {}
        if g.get("GRUB_TIMEOUT", "").lstrip("-").isdigit():
            out["TIMEOUT"] = max(0, int(g["GRUB_TIMEOUT"]))
        if "GRUB_CMDLINE_LINUX_DEFAULT" in g:
            out["CMDLINE"] = g["GRUB_CMDLINE_LINUX_DEFAULT"]
        if g.get("GRUB_TIMEOUT_STYLE") in ("menu", "countdown", "hidden"):
            out["GRUB_TIMEOUT_STYLE"] = g["GRUB_TIMEOUT_STYLE"]
        if g.get("GRUB_DEFAULT") in ("0", "saved"):
            out["GRUB_DEFAULT"] = g["GRUB_DEFAULT"]
        if "GRUB_DISABLE_OS_PROBER" in g:
            out["GRUB_OS_PROBER"] = g["GRUB_DISABLE_OS_PROBER"] == "false"
        if "GRUB_DISABLE_RECOVERY" in g:
            out["GRUB_RECOVERY"] = g["GRUB_DISABLE_RECOVERY"] != "true"
        out["GRUB_GFXMODE"] = g.get("GRUB_GFXMODE", "")
        return out

    # Install / remove in the image ------------------------------------------------------------
    def install(self, loader_id):
        """Install the packages of *loader_id* into the image (and the setup script)."""
        lo = loader(loader_id)
        from eduka_customizer.core.apt import Packages
        pk = Packages(self.project)
        with pk.chroot:
            if lo.id in PRESEED:
                pk.chroot.run(["debconf-set-selections"], input=PRESEED[lo.id], check=False)
            missing = [p for p in lo.packages if not pk.is_installed(p)]
            if missing:
                pk.update()
                have = pk.available(missing)
                lacking = [p for p in missing if p not in have]
                if lacking:
                    raise RuntimeError("{} is not available from the repositories of the image: {}".format(
                        lo.name, " ".join(lacking)))
                pk.install(missing, update=False)
        absent = [f for f in lo.files if not (self.rootfs / f).exists()]
        if absent:
            raise RuntimeError("{} is installed but /{} is missing".format(lo.name, absent[0]))
        self.write_script()
        self.project.record("boot-loader-install", lo.id)
        log.info("%s is installed in the image", lo.name)

    def remove(self, loader_id):
        """Remove the packages of *loader_id* from the image (never the chosen one)."""
        lo = loader(loader_id)
        if loader_id == self.current() or (loader_id == "grub" and self.current() == "grub-secureboot"):
            raise ValueError("{} is the boot loader of installed systems: choose another one first".format(lo.name))
        if loader_id in ("grub", "grub-secureboot") and self.current() in ("systemd-boot", "refind", "efistub"):
            log.warning("Without GRUB, BIOS computers can only be installed with Syslinux")
        from eduka_customizer.core.apt import Packages
        pk = Packages(self.project)
        names = [p for p in lo.remove if pk.is_installed(p)]
        if not names:
            log.info("%s is not installed in the image", lo.name)
            return []
        with pk.chroot:
            sim = pk.chroot.output(["apt-get", "-s", "purge"] + names, check=False) or ""
            gone = set(re.findall(r"(?m)^(?:Remv|Purg) (\S+)", sim))
            related = re.compile(r"^(grub|shim|systemd-boot|refind|extlinux|syslinux|efibootmgr|os-prober|mokutil)")
            others = sorted(p for p in gone - set(names) if not related.match(p))
            if others:
                raise RuntimeError("Removing {} would also remove {}: it stays installed".format(
                    lo.name, ", ".join(others[:8])))
            pk.remove(names, autoremove=False)
        self.project.record("boot-loader-remove", lo.id)
        return names

    # The installer --------------------------------------------------------------------------
    def write_script(self):
        from eduka_customizer.core.config import data_file
        src = data_file("bootloader", "distroforge-bootloader")
        dest = self.rootfs / SCRIPT
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(src.read_text())
        dest.chmod(0o755)
        for rel, kind in HOOKS.items():
            p = self.rootfs / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(HOOK_TEXT.format(kind))
            p.chmod(0o755)

    def write_conf(self, loader_id):
        lid = "grub" if loader_id == "grub-secureboot" else loader_id
        values = self.settings(lid)
        lines = ["# Written by DistroForge: the boot loader the installer sets up.",
                 "# Used by /usr/sbin/distroforge-bootloader (installer step and kernel hooks).",
                 "LOADER={}".format(loader_id)]
        efi_id = self._efi_id()
        if efi_id:
            lines.append("EFI_ID={}".format(shlex.quote(efi_id)))
        for key, value in values.items():
            if isinstance(value, bool):
                value = "yes" if value else "no"
            lines.append("{}={}".format(key, shlex.quote(str(value))))
        lines += ["INSTALLED=0", "ACTIVE="]
        p = self.rootfs / CONF
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n")

    def _efi_id(self):
        try:
            from eduka_customizer.core.calamares import Calamares
            v = str(Calamares(self.project).read("bootloader").get("efiBootloaderId") or "")
            return v if re.match(r"^[A-Za-z0-9_.-]+$", v) else ""
        except (OSError, ValueError):
            return ""

    def wire_calamares(self, loader_id):
        """Point the installer at *loader_id*. Returns False when Calamares is not in the image."""
        from eduka_customizer.core.calamares import Calamares
        lo = loader(loader_id)
        cal = Calamares(self.project)
        if not cal.installed() or not cal.settings_path().exists():
            return False
        settings = cal.read("settings")
        own = not lo.calamares
        extra = lo.id in ("systemd-boot", "refind")
        seq, placed = [], False
        for step in settings.get("sequence") or []:
            if isinstance(step, dict) and "exec" in step:
                new = []
                for m in step.get("exec") or []:
                    if m in ("bootloader", STEP):
                        if not placed:
                            new += [STEP] if own else (["bootloader", STEP] if extra else ["bootloader"])
                            placed = True
                        continue
                    new.append(m)
                step = dict(step, exec=new)
            seq.append(step)
        if not placed:
            raise RuntimeError("The installer's sequence has no boot loader step: add 'bootloader' to "
                               "settings.conf (Installer page) first")
        instances = [i for i in settings.get("instances") or []
                     if not (isinstance(i, dict) and i.get("id") == INSTANCE)]
        if own or extra:
            instances.append({"id": INSTANCE, "module": "shellprocess", "config": STEP_CONF})
            conf = cal.etc / "modules" / STEP_CONF
            conf.parent.mkdir(parents=True, exist_ok=True)
            conf.write_text("---\n# Written by DistroForge: installs and sets up the boot loader ({}).\n"
                            "dontChroot: false\ntimeout: 900\nscript:\n"
                            "    - command: \"/{} install\"\n      timeout: 900\n"
                            "i18n:\n    name: \"Install the boot loader\"\n".format(lo.name, SCRIPT))
        cal.write("settings", {"instances": instances or None, "sequence": seq})
        if lo.calamares:
            values = {"efiBootLoader": lo.calamares}
            s = self.settings(lo.id if lo.id != "grub-secureboot" else "grub")
            if "TIMEOUT" in s:
                values["timeout"] = str(s["TIMEOUT"])
            version = self.calamares_version()
            if lo.id in ("systemd-boot", "refind") and (version is None or version >= (3, 3)):
                values["kernelParams"] = s.get("CMDLINE", "quiet splash").split() or None
            cal.write("bootloader", values)
        return True

    def use(self, loader_id, timeout=None):
        """Install *loader_id* into the image when needed and make the installer use it."""
        lo = loader(loader_id)
        ok, why = self.usable(loader_id)
        if not ok:
            raise ValueError("{} {}".format(lo.name, why))
        if timeout not in (None, ""):
            self.configure(loader_id, dict(self.settings(loader_id), TIMEOUT=timeout), write=False)
        if not self.in_image(loader_id):
            self.install(loader_id)
        self._boot()["installed_loader"] = loader_id
        self.project.save()
        self.write_script()
        self.write_conf(loader_id)
        if lo.id in ("grub", "grub-secureboot"):
            self._write_grub()
        if not self.wire_calamares(loader_id):
            log.warning("Calamares is not installed: the choice is stored and used when it is")
        self.project.record("installed-boot-loader", loader_id)
        log.info("Boot loader of installed systems: %s", lo.name)

    apply = use  # older name, used by recipes

    def configure(self, loader_id, values, write=True):
        """Save the settings of *loader_id* (written into the image when it is the chosen one)."""
        lid = "grub" if loader_id == "grub-secureboot" else loader_id
        clean = validate(lid, values)
        self._boot().setdefault("loaders", {})[lid] = clean
        self.project.save()
        if write:
            if lid == "grub":
                self._write_grub()
            cur = self.current()
            if cur == loader_id or (lid == "grub" and cur == "grub-secureboot"):
                self.write_conf(cur)
                self.wire_calamares(cur)
        self.project.record("boot-loader-settings", lid)
        return clean

    def _write_grub(self):
        from eduka_customizer.core.kernel import Kernels
        s = self.settings("grub")
        values = {"GRUB_TIMEOUT": str(s["TIMEOUT"]), "GRUB_TIMEOUT_STYLE": s["GRUB_TIMEOUT_STYLE"],
                  "GRUB_DEFAULT": s["GRUB_DEFAULT"], "GRUB_CMDLINE_LINUX_DEFAULT": s["CMDLINE"],
                  "GRUB_DISABLE_OS_PROBER": "false" if s["GRUB_OS_PROBER"] else "true",
                  "GRUB_DISABLE_RECOVERY": "false" if s["GRUB_RECOVERY"] else "true",
                  "GRUB_GFXMODE": s["GRUB_GFXMODE"]}
        if s["GRUB_DEFAULT"] == "saved":
            values["GRUB_SAVEDEFAULT"] = "true"
        Kernels(self.project).set_grub_defaults(values)

    def check(self):
        """[(level, text)] about the chosen boot loader, for the page and the checks."""
        out = []
        cur = self.current()
        lo = loader(cur)
        if not self.in_image(cur):
            out.append(("warn", "{} is chosen but not installed in the image: press 'Use for installed "
                                "systems' again".format(lo.name)))
        if cur not in ("grub", "grub-secureboot") and not (self.rootfs / SCRIPT).exists():
            out.append(("fail", "/{} is missing: choose {} again".format(SCRIPT, lo.name)))
        if cur not in ("grub", "grub-secureboot", "syslinux") and not self.in_image("syslinux") \
                and not (self.rootfs / "usr/sbin/grub-install").exists() \
                and not calamares_check.grub_at_install(self.rootfs, getattr(self.project, "isodir", None)):
            out.append(("warn", "{} works on UEFI computers only and neither GRUB nor Syslinux is in the image: "
                                "BIOS computers cannot be installed".format(lo.name)))
        if cur in ("efistub", "syslinux") and not (self.rootfs / "usr/bin/efibootmgr").exists():
            out.append(("warn", "efibootmgr is not installed: UEFI boot entries cannot be written"))
        return out or [("ok", "{} for installed systems".format(lo.name))]
