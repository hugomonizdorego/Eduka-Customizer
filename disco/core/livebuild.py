"""The live-build route: Debian's own tool makes the whole ISO.

D!sco turns the choices of a project (disco builder) into a live-build configuration in
<project>/live-build and runs Debian's live-build there:

  auto/config                            the `lb config` command with every choice
  config/package-lists/*.list.chroot     the package lists that are on, and the desktop
  config/includes.chroot/                a copy of the overlay folder
  config/hooks/normal/*.hook.chroot      your scripts (hooks/*.sh) and the removals ('-name')

`lb build` then makes the system (debootstrap), installs everything in a chroot,
compresses it (squashfs) and writes the ISO (xorriso). The ISO is moved to the
output folder with its checksum. The configuration stays: you can open it, change
it and run `sudo lb build` in that folder yourself.

live-build makes ISO images of Debian. Raspberry Pi SD cards and Devuan are made
with the D!sco method.
"""

import shlex
import shutil
from pathlib import Path

from disco.core import platforms, runner
from disco.core.log import log

FOLDER = "live-build"
COMPRESSION = {"zstd", "xz", "gzip", "lzo", "lz4"}


def folder(project):
    return Path(project.path) / FOLDER


def version():
    """The version of live-build on this computer ('' when it is not installed)."""
    if not runner.which("lb"):
        return ""
    try:
        out = runner.run(["lb", "--version"], capture=True, check=False, quiet=True)
    except OSError:
        return ""
    import re
    m = re.search(r"(\d[\w.:~+-]*)", out or "")
    return m.group(1) if m else ""


def usable(ver=None):
    """(ok, why): Debian's live-build of 2021 or later (Debian 11+) understands the options D!sco writes."""
    ver = version() if ver is None else ver
    if not ver:
        return False, "live-build is not installed: sudo apt install live-build"
    num = ver.split(":")[-1]
    if not (num[:8].isdigit() and int(num[:8]) >= 20210407):
        return False, ("live-build {} is too old or not Debian's (Debian 11 or newer has 1:2021... and later): "
                       "install Debian's live-build".format(ver))
    return True, "live-build {}".format(ver)


# lb's own exit status counts: behind a pipe into tee only tee's would (and a failed build would pass).
AUTO_BUILD = """#!/bin/sh
set -e
rm -f .lb-failed
{ lb build noauto "${@}" 2>&1 || echo "$?" > .lb-failed; } | tee build.log
if [ -s .lb-failed ]; then
    status=$(cat .lb-failed)
    rm -f .lb-failed
    exit "$status"
fi
"""


def identity(project):
    """(name, os id) of the distribution for live-build (there is no image yet to read them from)."""
    import re
    b = _builder(project)
    ident = project.state.get("identity") or {}
    name = ident.get("name") or b["distro_name"] or project.display_name()
    os_id = ident.get("id") or ""
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,29}", os_id):
        os_id = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")[:30].strip("-") or "linux"
    return name, os_id


def hostname(project):
    """The host name of the live system: the one of the Identity page when it is a valid one."""
    import re
    host = (project.state.get("identity") or {}).get("hostname") or ""
    return host if re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", host) else identity(project)[1].replace(
        ".", "-").replace("_", "-").strip("-") or "linux"


def _builder(project):
    from disco.core.presets import normalize
    return normalize({"name": "x", "builder": project.state.get("builder") or {}})["builder"]


def config_args(project):
    """The options of `lb config` for the project."""
    from disco.core.config import settings
    b = _builder(project)
    plat = platforms.get(b["platform"])
    if plat.output != "iso":
        raise ValueError("live-build makes ISO images: {} needs the D!sco method".format(plat.name))
    if b["family"] != "debian":
        raise ValueError("live-build builds Debian: use the D!sco method for Devuan")
    cfg = settings()
    codename = cfg.suite_codenames()[b["suite"]] if b["suite"] != "sid" else "sid"
    mirror = b["mirror"] or cfg.get("debian", "mirror")
    areas = cfg.get("debian", "components")
    if codename in ("bullseye", "buster"):
        areas = " ".join(a for a in areas.split() if a != "non-free-firmware")
    flavour = plat.kernel[len("linux-image-"):]
    name, os_id = identity(project)
    from disco.core.users import Users, check_username
    live = Users(project).live()
    check_username(live["username"])
    append = "boot=live components quiet splash hostname={} username={}".format(hostname(project), live["username"])
    comp = (project.state.get("build", {}) or {}).get("compression") or cfg.get("build", "compression")
    args = ["--mode", "debian", "--system", "live", "--distribution", codename,
            "--architecture", plat.arch, "--linux-flavours", flavour,
            "--archive-areas", areas,
            "--mirror-bootstrap", mirror, "--mirror-chroot", mirror, "--mirror-binary", mirror,
            "--security", "true" if b["suite"] != "sid" else "false",
            "--updates", "true" if b["suite"] != "sid" else "false",
            "--binary-images", "iso-hybrid", "--debian-installer", "none",
            "--bootloaders", "syslinux,grub-efi" if plat.arch in ("amd64", "i386") else "grub-efi",
            "--initsystem", _initsystem(b["init"]),
            "--apt-recommends", "true", "--memtest", "none",
            "--iso-application", name, "--iso-publisher", name, "--iso-volume", project.volume_label(),
            "--image-name", os_id,
            "--bootappend-live", append,
            "--chroot-squashfs-compression-type", comp if comp in COMPRESSION else "zstd"]
    if plat.arch in ("amd64", "i386"):
        args += ["--firmware-chroot", "true", "--firmware-binary", "true"]
    return args


def _initsystem(init):
    if init not in ("systemd", "sysvinit", "runit"):
        raise ValueError("live-build cannot set up {}: choose systemd, sysvinit or runit, or use the D!sco "
                         "method".format(init))
    return init


def write_config(project):
    """Write <project>/live-build (auto scripts, package lists, includes, hooks). Returns the folder."""
    from disco.core.pkglists import Lists
    b = _builder(project)
    lb = folder(project)
    (lb / "auto").mkdir(parents=True, exist_ok=True)
    args = config_args(project)
    lines = ["#!/bin/sh", "# Written by D!sco from the project's choices; it is written again before every build.",
             "set -e", "", "lb config noauto \\"]
    lines += ["    {} \\".format(" ".join(shlex.quote(a) for a in args[i:i + 2])) for i in range(0, len(args), 2)]
    lines += ['    "${@}"', ""]
    _script(lb / "auto/config", "\n".join(lines))
    _script(lb / "auto/build", AUTO_BUILD)
    _script(lb / "auto/clean", "#!/bin/sh\nset -e\nlb clean noauto \"${@}\"\nrm -f config/binary config/bootstrap "
                               "config/chroot config/common config/source build.log\n")
    # Package lists
    pl = lb / "config/package-lists"
    if pl.exists():
        shutil.rmtree(pl)
    pl.mkdir(parents=True)
    lists = Lists(project)
    install, remove = lists.plan()
    for l in lists.all():
        if lists.is_on(l):
            inst, _rem = l.read()
            (pl / (l.path.stem + ".list.chroot")).write_text(
                "# {} (from {})\n".format(l.title, l.name) + "".join(p + "\n" for p in inst))
    if b["desktop"]:
        from disco.core import desktop as dsk
        d = dsk.desktop(b["desktop"])
        pkgs = [d["task"]] if d.get("task") else list(d.get("packages", []))
        if b["dm"]:
            pkgs += dsk.display_manager(b["dm"])["packages"]
        (pl / "05-desktop.list.chroot").write_text("# The desktop: {}\n".format(d["name"]) +
                                                   "".join(p + "\n" for p in pkgs))
    (pl / "00-live.list.chroot").write_text("# The live system\nlive-boot\nlive-config\n" + (
        "live-config-systemd\n" if b["init"] == "systemd" else "live-config-sysvinit\n"))
    # Files and scripts
    inc = lb / "config/includes.chroot"
    if inc.exists():
        shutil.rmtree(inc)
    inc.mkdir(parents=True)
    overlay = Path(project.path) / "overlay"
    if overlay.is_dir():
        from disco.core.pipeline import copy_overlay
        copy_overlay(overlay, inc)
    hooks = lb / "config/hooks/normal"
    hooks.mkdir(parents=True, exist_ok=True)
    for old in hooks.glob("*-disco-*.hook.chroot"):
        old.unlink()
    from disco.core import hooks as hk
    for i, script in enumerate(hk.hook_dirs(project)):
        if script.suffix in (".sh", ""):
            target = hooks / "{:04d}-disco-{}.hook.chroot".format(8000 + i, script.stem)
            shutil.copy2(script, target)
            target.chmod(0o755)
    _script(hooks / "8100-disco-identity.hook.chroot", _identity_hook(project))
    if remove:
        _script(hooks / "8999-disco-remove.hook.chroot",
                "#!/bin/sh\n# Packages the lists remove ('-name')\nset -e\napt-get purge -y {}\n"
                "apt-get autoremove --purge -y\n".format(" ".join(shlex.quote(p) for p in remove)))
    log.info("live-build configuration written to %s (%d packages)", lb, len(install))
    return lb


def _identity_hook(project):
    """A hook that names the system (os-release, issue, lsb-release, host name) inside the chroot."""
    from disco.core.distro import format_lsb_release, format_os_release
    name, os_id = identity(project)
    ident = project.state.get("identity") or {}
    version = ident.get("version") or "1.0"
    pretty = "{} {}".format(name, version).strip()
    osr = format_os_release({k: v for k, v in {
        "PRETTY_NAME": pretty, "NAME": name, "VERSION_ID": version, "VERSION": version, "ID": os_id,
        "ID_LIKE": "debian", "HOME_URL": ident.get("home_url", ""), "SUPPORT_URL": ident.get("support_url", ""),
        "BUG_REPORT_URL": ident.get("bug_url", "")}.items() if v})
    lsb = format_lsb_release(name, version, "", pretty)
    host = hostname(project)
    return ("#!/bin/sh\n# The name of the distribution (written by D!sco)\nset -e\n"
            "cat > /usr/lib/os-release <<'DISCO_EOF'\n{osr}DISCO_EOF\n"
            "ln -sf ../usr/lib/os-release /etc/os-release\n"
            "cat > /etc/lsb-release <<'DISCO_EOF'\n{lsb}DISCO_EOF\n"
            "printf '%s\\n' 'Welcome to {pretty_sh} - \\n \\l' '' > /etc/issue\n"
            "printf '%s\\n' 'Welcome to {pretty_sh}' > /etc/issue.net\n"
            "echo {host} > /etc/hostname\n").format(osr=osr, lsb=lsb, pretty_sh=pretty.replace("'", ""),
                                                     host=shlex.quote(host))


def _script(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def build(project, progress=None, stage=None):
    """lb clean, lb config, lb build; the ISO goes to the output folder. Returns its path."""
    stage = stage or (lambda text: log.info("== %s ==", text))
    progress = progress or (lambda pct: None)
    runner.require("lb")
    lb = write_config(project)
    stage("live-build: cleaning the previous build (the download cache stays)")
    runner.run(["lb", "clean"], cwd=lb, check=False)
    stage("live-build: lb config")
    runner.run(["lb", "config"], cwd=lb)
    progress(5)
    stage("live-build: lb build (this takes a long time)")
    runner.run(["lb", "build"], cwd=lb)
    progress(95)
    isos = sorted(lb.glob("*.iso"), key=lambda p: p.stat().st_mtime)
    if not isos:
        raise RuntimeError("lb build finished without an ISO: see {}".format(lb / "build.log"))
    from disco.core.isobuild import BuildOptions, hash_file, iso_filename
    out = Path(project.output) / iso_filename(BuildOptions.from_project(project).iso_name, project)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(isos[-1]), str(out))
    Path(str(out) + ".sha256").write_text("{}  {}\n".format(hash_file(out, "sha256"), out.name))
    project.state["last_iso"] = str(out)
    project.save()
    project.record("live-build", out.name)
    progress(100)
    log.info("live-build made %s", out)
    return out
