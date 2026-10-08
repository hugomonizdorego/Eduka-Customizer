"""A careful check of the Calamares installer of the image.

Calamares stops (or the installation fails at the end) when one piece of its
configuration does not match the system: a branding folder whose componentName
differs, a missing image, a module of the sequence that is not installed, a
package to remove that is not there, a file system without its mkfs tool, a
boot loader whose tools are missing... Every problem is reported with the file
it is in, before the ISO is built.
"""

import re
from pathlib import Path

from eduka_customizer.core import yamlconf
from eduka_customizer.core.apt import is_installed_status, parse_deb822

ETC = "etc/calamares"
SHARE = "usr/share/calamares"
# Modules that do nothing useful (or fail) without a configuration file.
NEEDS_CONF = {"unpackfs", "shellprocess", "contextualprocess", "packagechooser", "netinstall", "dummyprocess"}
MKFS = {"ext4": "mkfs.ext4", "btrfs": "mkfs.btrfs", "xfs": "mkfs.xfs", "f2fs": "mkfs.f2fs",
        "ext3": "mkfs.ext3", "jfs": "mkfs.jfs", "reiser": "mkreiserfs"}
MKFS_PACKAGE = {"btrfs": "btrfs-progs", "xfs": "xfsprogs", "f2fs": "f2fs-tools", "jfs": "jfsutils"}
DM_BINARIES = {"sddm": "usr/bin/sddm", "lightdm": "usr/sbin/lightdm", "gdm": "usr/sbin/gdm3",
               "lxdm": "usr/sbin/lxdm", "slim": "usr/bin/slim", "greetd": "usr/sbin/greetd",
               "mdm": "usr/sbin/mdm", "lightdm-gtk-greeter": "usr/sbin/lightdm"}
LOADER_TOOLS = {"grub": ["usr/sbin/grub-install", "usr/sbin/grub-mkconfig"],
                "sb-shim": ["usr/sbin/grub-install"],
                "systemd-boot": ["usr/bin/bootctl", "usr/bin/kernel-install"],
                "refind": ["usr/sbin/refind-install"]}


def _version(rootfs):
    status = Path(rootfs, "var/lib/dpkg/status")
    if status.exists():
        m = re.search(r"(?ms)^Package: calamares\n.*?^Version: (\S+)", status.read_text(errors="replace"))
        if m:
            v = re.match(r"(?:\d+:)?(\d+)\.(\d+)", m.group(1))
            if v:
                return int(v.group(1)), int(v.group(2))
    return None


def loaders_for(version):
    """EFI boot loaders the Calamares version can install (3.3 added rEFInd)."""
    out = ["grub", "sb-shim", "systemd-boot"]
    if version is None or version >= (3, 3):
        out.append("refind")
    return out


def _installed(rootfs):
    status = Path(rootfs, "var/lib/dpkg/status")
    if not status.exists():
        return set()
    return {st.get("Package") for st in parse_deb822(status.read_text(errors="replace"))
            if is_installed_status(st.get("Status", ""))}


def _load(path):
    """(data, error) of a YAML file."""
    try:
        text = Path(path).read_text(errors="replace")
    except OSError as e:
        return {}, str(e)
    try:
        data = yamlconf.load(text)
    except Exception as e:  # any parser error is a problem of the file
        return {}, "not valid YAML: {}".format(e)
    if text.strip() and not isinstance(data, dict):
        return {}, "not a YAML mapping"
    return data or {}, ""


def _module_dirs(rootfs, settings):
    r = Path(rootfs)
    dirs = sorted(r.glob("usr/lib/*/calamares/modules")) + [r / "usr/lib/calamares/modules"]
    for d in settings.get("modules-search") or []:
        if isinstance(d, str) and d.startswith("/"):
            dirs.append(r / d.lstrip("/"))
    return [d for d in dirs if d.is_dir()]


def _conf(rootfs, name):
    for base in (Path(rootfs, ETC, "modules"), Path(rootfs, SHARE, "modules")):
        p = base / name
        if p.is_file():
            return p
    return None


def _exists_in_image(rootfs, path):
    p = Path(rootfs, str(path).lstrip("/"))
    return p.exists() or p.is_symlink()


def check(project):
    """[(level, where, message)] with level 'fail', 'warn' or 'ok'."""
    r = Path(project.rootfs)
    out = []
    add = lambda level, where, msg: out.append((level, where, msg))  # noqa: E731
    settings_path = r / ETC / "settings.conf"
    if not settings_path.exists():
        settings_path = r / SHARE / "settings.conf"
    if not settings_path.exists():
        if (r / "usr/bin/calamares").exists():
            add("fail", "settings.conf", "Calamares is installed but has no settings.conf (install "
                                         "calamares-settings-debian or your own settings package)")
        return out
    settings, err = _load(settings_path)
    rel = "/" + str(settings_path.relative_to(r))
    if err:
        add("fail", rel, err)
        return out
    if not (r / "usr/bin/calamares").exists():
        add("fail", rel, "settings.conf is there but the calamares program is not installed")
    version = _version(r)
    installed = _installed(r)

    # Branding -----------------------------------------------------------------------------
    name = str(settings.get("branding") or "")
    bdir = None
    for base in (r / ETC / "branding", r / SHARE / "branding"):
        if name and (base / name / "branding.desc").exists():
            bdir = base / name
            break
    if not name:
        add("fail", rel, "no 'branding:' key")
    elif not bdir:
        add("fail", rel, "branding '{}' has no folder with branding.desc".format(name))
    else:
        before = len(out)
        brel = "/" + str((bdir / "branding.desc").relative_to(r))
        desc, err = _load(bdir / "branding.desc")
        if err:
            add("fail", brel, err)
        else:
            comp = str(desc.get("componentName") or "")
            if comp != name:
                add("fail", brel, "componentName '{}' must be the folder name '{}'".format(comp, name))
            for key, value in (desc.get("images") or {}).items():
                if value and not str(value).startswith("/") and not (bdir / str(value)).exists():
                    add("fail", brel, "image {} = {} does not exist".format(key, value))
                elif value and str(value).startswith("/") and not _exists_in_image(r, value):
                    add("fail", brel, "image {} = {} does not exist".format(key, value))
            show = desc.get("slideshow")
            api = int(desc.get("slideshowAPI") or 1)
            if isinstance(show, str):
                qml = bdir / show
                if not qml.exists():
                    add("fail", brel, "slideshow {} does not exist".format(show))
                else:
                    out.extend(_check_qml(r, qml, api))
            elif isinstance(show, list):
                for img in show:
                    if not (bdir / str(img)).exists():
                        add("fail", brel, "slideshow image {} does not exist".format(img))
            if version:
                style = desc.get("style") or {}
                lower = [k for k in style if k[:1].islower()]
                upper = [k for k in style if k[:1].isupper()]
                if version >= (3, 3) and lower:
                    add("warn", brel, "Calamares {}.{} ignores lower-case style keys: {}".format(
                        version[0], version[1], ", ".join(lower)))
                if version < (3, 3) and upper:
                    add("warn", brel, "Calamares {}.{} ignores upper-case style keys: {}".format(
                        version[0], version[1], ", ".join(upper)))
            for key in ("productName", "bootloaderEntryName"):
                if not (desc.get("strings") or {}).get(key):
                    add("warn", brel, "strings: {} is empty".format(key))
            if len(out) == before:
                add("ok", brel, "branding '{}' is complete".format(name))

    # Modules of the sequence -------------------------------------------------------------------
    instances = {}
    for inst in settings.get("instances") or []:
        if isinstance(inst, dict) and inst.get("id") and inst.get("module"):
            instances["{}@{}".format(inst["module"], inst["id"])] = inst
            conf = inst.get("config") or "{}-{}.conf".format(inst["module"], inst["id"])
            if not _conf(r, conf):
                add("fail", rel, "instance {}@{}: configuration {} not found".format(inst["module"], inst["id"],
                                                                                   conf))
    available = set()
    for d in _module_dirs(r, settings):
        available |= {p.parent.name for p in d.glob("*/module.desc")}
    used = []
    for step in settings.get("sequence") or []:
        if isinstance(step, dict):
            for kind in ("show", "exec"):
                used += [str(m) for m in step.get(kind) or []]
    if not used:
        add("fail", rel, "the 'sequence' is empty")
    for m in used:
        module = m.split("@")[0]
        if "@" in m and m not in instances and m.split("@")[1] != module:
            add("fail", rel, "sequence uses {} but no instance defines it".format(m))
        if available and module not in available:
            add("fail", rel, "module '{}' of the sequence is not installed".format(module))
        if module in NEEDS_CONF and "@" not in m and not _conf(r, module + ".conf"):
            add("fail", rel, "module '{}' needs modules/{}.conf".format(module, module))
    for p in sorted((r / ETC / "modules").glob("*.conf")) if (r / ETC / "modules").is_dir() else []:
        _d, err = _load(p)
        if err:
            add("fail", "/" + str(p.relative_to(r)), err)
    modules = {m.split("@")[0] for m in used}

    # Module configurations ------------------------------------------------------------------------
    if "unpackfs" in modules:
        out.extend(_check_unpackfs(r))
    if "bootloader" in modules:
        out.extend(_check_bootloader(r, version))
    if "displaymanager" in modules:
        out.extend(_check_dm(r))
    if "packages" in modules:
        out.extend(_check_packages(r, installed))
    if "partition" in modules:
        out.extend(_check_partition(r))
    if "users" in modules:
        out.extend(_check_users(r))
    if "locale" in modules:
        out.extend(_check_locale(r))
    for m in used:
        if m.split("@")[0] in ("shellprocess", "contextualprocess"):
            conf = instances.get(m, {}).get("config") or ("{}-{}.conf".format(*m.split("@")) if "@" in m
                                                          else m + ".conf")
            p = _conf(r, conf)
            if p:
                out.extend(_check_commands(r, p))
    return out


def _check_qml(r, qml, api):
    rel = "/" + str(qml.relative_to(r))
    out = []
    text = qml.read_text(errors="replace")
    body = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    body = re.sub(r"//[^\n]*|/\*.*?\*/", "", body, flags=re.S)
    if body.count("{") != body.count("}"):
        out.append(("fail", rel, "the numbers of '{' and '}' differ: the slideshow would not load"))
    if "import QtQuick" not in text:
        out.append(("fail", rel, "missing 'import QtQuick'"))
    if api == 2 and "calamares.slideshow" not in text:
        out.append(("fail", rel, "slideshowAPI 2 needs 'import calamares.slideshow 1.0'"))
    for src in re.findall(r'source:\s*"([^"]+)"', text):
        if not src.startswith(("qrc:", "file:", "http", "image:")) and not (qml.parent / src).exists():
            out.append(("fail", rel, "slide image {} does not exist".format(src)))
    return out


def _check_unpackfs(r):
    p = _conf(r, "unpackfs.conf")
    if not p:
        return [("fail", "unpackfs", "modules/unpackfs.conf is missing: nothing would be copied")]
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    out = []
    for item in data.get("unpack") or []:
        src = str((item or {}).get("source", ""))
        if src.endswith(".squashfs") and "/live/" not in src:
            out.append(("fail", rel, "source {} is not a live-boot path (use /run/live/medium/live/"
                                     "filesystem.squashfs)".format(src)))
        elif src.endswith(".squashfs") and not src.startswith(("/run/live/medium/", "/lib/live/mount/medium/")):
            out.append(("warn", rel, "source {}: live-boot mounts the ISO at /run/live/medium".format(src)))
    if not data.get("unpack"):
        out.append(("fail", rel, "'unpack' is empty"))
    return out or [("ok", rel, "copies the live system")]


def _check_bootloader(r, version):
    p = _conf(r, "bootloader.conf")
    if not p:
        return [("warn", "bootloader", "modules/bootloader.conf is missing: Calamares defaults are used")]
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    out = []
    loader = str(data.get("efiBootLoader") or "grub")
    if loader not in loaders_for(version):
        out.append(("fail", rel, "efiBootLoader '{}' is not supported by this Calamares (use {})".format(
            loader, ", ".join(loaders_for(version)))))
    for tool in LOADER_TOOLS.get(loader, []):
        if not _exists_in_image(r, tool):
            out.append(("fail", rel, "{} needs /{} in the image".format(loader, tool)))
    if loader not in ("grub", "sb-shim") and not _exists_in_image(r, "usr/sbin/grub-install"):
        out.append(("warn", rel, "BIOS computers always get GRUB: install grub-pc-bin in the image"))
    if not _exists_in_image(r, "usr/bin/efibootmgr") and not _exists_in_image(r, "bin/efibootmgr"):
        out.append(("warn", rel, "efibootmgr is not installed: UEFI boot entries cannot be written"))
    efi_id = str(data.get("efiBootloaderId") or "")
    signed = _exists_in_image(r, "usr/lib/shim/shimx64.efi.signed") or \
        bool(list(Path(r, "usr/lib/grub/x86_64-efi-signed").glob("*.efi.signed")))
    if loader in ("grub", "sb-shim") and signed and efi_id and efi_id != "debian":
        out.append(("warn", rel, "Debian's signed GRUB looks for EFI/debian: efiBootloaderId '{}' needs a copy "
                                 "in EFI/debian (Distro Branding keeps it in sync)".format(efi_id)))
    return out or [("ok", rel, "boot loader {}".format(loader))]


def _check_dm(r):
    p = _conf(r, "displaymanager.conf")
    if not p:
        return []
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    listed = [str(d) for d in data.get("displaymanagers") or []]
    present = [d for d, b in DM_BINARIES.items() if _exists_in_image(r, b) and "greeter" not in d]
    if listed and present and not set(listed) & set(present):
        return [("fail", rel, "displaymanagers {} but the image has {}: autologin and the default session "
                              "would not be set".format(", ".join(listed), ", ".join(present)))]
    return [("ok", rel, "login screen {}".format(", ".join(set(listed) & set(present)) or "auto"))]


def _check_packages(r, installed):
    p = _conf(r, "packages.conf")
    if not p:
        return []
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    out = []
    for op in data.get("operations") or []:
        if not isinstance(op, dict):
            continue
        for pkg in op.get("remove") or []:
            name = pkg if isinstance(pkg, str) else (pkg or {}).get("package", "")
            if name and name not in installed:
                out.append(("fail", rel, "'remove: {}' is not installed: apt would fail at the end of the "
                                         "installation (use try_remove)".format(name)))
    if data.get("backend", "apt") != "apt":
        out.append(("warn", rel, "backend is {} (Debian uses apt)".format(data.get("backend"))))
    return out or [("ok", rel, "package operations")]


def _check_partition(r):
    p = _conf(r, "partition.conf")
    if not p:
        return []
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    out = []
    fss = [str(f).lower() for f in (data.get("availableFileSystemTypes") or [])] + \
        [str(data.get("defaultFileSystemType", "ext4")).lower()]
    for fs in sorted(set(fss)):
        tool = MKFS.get(fs)
        if tool and not any(_exists_in_image(r, d + "/" + tool) for d in ("usr/sbin", "sbin")):
            out.append(("fail", rel, "{} needs {} ({}) in the image".format(fs, tool, MKFS_PACKAGE.get(fs, "")
                                                                          or "e2fsprogs")))
    swap = data.get("userSwapChoices") or []
    if data.get("initialSwapChoice") and swap and data["initialSwapChoice"] not in swap:
        out.append(("fail", rel, "initialSwapChoice {} is not one of userSwapChoices".format(data["initialSwapChoice"])))
    return out or [("ok", rel, "file systems {}".format(", ".join(sorted(set(fss)))))]


def _check_users(r):
    p = _conf(r, "users.conf")
    if not p:
        return []
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    groups = set()
    gfile = r / "etc/group"
    if gfile.exists():
        groups = {l.split(":")[0] for l in gfile.read_text(errors="replace").splitlines() if l}
    out = []
    for g in data.get("defaultGroups") or []:
        if isinstance(g, dict):
            if g.get("must_exist") and g.get("name") not in groups and groups:
                out.append(("fail", rel, "group {} must exist but is not in /etc/group".format(g.get("name"))))
        elif groups and str(g) not in groups:
            out.append(("warn", rel, "group {} is not in /etc/group (Calamares creates it)".format(g)))
    sudo = data.get("sudoersGroup")
    if sudo and groups and sudo not in groups:
        out.append(("fail", rel, "sudoersGroup {} does not exist".format(sudo)))
    shell = (data.get("user") or {}).get("shell") or data.get("userShell")
    if shell and not _exists_in_image(r, shell):
        out.append(("fail", rel, "the user shell {} is not installed".format(shell)))
    return out or [("ok", rel, "users and groups")]


def _check_locale(r):
    p = _conf(r, "locale.conf")
    if not p:
        return []
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    region, zone = data.get("region"), data.get("zone")
    if region and zone and Path(r, "usr/share/zoneinfo").is_dir() and \
            not Path(r, "usr/share/zoneinfo", str(region), str(zone)).exists():
        return [("fail", rel, "time zone {}/{} does not exist".format(region, zone))]
    return [("ok", rel, "time zone {}/{}".format(region or "auto", zone or ""))]


def _check_commands(r, p):
    rel = "/" + str(p.relative_to(r))
    data, err = _load(p)
    if err:
        return [("fail", rel, err)]
    out = []
    script = data.get("script") or []
    if isinstance(script, (str, dict)):
        script = [script]
    for item in script:
        cmd = item.get("command", "") if isinstance(item, dict) else str(item)
        cmd = re.sub(r"^-", "", cmd.strip())
        first = cmd.split()[0] if cmd.split() else ""
        if first.startswith("/") and "@@" not in first and "${" not in first and not _exists_in_image(r, first):
            out.append(("fail", rel, "command {} does not exist in the image".format(first)))
    return out


def summary(results):
    return (sum(1 for x in results if x[0] == "fail"), sum(1 for x in results if x[0] == "warn"))
