"""Boot menus of the live image (GRUB for UEFI, ISOLINUX for BIOS)."""

import re
import shutil
import uuid
from pathlib import Path

from eduka_customizer.core import runner
from eduka_customizer.core.log import log

ISOLINUX_BIN = ["/usr/lib/ISOLINUX/isolinux.bin", "/usr/lib/syslinux/isolinux.bin"]
ISOHDPFX = ["/usr/lib/ISOLINUX/isohdpfx.bin", "/usr/lib/syslinux/isohdpfx.bin"]
SYSLINUX_MODULES = ["/usr/lib/syslinux/modules/bios", "/usr/lib/syslinux"]
BIOS_MODULES = ["ldlinux.c32", "vesamenu.c32", "libcom32.c32", "libutil.c32", "menu.c32"]
SHIM = ["/usr/lib/shim/shimx64.efi.signed", "/usr/lib/shim/shimx64.efi"]
SIGNED_GRUB_CD = ["/usr/lib/grub/x86_64-efi-signed/gcdx64.efi.signed"]
MOK = ["/usr/lib/shim/mmx64.efi.signed", "/usr/lib/shim/mmx64.efi"]
FONT = ["/usr/share/grub/unicode.pf2"]


def first(paths):
    for p in paths:
        if Path(p).exists():
            return Path(p)
    return None


def config_files(isodir):
    isodir = Path(isodir)
    files = []
    for d in ("boot/grub", "isolinux", "syslinux", "EFI/boot", "boot/isolinux"):
        base = isodir / d
        if base.is_dir():
            files += sorted(p for p in base.rglob("*.cfg") if p.is_file())
    return files


# --------------------------------------------------------------------------
# Editing existing configuration (remaster mode)

def normalize_kernel_paths(isodir):
    """Point every live boot entry at /live/vmlinuz and /live/initrd.img."""
    for f in config_files(isodir):
        text = f.read_text(errors="replace")
        new = re.sub(r"/live/vmlinuz[^\s,]*", "/live/vmlinuz", text)
        new = re.sub(r"/live/initrd[^\s,]*", "/live/initrd.img", new)
        if new != text:
            f.write_text(new)
            log.debug("Updated kernel paths in %s", f)


def _strip_grub_blocks(text, needle):
    """Remove menuentry/submenu blocks whose body contains *needle*."""
    out, i, n = [], 0, len(text)
    pattern = re.compile(r"(?m)^[ \t]*(menuentry|submenu)\b[^\n{]*\{")
    while i < n:
        m = pattern.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        depth, j = 1, m.end()
        while j < n and depth:
            if text[j] == "{":
                depth += 1
            elif text[j] == "}":
                depth -= 1
            j += 1
        block = text[m.start():j]
        if needle in block and m.group(1) == "menuentry":
            pass  # drop it
        elif needle in block:
            # Recurse into submenus so unrelated entries stay.
            head_end = block.index("{") + 1
            inner = _strip_grub_blocks(block[head_end:-1], needle)
            if re.search(r"(?m)^\s*menuentry\b", inner):
                out.append(block[:head_end] + inner + "}")
        else:
            out.append(block)
        i = j
    return "".join(out)


def _strip_isolinux_labels(text, needle):
    blocks = re.split(r"(?im)^(?=\s*label\s)", text)
    kept = [b for b in blocks if not (re.match(r"(?i)\s*label\s", b) and needle in b)]
    return "".join(kept)


def remove_installer_entries(isodir):
    """Drop Debian-Installer entries: they would install plain Debian, not our image."""
    removed = 0
    for f in config_files(isodir):
        text = f.read_text(errors="replace")
        if "/install" not in text and "/d-i/" not in text:
            continue
        new = text
        for needle in ("/install.amd/", "/install/", "/d-i/"):
            if f.parent.name in ("isolinux", "syslinux"):
                new = _strip_isolinux_labels(new, needle)
            else:
                new = _strip_grub_blocks(new, needle)
        if new != text:
            f.write_text(new)
            removed += 1
    for f in Path(isodir).joinpath("isolinux").glob("*.cfg"):
        # Includes of installer menus that may now be empty.
        text = f.read_text(errors="replace")
        new = re.sub(r"(?im)^\s*include\s+(install|stdmenu-install|txt-install|gtk-install)\S*\.cfg\s*$\n?", "", text)
        if new != text:
            f.write_text(new)
    return removed


def append_params(isodir, params):
    """Add kernel parameters to every live boot entry (idempotent)."""
    params = params.split() if isinstance(params, str) else list(params)
    if not params:
        return
    keys = {p.split("=")[0] for p in params}

    def merge(line):
        tokens = line.split()
        tokens = [t for t in tokens if t.split("=")[0] not in keys or t in params]
        for p in params:
            if p not in tokens:
                tokens.append(p)
        return tokens

    for f in config_files(isodir):
        text = f.read_text(errors="replace")
        lines = text.split("\n")
        changed = False
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if "boot=live" not in stripped:
                continue
            if stripped.startswith(("linux ", "linuxefi ", "append ", "APPEND ")):
                indent = line[:len(line) - len(line.lstrip())]
                head, *rest = stripped.split(None, 1)
                rest = rest[0] if rest else ""
                if head.lower() == "append":
                    new = indent + head + " " + " ".join(merge(rest))
                else:
                    kernel, *args = rest.split(None, 1)
                    new = indent + head + " " + kernel + " " + " ".join(merge(args[0] if args else ""))
                if new != line:
                    lines[idx] = new
                    changed = True
        if changed:
            f.write_text("\n".join(lines))


def remove_params(isodir, params):
    params = set(params.split() if isinstance(params, str) else params)
    for f in config_files(isodir):
        text = f.read_text(errors="replace")
        lines = text.split("\n")
        for idx, line in enumerate(lines):
            if "boot=live" in line:
                tokens = line.split(" ")
                lines[idx] = " ".join(t for t in tokens if t not in params)
        new = "\n".join(lines)
        if new != text:
            f.write_text(new)


def set_titles(isodir, name):
    """Replace Debian branding in boot menu titles."""
    for f in config_files(isodir):
        text = f.read_text(errors="replace")

        def fix(m):
            s = m.group(0)
            s = s.replace("Debian GNU/Linux", name).replace("Debian Live", name + " Live")
            s = re.sub(r"\bLive system\b", name + " Live", s)
            return s
        new = re.sub(r"(?im)^\s*(menuentry|submenu)\s+(['\"]).*?\2", fix, text)
        new = re.sub(r"(?im)^\s*menu\s+(label|title)\s.*$", fix, new)
        new = re.sub(r'(?im)^(\s*title-text:\s*").*(")', r"\g<1>" + name + r"\2", new)
        if new != text:
            f.write_text(new)


def set_timeout(isodir, seconds):
    seconds = max(0, int(seconds))
    for f in config_files(isodir):
        text = f.read_text(errors="replace")
        if f.parent.name in ("isolinux", "syslinux"):
            new = re.sub(r"(?im)^(\s*timeout\s+)\d+", lambda m: m.group(1) + str(seconds * 10), text)
        else:
            new = re.sub(r"(?m)^(\s*set\s+timeout=)\S+", lambda m: m.group(1) + str(seconds), text)
        if new != text:
            f.write_text(new)


def set_splash(isodir, image):
    """Replace boot menu background images (GRUB and ISOLINUX)."""
    isodir = Path(isodir)
    targets = [p for p in list(isodir.glob("isolinux/splash*.png")) +
               list(isodir.glob("boot/grub/**/splash*.png")) +
               list(isodir.glob("boot/grub/**/background*.png")) if p.is_file()]
    if not targets:
        targets = [isodir / "boot/grub/splash.png"]
        if (isodir / "isolinux").is_dir():
            targets.append(isodir / "isolinux/splash.png")
    for t in targets:
        size = (640, 480) if t.parent.name == "isolinux" and t.name == "splash.png" else None
        if t.name == "splash800x600.png":
            size = (800, 600)
        _write_png(image, t, size)
        log.info("Boot splash: %s", t.relative_to(isodir))


def _write_png(src, dest, size=None):
    from eduka_customizer.core import imaging
    imaging.write_png(src, dest, size)


# --------------------------------------------------------------------------
# Generating a new boot structure (bootstrap and snapshot projects)

GRUB_CFG = """# Generated by Eduka-Customizer
set default=0
set timeout={timeout}
insmod all_video
insmod gfxterm
insmod png
if loadfont /boot/grub/font.pf2 ; then
    set gfxmode=auto
    terminal_output gfxterm
fi
if background_image /boot/grub/splash.png ; then
    set color_normal=white/black
    set color_highlight=black/white
else
    set menu_color_normal=white/black
    set menu_color_highlight=black/light-green
fi

menuentry "{title} Live" --id live {{
    linux /live/vmlinuz boot=live components {params}
    initrd /live/initrd.img
}}
menuentry "{title} Live (safe graphics)" {{
    linux /live/vmlinuz boot=live components {params} nomodeset
    initrd /live/initrd.img
}}
menuentry "{title} Live (copy to RAM)" {{
    linux /live/vmlinuz boot=live components {params} toram
    initrd /live/initrd.img
}}
menuentry "{title} Live (fail-safe)" {{
    linux /live/vmlinuz boot=live components memtest noapic noapm nodma nomce nosmp nosplash vga=788
    initrd /live/initrd.img
}}
if [ "$grub_platform" = "efi" ]; then
menuentry "UEFI firmware settings" {{
    fwsetup
}}
fi
"""

# Keep $prefix pointing at the memdisk of the standalone image: its modules
# live there, the ISO only provides grub.cfg (and an optional module copy).
GRUB_EMBED = """search --no-floppy --set=root --file /.disk/id/{uuid}
configfile ($root)/boot/grub/grub.cfg
"""
GRUB_MODULES = "/usr/lib/grub/x86_64-efi"

ISOLINUX_CFG = """# Generated by Eduka-Customizer
UI vesamenu.c32
DEFAULT live
PROMPT 0
TIMEOUT {timeout10}
MENU TITLE {title}
MENU BACKGROUND splash.png
MENU COLOR title 1;37;40 #ffffffff #00000000 std
MENU COLOR sel 7;37;40 #ff000000 #ffa8e6cf all
MENU COLOR unsel 37;40 #ffffffff #00000000 std
MENU TABMSG Press TAB to edit options

LABEL live
  MENU LABEL {title} Live
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components {params}

LABEL safe
  MENU LABEL {title} Live (safe graphics)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components {params} nomodeset

LABEL toram
  MENU LABEL {title} Live (copy to RAM)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components {params} toram

LABEL failsafe
  MENU LABEL {title} Live (fail-safe)
  KERNEL /live/vmlinuz
  APPEND initrd=/live/initrd.img boot=live components memtest noapic noapm nodma nomce nosmp nosplash vga=788
"""


class BootGenerator:
    """Create /isolinux, /boot/grub and an EFI image from scratch."""

    def __init__(self, project):
        self.project = project
        self.isodir = project.isodir
        self.work = project.cache / "efi"

    def tools(self):
        return {
            "isolinux": first(ISOLINUX_BIN), "isohdpfx": first(ISOHDPFX),
            "syslinux_modules": first(SYSLINUX_MODULES), "shim": first(SHIM),
            "signed_grub": first(SIGNED_GRUB_CD), "grub_mkstandalone": runner.which("grub-mkstandalone"),
            "mkfs_vfat": runner.which("mkfs.vfat") or runner.which("mkfs.fat"),
            "mtools": runner.which("mcopy"),
        }

    def generate(self, title, params, timeout=10, secure_boot=True):
        t = self.tools()
        isodir = self.isodir
        (isodir / "live").mkdir(parents=True, exist_ok=True)
        disk_id = str(uuid.uuid4())
        disk = isodir / ".disk"
        if (disk / "id").is_dir():
            shutil.rmtree(disk / "id")
        (disk / "id").mkdir(parents=True, exist_ok=True)
        (disk / "id" / disk_id).write_text("")
        if not (disk / "info").exists():
            (disk / "info").write_text(title + "\n")
        grub_dir = isodir / "boot/grub"
        grub_dir.mkdir(parents=True, exist_ok=True)
        (grub_dir / "grub.cfg").write_text(GRUB_CFG.format(title=title, params=params, timeout=timeout))
        font = first(FONT)
        if font:
            shutil.copy2(font, grub_dir / "font.pf2")
        mods = grub_dir / "x86_64-efi"
        if Path(GRUB_MODULES).is_dir() and not mods.exists():
            # Used by the signed CD GRUB, which takes its prefix from the ISO.
            shutil.copytree(GRUB_MODULES, mods,
                            ignore=lambda d, names: [n for n in names if not n.endswith((".mod", ".lst"))])
        bios = self._bios(t, title, params, timeout)
        efi = self._efi(t, disk_id, secure_boot)
        if not bios and not efi:
            raise RuntimeError("Neither ISOLINUX nor GRUB EFI tools are installed on this computer. "
                               "Install isolinux, syslinux-common, grub-efi-amd64-bin, mtools and "
                               "dosfstools.")
        self.project.state["source"]["boot_mode"] = "generate"
        self.project.state["boot_generated"] = {"bios": bios, "efi": efi}
        self.project.save()
        return bios, efi

    def _bios(self, t, title, params, timeout):
        if not (t["isolinux"] and t["isohdpfx"] and t["syslinux_modules"]):
            log.warning("ISOLINUX not found: the image will not boot on legacy BIOS")
            return False
        d = self.isodir / "isolinux"
        d.mkdir(parents=True, exist_ok=True)
        shutil.copy2(t["isolinux"], d / "isolinux.bin")
        for mod in BIOS_MODULES:
            src = t["syslinux_modules"] / mod
            if src.exists():
                shutil.copy2(src, d / mod)
        (d / "isolinux.cfg").write_text(ISOLINUX_CFG.format(title=title, params=params,
                                                            timeout10=max(1, int(timeout) * 10)))
        shutil.copy2(t["isohdpfx"], self.project.bootdir / "isohdpfx.bin")
        return True

    def _efi(self, t, disk_id, secure_boot):
        if not (t["mkfs_vfat"] and t["mtools"]):
            log.warning("mtools/dosfstools missing: the image will not boot on UEFI")
            return False
        if self.work.exists():
            shutil.rmtree(self.work)
        efi_boot = self.work / "EFI/boot"
        efi_boot.mkdir(parents=True)
        embed = self.work / "embedded.cfg"
        embed.write_text(GRUB_EMBED.format(uuid=disk_id))
        if secure_boot and t["shim"] and t["signed_grub"]:
            log.info("Using signed shim + GRUB (Secure Boot capable)")
            shutil.copy2(t["shim"], efi_boot / "bootx64.efi")
            shutil.copy2(t["signed_grub"], efi_boot / "grubx64.efi")
            mok = first(MOK)
            if mok:
                shutil.copy2(mok, efi_boot / "mmx64.efi")
            debian = self.work / "EFI/debian"
            debian.mkdir(parents=True)
            shutil.copy2(embed, debian / "grub.cfg")
        elif t["grub_mkstandalone"]:
            log.info("Building unsigned GRUB EFI image (Secure Boot must be disabled)")
            runner.run([t["grub_mkstandalone"], "-O", "x86_64-efi", "--locales=", "--fonts=",
                        "--themes=", "--compress=xz", "-o", efi_boot / "bootx64.efi",
                        "boot/grub/grub.cfg={}".format(embed)])
        else:
            log.warning("No GRUB EFI binaries found (grub-efi-amd64-bin or grub-efi-amd64-signed)")
            return False
        # The signed CD GRUB looks for /.disk/info; keep a copy of the EFI tree on the ISO too.
        dest = self.isodir / "EFI"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.work / "EFI", dest)
        size_kb = sum(f.stat().st_size for f in self.work.rglob("*") if f.is_file()) // 1024 + 1024
        img = self.isodir / "boot/grub/efi.img"
        if img.exists():
            img.unlink()
        runner.run([t["mkfs_vfat"], "-C", "-n", "EDUKA_EFI", img, str(max(size_kb, 4096))], quiet=True)
        for sub in ("::/EFI", "::/EFI/boot", "::/EFI/debian"):
            if sub == "::/EFI/debian" and not (self.work / "EFI/debian").is_dir():
                continue
            runner.run(["mmd", "-i", img, sub], quiet=True)
        for f in sorted(self.work.rglob("*")):
            if f.is_file() and f.name != "embedded.cfg":
                rel = f.relative_to(self.work)
                runner.run(["mcopy", "-i", img, f, "::/" + str(rel)], quiet=True)
        return True

    def xorriso_args(self, volume_label):
        info = self.project.state.get("boot_generated", {})
        args = ["-iso-level", "3", "-full-iso9660-filenames", "-joliet", "-joliet-long",
                "-rational-rock", "-volid", volume_label]
        bios = info.get("bios") and (self.isodir / "isolinux/isolinux.bin").exists()
        efi = info.get("efi") and (self.isodir / "boot/grub/efi.img").exists()
        if bios:
            args += ["-eltorito-boot", "isolinux/isolinux.bin", "-eltorito-catalog", "isolinux/boot.cat",
                     "-no-emul-boot", "-boot-load-size", "4", "-boot-info-table",
                     "-isohybrid-mbr", str(self.project.bootdir / "isohdpfx.bin")]
            if efi:
                args += ["-eltorito-alt-boot"]
        if efi:
            args += ["-e", "boot/grub/efi.img", "-no-emul-boot", "-isohybrid-gpt-basdat"]
        return args
