"""Automatic fixes for the problems the checks find.

Every rule recognizes one kind of problem (by its message) and knows a safe
way to fix it: install the missing package, correct a Calamares setting,
repair the package database, remove a leftover file. Problems without a rule
need a decision only you can make (for example which files in /home belong
in the ISO); the checks then point to the page where you fix them.
"""

import re
from pathlib import Path

from eduka_customizer.core.log import log


def _install(*packages):
    def fix(project):
        from eduka_customizer.core.apt import Packages
        pk = Packages(project)
        with pk.chroot:
            pk.update()
            have = pk.available(packages)
            missing = [p for p in packages if p not in have]
            if missing:
                raise RuntimeError("Not available from the APT sources of the image: " + " ".join(missing))
            pk.install(list(packages), update=False)
    return fix


def _calamares(module, values):
    def fix(project):
        from eduka_customizer.core.calamares import Calamares
        Calamares(project).write(module, values)
    return fix


def _repair_dpkg(project):
    from eduka_customizer.core.chroot import Chroot
    with Chroot(project.rootfs) as ch:
        ch.run(["dpkg", "--configure", "-a"], check=False)
        ch.run(["apt-get", "-y", "-f", "install"], check=False)


def _remove_policy(project):
    p = Path(project.rootfs, "usr/sbin/policy-rc.d")
    if p.exists():
        p.unlink()


def _unmount(project):
    from eduka_customizer.core.chroot import unmount_all
    unmount_all(project.rootfs)


def _host_tools(project):
    from eduka_customizer.core import runner
    runner.run(["apt-get", "install", "-y", "squashfs-tools", "xorriso"])


def _try_remove(name):
    def fix(project):
        from eduka_customizer.core.calamares import Calamares
        c = Calamares(project)
        data = c.read("packages")
        ops = []
        for op in data.get("operations") or []:
            if isinstance(op, dict) and "remove" in op:
                keep = [p for p in op["remove"] if (p if isinstance(p, str) else p.get("package")) != name]
                op = dict(op)
                if keep:
                    op["remove"] = keep
                else:
                    op.pop("remove")
                op.setdefault("try_remove", [])
                op["try_remove"] = list(op["try_remove"]) + [name]
            ops.append(op)
        c.write("packages", {"operations": [o for o in ops if o]})
    return fix


def _display_managers(present):
    return _calamares("displaymanager", {"displaymanagers": present})


def _shell(project):
    from eduka_customizer.core.calamares import Calamares
    c = Calamares(project)
    if c._is_32():
        c.write("users", {"userShell": "/bin/bash"})
    else:
        user = dict(c.read("users").get("user") or {})
        user["shell"] = "/bin/bash"
        c.write("users", {"user": user})


def _drop_module(module):
    def fix(project):
        from eduka_customizer.core.calamares import Calamares
        c = Calamares(project)
        seq = []
        for step in c.read("settings").get("sequence") or []:
            if isinstance(step, dict):
                step = {k: [m for m in v if str(m).split("@")[0] != module] for k, v in step.items()}
            seq.append(step)
        c.write("settings", {"sequence": seq})
    return fix


def _component_name(name):
    def fix(project):
        from eduka_customizer.core import yamlconf
        from eduka_customizer.core.calamares import Calamares
        desc = Calamares(project).branding_dir() / "branding.desc"
        desc.write_text(yamlconf.update(desc.read_text(errors="replace"), {"componentName": name}))
    return fix


def _slideshow(project):
    from eduka_customizer.core.calamares import Calamares
    c = Calamares(project)
    c.set_branding(slides=c.slide_data() or [], slide_seconds=8)


def _timezone(project):
    from eduka_customizer.core.calamares import Calamares
    from eduka_customizer.core.config import DEFAULT_TIMEZONE
    tz = project.state.get("locale", {}).get("timezone") or DEFAULT_TIMEZONE
    Calamares(project).set_locale(tz)


def _boot_loader_again(project):
    from eduka_customizer.core.bootchoice import BootChoice
    b = BootChoice(project)
    b.use(b.current())


def _install_loader_tools(loader_id):
    def fix(project):
        from eduka_customizer.core.bootchoice import BootChoice
        BootChoice(project).install(loader_id)
    return fix


# (message pattern, what the fix does, function(match) -> fix(project))
RULES = [
    (r"choose the boot loader again|is chosen but not installed in the image",
     "Set up the chosen boot loader again", lambda m: _boot_loader_again),
    (r"(efistub|syslinux) needs /", "Install the {1} packages", lambda m: _install_loader_tools(m.group(1))),
    (r"(?:grub|sb-shim) needs /usr/sbin/grub-install", "Install GRUB (grub2-common, grub-efi-amd64-bin, grub-pc-bin, "
     "efibootmgr)", lambda m: _install("grub2-common", "grub-efi-amd64-bin", "grub-pc-bin", "efibootmgr")),
    (r"systemd-boot needs", "Install systemd-boot", lambda m: _install("systemd-boot")),
    (r"refind needs", "Install rEFInd", lambda m: _install("refind")),
    (r"efibootmgr is not installed", "Install efibootmgr", lambda m: _install("efibootmgr")),
    (r"needs (mkfs\.\w+) \(([\w.+-]+)\)", "Install {2}", lambda m: _install(m.group(2))),
    (r"'remove: (\S+)' is not installed", "Change 'remove: {1}' to 'try_remove'", lambda m: _try_remove(m.group(1))),
    (r"displaymanagers .* but the image has ([\w, -]+?):", "Use the login screen of the image ({1})",
     lambda m: _display_managers([x.strip() for x in m.group(1).split(",") if x.strip()])),
    (r"componentName '.*' must be the folder name '(.+)'", "Set componentName to {1}",
     lambda m: _component_name(m.group(1))),
    (r"source \S+ is not a live-boot path", "Copy from /run/live/medium/live/filesystem.squashfs",
     lambda m: _calamares("unpackfs", {"unpack": [{"source": "/run/live/medium/live/filesystem.squashfs",
                                                   "sourcefs": "squashfs", "destination": ""}]})),
    (r"sudoersGroup (\S+) does not exist", "Use the group sudo", lambda m: _calamares("users", {"sudoersGroup": "sudo"})),
    (r"the user shell (\S+) is not installed", "Use /bin/bash", lambda m: _shell),
    (r"time zone \S+ does not exist", "Use the project's time zone", lambda m: _timezone),
    (r"module '([\w-]+)' of the sequence is not installed", "Leave '{1}' out of the installer",
     lambda m: _drop_module(m.group(1))),
    (r"slideshow|the numbers of '\{' and '\}' differ|slide image .* does not exist|import calamares.slideshow",
     "Write a new working slideshow", lambda m: _slideshow),
    (r"settings\.conf is there but the calamares program is not installed", "Install calamares",
     lambda m: _install("calamares")),
    (r"Calamares is installed but has no settings\.conf", "Install calamares-settings-debian",
     lambda m: _install("calamares-settings-debian")),
    (r"Half-installed packages|interrupted dpkg run", "Repair the package database (dpkg --configure -a, "
     "apt-get -f install)", lambda m: _repair_dpkg),
    (r"/usr/sbin/policy-rc.d is left", "Remove /usr/sbin/policy-rc.d", lambda m: _remove_policy),
    (r"mount\(s\) are active", "Release the mounts", lambda m: _unmount),
    (r"Missing: .*\(sudo apt install squashfs-tools xorriso\)", "Install squashfs-tools and xorriso on this "
     "computer", lambda m: _host_tools),
    (r"Missing (live-boot|live-config)", "Install live-boot, live-config and live-config-systemd",
     lambda m: _install("live-boot", "live-config", "live-config-systemd")),
    (r"No kernel in /boot", "Install the Debian kernel (linux-image-amd64)", lambda m: _install("linux-image-amd64")),
]


def find(message):
    """(label, fix function) for a problem message, or None when only you can fix it."""
    for pattern, label, make in RULES:
        m = re.search(pattern, message)
        if m:
            text = label
            for i, g in enumerate(m.groups(), 1):
                text = text.replace("{%d}" % i, g or "")
            return text, make(m)
    return None


def run(project, messages, progress=None):
    """Apply the automatic fixes for *messages*. Returns (fixed labels, [(label, error)])."""
    done, failed, seen = [], [], set()
    for msg in messages:
        found = find(msg)
        if not found or found[0] in seen:
            continue
        label, func = found
        seen.add(label)
        if progress:
            progress("Fixing: " + label)
        try:
            func(project)
            done.append(label)
            log.info("Fixed: %s", label)
        except Exception as e:  # report every fix that did not work and go on
            failed.append((label, str(e)))
            log.error("Could not fix (%s): %s", label, e)
    if done:
        project.record("auto-fix", "; ".join(done))
    return done, failed
