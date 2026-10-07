"""Snapshot the running Edukasaun OS / Debian system (remastersys style).

The running system is copied with rsync into the project's root
filesystem, without personal data unless "backup" mode is chosen, and
can then be customized and built like any other project.
"""

from pathlib import Path

from eduka_customizer.core import distro, runner
from eduka_customizer.core.log import log

EXCLUDES = [
    "/dev/*", "/proc/*", "/sys/*", "/run/*", "/tmp/*", "/var/tmp/*", "/mnt/*", "/media/*",
    "/lost+found", "/swapfile", "/swap.img", "/boot/efi/*", "/etc/fstab", "/etc/crypttab",
    "/etc/machine-id", "/var/lib/dbus/machine-id", "/etc/ssh/ssh_host_*",
    "/etc/NetworkManager/system-connections/*", "/var/cache/apt/archives/*.deb",
    "/var/lib/docker/*", "/var/lib/containers/*", "/var/lib/machines/*", "/var/lib/libvirt/images/*",
    "/var/log/*", "/root/.cache", "/root/.bash_history", "/snap", "/var/lib/snapd",
]
PERSONAL = ["/home/*"]


def snapshot(project, mode="dist"):
    """mode 'dist': without /home (public ISO). 'backup': keeps /home."""
    runner.require("rsync")
    info = distro.detect("/")
    distro.validate(info, "/")
    rootfs = project.rootfs
    rootfs.mkdir(parents=True, exist_ok=True)
    excludes = EXCLUDES + (PERSONAL if mode == "dist" else [])
    # Never copy the project (or any other project) into itself.
    excludes.append(str(project.path) + "/*")
    excludes.append(str(Path(project.path).parent) + "/*/rootfs")
    args = ["rsync", "-aHAX", "--delete", "--numeric-ids", "--info=progress2", "--no-inc-recursive"]
    for e in excludes:
        args += ["--exclude", e]
    args += ["/", str(rootfs) + "/"]
    log.info("Copying the running system (%s mode). This can take a long time.", mode)
    runner.run(args, ok_codes=(0, 23, 24), progress=lambda p: None)
    for d in ("dev", "proc", "sys", "run", "tmp", "mnt", "media", "home"):
        (rootfs / d).mkdir(exist_ok=True)
    (rootfs / "tmp").chmod(0o1777)
    fstab = rootfs / "etc/fstab"
    fstab.write_text("# /etc/fstab: the installer writes the real table\n")
    if mode == "dist":
        _reset_users(rootfs)
    project.state["source"].update({"kind": "snapshot", "path": "/", "label": info.pretty_name,
                                    "boot_mode": "generate"})
    project.state["distro"] = info.to_dict()
    project.record("snapshot", mode)
    return info


def _reset_users(rootfs):
    """Remove regular user accounts (UID 1000-59999) from the copy."""
    removed = []
    for name in ("passwd", "shadow", "group", "gshadow"):
        p = rootfs / "etc" / name
        if not p.exists():
            continue
        keep = []
        for line in p.read_text().splitlines():
            parts = line.split(":")
            if name == "passwd" and len(parts) > 2 and parts[2].isdigit() and 1000 <= int(parts[2]) < 60000:
                removed.append(parts[0])
                continue
            if name in ("shadow", "gshadow") and parts[0] in removed:
                continue
            if name == "group":
                if len(parts) > 2 and parts[2].isdigit() and 1000 <= int(parts[2]) < 60000 and parts[0] in removed:
                    continue
                if len(parts) > 3:
                    members = [m for m in parts[3].split(",") if m and m not in removed]
                    parts[3] = ",".join(members)
                    line = ":".join(parts)
            if name == "gshadow" and len(parts) > 3:
                parts[3] = ",".join(m for m in parts[3].split(",") if m and m not in removed)
                line = ":".join(parts)
            keep.append(line)
        p.write_text("\n".join(keep) + "\n")
    if removed:
        log.info("Removed personal accounts from the snapshot: %s", ", ".join(removed))
