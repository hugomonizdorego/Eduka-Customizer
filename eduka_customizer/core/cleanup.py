"""Clean the root filesystem before it is squashed.

The list of things removed follows remastersys and penguins-eggs: caches,
logs, machine identity and credentials must not leak into a public ISO.
"""

import glob
import os
import shutil
from pathlib import Path

from eduka_customizer.core.apt import APT
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

OPTIONS = {
    "apt_cache": ("Clean APT package cache", True),
    "apt_lists": ("Remove APT package lists (smaller ISO, run apt update after install)", False),
    "logs": ("Empty log files", True),
    "history": ("Remove shell history and root's caches", True),
    "machine_id": ("Reset machine-id (regenerated on boot)", True),
    "ssh_keys": ("Remove SSH host keys (regenerated on boot)", True),
    "network": ("Remove saved network connections", True),
    "tmp": ("Empty /tmp and /var/tmp", True),
    "old_kernels": ("Remove old kernels, keep the newest", False),
    "skel_cache": ("Remove caches from /etc/skel", True),
    "flatpak_cache": ("Remove Flatpak download caches", True),
    # Size savers: never needed to run the system (license files are always kept).
    "docs": ("Smaller ISO: remove documentation in /usr/share/doc (keeps license files)", False),
    "man_pages": ("Smaller ISO: remove manual pages and info pages", False),
    "locales": ("Smaller ISO: remove translations of languages you did not choose", False),
}
SIZE_SAVERS = ("apt_lists", "old_kernels", "docs", "man_pages", "locales")


def defaults():
    return {k: v[1] for k, v in OPTIONS.items()}


def _rm(path):
    for p in glob.glob(str(path)):
        if os.path.islink(p) or os.path.isfile(p):
            os.unlink(p)
        elif os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)


def _empty_dir(path):
    path = Path(path)
    if path.is_dir():
        for p in path.iterdir():
            _rm(p)


def kernels(rootfs):
    """Installed kernel versions, newest last."""
    import re
    versions = []
    for p in Path(rootfs, "boot").glob("vmlinuz-*"):
        versions.append(p.name[len("vmlinuz-"):])

    def key(v):
        return [int(x) if x.isdigit() else x for x in re.split(r"[.+~-]", v)]
    try:
        return sorted(versions, key=key)
    except TypeError:
        return sorted(versions)


def _remove_docs(rootfs):
    """Remove /usr/share/doc except the copyright and license files (they must stay)."""
    base = Path(rootfs, "usr/share/doc")
    if not base.is_dir():
        return
    for f in base.rglob("*"):
        if (f.is_file() or f.is_symlink()) and not (f.name == "copyright" or f.name.lower().startswith(
                ("license", "licence", "copying", "notice"))):
            try:
                f.unlink()
            except OSError:
                pass


def kept_languages(project):
    """Language codes whose translations stay: English plus the project's languages."""
    loc = project.state.get("locale") or {}
    lang = project.state.get("language") or {}
    names = [loc.get("default", ""), lang.get("default", "")] + list(loc.get("extra") or []) + \
        list(lang.get("extra") or [])
    keep = {"en", "C"}
    for n in names:
        n = (n or "").split(".")[0]
        if n:
            keep.add(n)
            keep.add(n.split("_")[0])
    return keep


def _remove_locales(rootfs, keep):
    base = Path(rootfs, "usr/share/locale")
    if not base.is_dir():
        return
    for d in base.iterdir():
        if d.is_dir() and (d / "LC_MESSAGES").is_dir():
            name = d.name.split("@")[0]
            if name not in keep and name.split("_")[0] not in keep:
                shutil.rmtree(d, ignore_errors=True)


def run(project, options=None):
    opts = defaults()
    opts.update(options or {})
    rootfs = project.rootfs
    chroot = Chroot(rootfs)
    log.info("Cleaning the root filesystem")
    with chroot:
        if opts.get("old_kernels"):
            ks = kernels(rootfs)
            old = ["linux-image-" + k for k in ks[:-1]]
            if old:
                log.info("Removing old kernels: %s", " ".join(old))
                chroot.run(APT + ["purge"] + old, check=False)
        chroot.run(APT + ["autoremove", "--purge"], check=False, quiet=True)
        if opts.get("apt_cache"):
            chroot.run(APT + ["clean"], check=False, quiet=True)
        if opts.get("logs") and (rootfs / "usr/bin/journalctl").exists():
            _empty_dir(rootfs / "var/log/journal")
    if opts.get("apt_lists"):
        _empty_dir(rootfs / "var/lib/apt/lists")
        (rootfs / "var/lib/apt/lists/partial").mkdir(parents=True, exist_ok=True)
    for p in ("var/cache/apt/*.bin", "var/lib/dpkg/*-old", "var/cache/debconf/*-old",
              "etc/apt/sources.list.eduka-old", "var/cache/apt/archives/partial/*"):
        _rm(rootfs / p)
    if opts.get("logs"):
        for f in Path(rootfs, "var/log").rglob("*"):
            if f.is_file() and not f.is_symlink():
                if f.suffix in (".gz", ".xz") or f.name[-2:] in (".1", ".2", ".3", ".4"):
                    f.unlink()
                else:
                    f.write_bytes(b"")
    if opts.get("history"):
        for p in ("root/.bash_history", "root/.zsh_history", "root/.eduka_history",
                  "root/.lesshst", "root/.viminfo", "root/.wget-hsts", "root/.python_history",
                  "root/.cache", "root/.local/share/recently-used.xbel", "root/.Xauthority"):
            _rm(rootfs / p)
    if opts.get("machine_id"):
        mid = rootfs / "etc/machine-id"
        if mid.exists() or mid.is_symlink():
            _rm(mid)
        mid.write_text("")  # empty file: systemd generates a new ID at boot
        _rm(rootfs / "var/lib/dbus/machine-id")
        _rm(rootfs / "var/lib/systemd/random-seed")
        _rm(rootfs / "var/lib/systemd/credential.secret")
    if opts.get("ssh_keys"):
        _rm(rootfs / "etc/ssh/ssh_host_*")
    if opts.get("network"):
        _empty_dir(rootfs / "etc/NetworkManager/system-connections")
        _rm(rootfs / "var/lib/NetworkManager/secret_key")
        _rm(rootfs / "var/lib/NetworkManager/*.lease")
        _rm(rootfs / "var/lib/dhcp/*")
        _rm(rootfs / "etc/udev/rules.d/70-persistent-*.rules")
    if opts.get("tmp"):
        _empty_dir(rootfs / "tmp")
        _empty_dir(rootfs / "var/tmp")
    if opts.get("skel_cache"):
        for p in (".cache", ".Xauthority", ".xsession-errors", ".xsession-errors.old",
                  ".bash_history", ".local/share/recently-used.xbel", ".local/share/Trash",
                  ".thumbnails", ".dbus", ".pki"):
            _rm(rootfs / "etc/skel" / p)
    if opts.get("flatpak_cache"):
        _rm(rootfs / "var/tmp/flatpak-cache-*")
        _rm(rootfs / "var/lib/flatpak/repo/tmp/*")
    if opts.get("docs"):
        _remove_docs(rootfs)
    if opts.get("man_pages"):
        for d in ("usr/share/man", "usr/share/info"):
            _empty_dir(rootfs / d)
    if opts.get("locales"):
        _remove_locales(rootfs, kept_languages(project))
    # Leftovers of the legacy Customizer (rootfs/conf, /temp.deb, /hook).
    for p in ("conf", "temp.deb", "hook"):
        _rm(rootfs / p)
    project.record("cleanup", ",".join(k for k, v in opts.items() if v))
