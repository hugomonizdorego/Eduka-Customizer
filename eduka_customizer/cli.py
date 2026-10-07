"""Command line interface: eduka-customizer <command> [options]."""

import argparse
import json
import os
import sys
from pathlib import Path

from eduka_customizer import APP_NAME, VERSION_LABEL
from eduka_customizer.core import log as logmod
from eduka_customizer.core.log import log

NO_ROOT = {"doctor", "gui", "info", "test", "download", None}


def _project(args, create=False):
    from eduka_customizer.core.project import Project
    path = args.project or os.getcwd()
    if create:
        return Project.create(path)
    return Project.open(path)


def _locked(args):
    p = _project(args)
    p.lock()
    logmod.add_file_handler(p.logs / "eduka-customizer.log")
    return p


def cmd_gui(args):
    from eduka_customizer.gui.app import run
    target = getattr(args, "target", None)
    if target and target.lower().endswith(".iso"):
        return run(args.project, iso=os.path.abspath(target))
    return run(args.project or target)


def cmd_new(args):
    from eduka_customizer.core.project import Project
    p = Project.create(args.path or args.project or os.getcwd(), name=args.name)
    p.lock()
    logmod.add_file_handler(p.logs / "eduka-customizer.log")
    if args.iso:
        from eduka_customizer.core import iso
        info = iso.extract(p, args.iso)
    elif args.bootstrap:
        from eduka_customizer.core import bootstrap
        info = bootstrap.bootstrap(p, args.bootstrap, args.arch, args.variant)
    elif args.snapshot:
        from eduka_customizer.core import snapshot
        info = snapshot.snapshot(p, args.snapshot)
    else:
        log.info("Empty project created at %s", p.path)
        return 0
    p.save()
    log.info("Project ready: %s", info.summary())
    return 0


def cmd_info(args):
    from eduka_customizer.core import distro
    p = _project(args)
    print("Project:   {}".format(p.path))
    print("Source:    {} {}".format(p.state["source"].get("kind"), p.state["source"].get("path")))
    if p.has_rootfs():
        info = distro.detect(p.rootfs)
        print("System:    {}".format(info.summary()))
        print("Suite:     {} ({})".format(info.suite, info.debian_codename))
    print("Last ISO:  {}".format(p.state.get("last_iso") or "-"))
    return 0


def cmd_shell(args):
    from eduka_customizer.core.chroot import Chroot
    p = _project(args)
    if not p.has_rootfs():
        log.error("This project has no root filesystem")
        return 1
    print("Entering the Edukasaun OS image. Type 'exit' to leave.")
    print("Everything you change here is saved to the next ISO build.")
    rc = Chroot(p.rootfs).interactive(args.command or None)
    p.mark_initramfs_dirty()
    p.record("shell")
    return rc


def cmd_run(args):
    from eduka_customizer.core import hooks
    p = _locked(args)
    hooks.run_command(p, " ".join(args.command))
    return 0


def cmd_hook(args):
    from eduka_customizer.core import hooks
    p = _locked(args)
    scripts = args.scripts or hooks.hook_dirs(p)
    for s in scripts:
        hooks.run_hook(p, s)
    return 0


def cmd_sources(args):
    from eduka_customizer.core.apt import Packages, Sources
    p = _locked(args)
    src = Sources(p.rootfs)
    if args.list:
        for f in src.files():
            print("==> {} <==".format(f.relative_to(p.rootfs)))
            print(f.read_text(errors="replace"))
        return 0
    if args.add:
        src.add_repository(args.add, args.uri, args.suites, args.components, key=args.key)
    if args.suite:
        src.set_debian(args.suite, backports=args.backports, deb_src=args.deb_src,
                       security=not args.no_security, mirror=args.mirror)
    Packages(p).update()
    return 0


def cmd_apt(args):
    from eduka_customizer.core.apt import Packages, read_package_list
    p = _locked(args)
    pk = Packages(p)
    if args.action == "install":
        pk.install(args.packages, no_recommends=args.no_recommends)
    elif args.action == "remove":
        pk.remove(args.packages)
    elif args.action == "upgrade":
        pk.upgrade()
    elif args.action == "update":
        pk.update()
    elif args.action == "deb":
        pk.install_debs(args.packages)
    elif args.action == "list":
        for name, version, _size, desc in pk.installed():
            print("{:40} {:30} {}".format(name, version, desc))
    elif args.action == "search":
        for name, desc in pk.search(" ".join(args.packages)):
            print("{:40} {}".format(name, desc))
    elif args.action == "file":
        for f in args.packages:
            inst, rem = read_package_list(f)
            pk.remove(rem)
            pk.install(inst)
    return 0


def cmd_flatpak(args):
    from eduka_customizer.core.flatpak import Flatpak, search_flathub
    if args.action == "search":
        for app_id, name, summary in search_flathub(" ".join(args.apps)):
            print("{:45} {:25} {}".format(app_id, name, summary))
        return 0
    p = _locked(args)
    fp = Flatpak(p)
    if args.action == "setup":
        fp.setup()
    elif args.action == "install":
        if args.firstboot:
            fp.set_firstboot(sorted(set(fp.firstboot_list() + args.apps)))
        else:
            fp.install(args.apps)
    elif args.action == "remove":
        if args.firstboot:
            fp.set_firstboot([a for a in fp.firstboot_list() if a not in args.apps])
        else:
            fp.uninstall(args.apps)
    elif args.action == "list":
        for row in fp.installed():
            print("\t".join(row))
        for app in fp.firstboot_list():
            print("{}\t(first boot)".format(app))
    return 0


def cmd_desktop(args):
    from eduka_customizer.core import desktop
    if args.action == "catalog":
        for d in desktop.catalog()["desktops"]:
            print("{:10} {:4} {:22} {}".format(d["id"], d["kind"], d["name"], d["description"]))
        return 0
    p = _locked(args)
    dm = desktop.DesktopManager(p)
    if args.action == "install":
        dm.install(args.name, dm_id=args.dm, remove_others=args.remove_others)
    elif args.action == "session":
        dm.set_default_session(args.name)
    elif args.action == "dm":
        dm.set_display_manager(args.name)
    elif args.action == "session-type":
        dm.set_session_type(args.name, args.type)
    elif args.action == "compositor":
        dm.set_compositor(args.name, args.preset)
    elif args.action == "sddm-theme":
        dm.set_sddm_theme(args.name)
    elif args.action == "list":
        for s in desktop.sessions(p.rootfs):
            print("{:24} {:8} {}".format(s["id"], s["type"], s["name"]))
    return 0


def cmd_eduka(args):
    from eduka_customizer.core.eduka_desktop import EdukaDesktop
    p = _locked(args)
    ed = EdukaDesktop(p)
    if args.deb:
        ed.install(args.deb)
    elif args.build_only:
        ed.fetch(args.repo, args.ref)
        print(ed.build())
    else:
        ed.fetch_build_install(args.repo, args.ref)
    if args.set:
        values = {"panel": {}, "menu": {}, "desktop": {}}
        for item in args.set:
            key, _, value = item.partition("=")
            section, _, name = key.partition(".")
            if section not in values or not name:
                raise SystemExit("Use --set panel.height=48, menu.language=pt or desktop.layout=List")
            try:
                value = json.loads(value)
            except ValueError:
                pass
            values[section][name] = value
        ed.write_defaults(values["panel"] or None, values["menu"] or None, values["desktop"] or None)
    return 0


def cmd_brand(args):
    from eduka_customizer.core.branding import Branding
    p = _locked(args)
    b = Branding(p)
    if args.what == "identity":
        ident = dict(p.state["identity"])
        for item in args.values:
            k, _, v = item.partition("=")
            ident[k] = v
        b.apply_identity(ident)
    elif args.what == "plymouth":
        theme = args.values[0] if args.values else ""
        if os.path.exists(theme):
            theme = b.import_plymouth(theme)
        b.set_plymouth(theme)
    elif args.what == "plymouth-generate":
        name, logo = args.values[0], args.values[1]
        b.set_plymouth(b.generate_plymouth(name, logo, *args.values[2:4]))
    elif args.what == "wallpaper":
        b.set_wallpaper(args.values[0])
    elif args.what == "login":
        b.set_login_screen(background=args.values[0] if args.values else None)
    elif args.what == "locale":
        default, tz, kb = (args.values + ["en_US.UTF-8", "Asia/Dili", "us"][len(args.values):])[:3]
        b.apply_locale(default, [], tz, kb)
    return 0


def cmd_branding(args):
    from dataclasses import asdict
    from eduka_customizer.core.distrobrand import BrandingSpec, DistroBranding
    p = _locked(args)
    db = DistroBranding(p)
    spec = BrandingSpec.from_project(p)
    for key in ("logo", "wallpaper", "login_background", "grub_background", "accent", "dark"):
        v = getattr(args, key, None)
        if v:
            setattr(spec, key, os.path.abspath(v) if key not in ("accent", "dark") else v)
    if args.no_grub_name:
        spec.grub_name = False
    if args.action == "apply":
        for d in db.apply(spec, with_keyring=args.keyring, email=args.email or ""):
            print(d)
    elif args.action == "generate":
        print(db.generate(spec))
    elif args.action == "build":
        debs = db.build()
        db.install(debs)
        print("\n".join(str(d) for d in debs))
    elif args.action == "key":
        print(db.generate_key(spec, args.email or "archive@{}.org".format(spec.os_id)))
    elif args.action == "show":
        print(json.dumps(asdict(spec), indent=2))
        print("Installed:", db.installed())
    return 0


def cmd_workshop(args):
    from eduka_customizer.core.workshop import Workshop
    p = _locked(args)
    ws = Workshop(p)
    if args.action == "open":
        print(ws.open(args.package))
    elif args.action == "build":
        print(ws.build(args.package, hold=not args.no_hold))
    elif args.action == "restore":
        ws.restore(args.package)
    elif args.action == "list":
        for name in ws.opened():
            print(name, ws.path(name))
    return 0


def cmd_themes(args):
    from eduka_customizer.core.themes import THEME_PACKS, Themes
    p = _locked(args)
    th = Themes(p)
    if args.action == "list":
        print("GTK:    ", ", ".join(th.gtk_themes()))
        print("Icons:  ", ", ".join(th.icon_themes()))
        print("Cursors:", ", ".join(th.cursor_themes()))
        print("Current:", th.current())
        print("Packs:  ", ", ".join(p for p, _k, _t in THEME_PACKS))
    elif args.action == "apply":
        th.apply(args.gtk or "", args.icons or "", args.cursor or "", args.font or "", args.dark)
    elif args.action == "packs":
        ok, missing = th.install_packs(args.items)
        print("installed:", " ".join(ok), "| not available:", " ".join(missing))
    elif args.action == "import":
        for item in args.items:
            print(th.import_theme(item))
    return 0


def cmd_build(args):
    from eduka_customizer.core.isobuild import BuildOptions, build
    p = _locked(args)
    opts = BuildOptions.from_project(p)
    for name in ("compression", "level", "volume_label", "iso_name", "boot_mode", "initramfs"):
        v = getattr(args, name, None)
        if v is not None:
            setattr(opts, name, v)
    if args.reuse_squashfs:
        opts.reuse_squashfs = True
    if args.keep_installer:
        opts.remove_installer = False
    out = build(p, opts)
    print(out)
    return 0


def cmd_test(args):
    from eduka_customizer.core import qemu
    p = _project(args)
    proc = qemu.start(p, args.iso, firmware=args.firmware, memory=args.memory, cpus=args.cpus,
                      disk=args.disk)
    return proc.wait()


def cmd_live(args):
    from eduka_customizer.core.livesession import LiveSession
    p = _locked(args)
    s = LiveSession(p)
    s.start(args.session, args.resolution, args.mode)
    try:
        s.wait()
    except KeyboardInterrupt:
        pass
    finally:
        s.stop()
    return 0


def cmd_recipe(args):
    from eduka_customizer.core import recipe
    p = _locked(args)
    if args.action == "apply":
        recipe.apply(p, args.file, build=not args.no_build)
    else:
        data = recipe.export(p)
        text = json.dumps(data, indent=2, ensure_ascii=False)
        if args.file:
            Path(args.file).write_text(text + "\n")
        else:
            print(text)
    return 0


def cmd_clean(args):
    import shutil
    from eduka_customizer.core.chroot import Chroot, safe_rmtree, unmount_all
    p = _project(args)
    Chroot(p.rootfs).force_release()
    unmount_all(p.path)
    if args.unmount_only:
        return 0
    if args.all:
        for d in (p.rootfs, p.isodir, p.cache, p.bootdir):
            if d.exists():
                log.info("Removing %s", d)
                safe_rmtree(d)
    else:
        if p.cache.exists():
            shutil.rmtree(p.cache)
        p.cache.mkdir()
    return 0


def cmd_doctor(args):
    from eduka_customizer.core import doctor
    host = doctor.host_info()
    print("Host system: {}".format(host["distro"].summary()))
    if not host["supported"]:
        print("  Note: fine as a build computer. Only 'snapshot this computer' needs Debian or "
              "Edukasaun OS.")
    print("Root: {}   KVM: {}".format("yes" if host["root"] else "no", "yes" if host["kvm"] else "no"))
    for r in doctor.check():
        print("  [{}] {:52} {:24} {}".format("ok" if r["ok"] else ("!!" if r["required"] else "--"),
                                            r["item"], r["package"], r["purpose"]))
    missing = doctor.missing_packages()
    if missing:
        print("\nInstall the missing tools with:\n  sudo apt install " + " ".join(missing))
        if args.fix:
            doctor.install_missing(missing)
    print("\nLogs: {}  (errors: {})".format(logmod.DEBUG_LOG, logmod.ERROR_LOG))
    return 0


def cmd_download(args):
    from eduka_customizer.core import download
    if args.list or not args.file:
        for name, _sha in download.list_images(args.suite):
            print(name)
        return 0
    print(download.download(args.suite, args.file, args.output or os.getcwd()))
    return 0


def build_parser():
    ap = argparse.ArgumentParser(prog="eduka-customizer",
                                 description="{} {} - ISO builder for Edukasaun OS (Debian stable, "
                                             "testing and sid).".format(APP_NAME, VERSION_LABEL))
    ap.add_argument("-p", "--project", help="project directory (default: current directory)")
    ap.add_argument("-D", "--debug", action="store_true", help="show debug messages")
    ap.add_argument("-V", "--version", action="version", version="{} {}".format(APP_NAME, VERSION_LABEL))
    sub = ap.add_subparsers(dest="command")

    s = sub.add_parser("gui", help="start the graphical interface (default)")
    s.add_argument("target", nargs="?", help="project folder or ISO image to open")
    s.set_defaults(func=cmd_gui)

    s = sub.add_parser("new", help="create a project from an ISO, a new Debian base or this system")
    s.add_argument("path", nargs="?", default=None)
    s.add_argument("--name", default="Edukasaun OS")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--iso", help="Debian or Edukasaun OS live ISO")
    g.add_argument("--bootstrap", choices=["stable", "testing", "sid"])
    g.add_argument("--snapshot", choices=["dist", "backup"], help="copy the running system")
    s.add_argument("--arch", default="amd64")
    s.add_argument("--variant", default="important", choices=["important", "standard", "minbase"])
    s.set_defaults(func=cmd_new)

    sub.add_parser("info", help="show project information").set_defaults(func=cmd_info)

    s = sub.add_parser("shell", help="open an interactive shell inside the image")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_shell)

    s = sub.add_parser("run", help="run a command inside the image")
    s.add_argument("command", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_run)

    s = sub.add_parser("hook", help="run hook scripts inside the image (default: <project>/hooks/*)")
    s.add_argument("scripts", nargs="*")
    s.set_defaults(func=cmd_hook)

    s = sub.add_parser("sources", help="APT sources (Debian suite, extra repositories)")
    s.add_argument("--suite", choices=["stable", "testing", "sid"])
    s.add_argument("--mirror")
    s.add_argument("--backports", action="store_true")
    s.add_argument("--deb-src", action="store_true")
    s.add_argument("--no-security", action="store_true")
    s.add_argument("--add", metavar="NAME", help="add a repository called NAME")
    s.add_argument("--uri")
    s.add_argument("--suites", default="")
    s.add_argument("--components", default="main")
    s.add_argument("--key", help="key URL or file for --add")
    s.add_argument("--list", action="store_true")
    s.set_defaults(func=cmd_sources)

    s = sub.add_parser("apt", help="manage packages inside the image")
    s.add_argument("action", choices=["install", "remove", "upgrade", "update", "deb", "list",
                                      "search", "file"])
    s.add_argument("packages", nargs="*")
    s.add_argument("--no-recommends", action="store_true")
    s.set_defaults(func=cmd_apt)

    s = sub.add_parser("flatpak", help="Flatpak / Flathub applications")
    s.add_argument("action", choices=["setup", "install", "remove", "list", "search"])
    s.add_argument("apps", nargs="*")
    s.add_argument("--firstboot", action="store_true", help="install on first boot instead")
    s.set_defaults(func=cmd_flatpak)

    s = sub.add_parser("desktop", help="desktop environments, window managers and sessions")
    s.add_argument("action", choices=["catalog", "install", "session", "dm", "list", "session-type",
                                      "compositor", "sddm-theme"])
    s.add_argument("name", nargs="?")
    s.add_argument("--dm")
    s.add_argument("--type", choices=["x11", "wayland"], default="x11", help="for session-type")
    s.add_argument("--preset", choices=["light", "shadows", "glass", "off"], default="shadows",
                   help="picom effects for compositor")
    s.add_argument("--remove-others", action="store_true")
    s.set_defaults(func=cmd_desktop)

    s = sub.add_parser("eduka-desktop", help="build and install Eduka-Desktop")
    s.add_argument("--repo")
    s.add_argument("--ref")
    s.add_argument("--deb")
    s.add_argument("--build-only", action="store_true")
    s.add_argument("--set", action="append", metavar="SECTION.KEY=VALUE",
                   help="default setting for new users, e.g. panel.height=48")
    s.set_defaults(func=cmd_eduka)

    s = sub.add_parser("brand", help="identity, Plymouth, wallpaper, login screen, locale")
    s.add_argument("what", choices=["identity", "plymouth", "plymouth-generate", "wallpaper",
                                    "login", "locale"])
    s.add_argument("values", nargs="*")
    s.set_defaults(func=cmd_brand)

    s = sub.add_parser("branding", help="full distro branding (base-files, lsb-release, logos, GRUB, ...)")
    s.add_argument("action", choices=["apply", "generate", "build", "key", "show"])
    s.add_argument("--logo")
    s.add_argument("--wallpaper")
    s.add_argument("--login-background", dest="login_background")
    s.add_argument("--grub-background", dest="grub_background")
    s.add_argument("--accent")
    s.add_argument("--dark")
    s.add_argument("--keyring", action="store_true", help="also create and install <id>-archive-keyring")
    s.add_argument("--email")
    s.add_argument("--no-grub-name", action="store_true")
    s.set_defaults(func=cmd_branding)

    s = sub.add_parser("workshop", help="edit an installed Debian package directly")
    s.add_argument("action", choices=["open", "build", "restore", "list"])
    s.add_argument("package", nargs="?")
    s.add_argument("--no-hold", action="store_true")
    s.set_defaults(func=cmd_workshop)

    s = sub.add_parser("themes", help="GTK/icon/cursor themes and fonts")
    s.add_argument("action", choices=["list", "apply", "packs", "import"])
    s.add_argument("items", nargs="*")
    s.add_argument("--gtk")
    s.add_argument("--icons")
    s.add_argument("--cursor")
    s.add_argument("--font")
    s.add_argument("--dark", action="store_true")
    s.set_defaults(func=cmd_themes)

    s = sub.add_parser("build", help="build the ISO image")
    s.add_argument("--compression", choices=["zstd", "xz", "gzip", "lz4", "lzo"])
    s.add_argument("--level", type=int)
    s.add_argument("--volume-label")
    s.add_argument("--iso-name")
    s.add_argument("--boot-mode", choices=["auto", "replay", "generate"])
    s.add_argument("--initramfs", choices=["auto", "always", "never"])
    s.add_argument("--reuse-squashfs", action="store_true")
    s.add_argument("--keep-installer", action="store_true",
                   help="keep Debian-Installer boot entries")
    s.set_defaults(func=cmd_build)

    s = sub.add_parser("test", help="boot the ISO in QEMU")
    s.add_argument("--iso")
    s.add_argument("--firmware", choices=["bios", "uefi", "secureboot"], default="uefi")
    s.add_argument("--memory")
    s.add_argument("--cpus")
    s.add_argument("--disk", action="store_true", help="attach a virtual disk to test installation")
    s.set_defaults(func=cmd_test)

    s = sub.add_parser("live", help="live edit: run the image desktop in a window")
    s.add_argument("--session")
    s.add_argument("--resolution", default="1280x800")
    s.add_argument("--mode", choices=["skel", "root", "sandbox"], default="skel")
    s.set_defaults(func=cmd_live)

    s = sub.add_parser("recipe", help="apply or export a JSON recipe")
    s.add_argument("action", choices=["apply", "export"])
    s.add_argument("file", nargs="?")
    s.add_argument("--no-build", action="store_true")
    s.set_defaults(func=cmd_recipe)

    s = sub.add_parser("clean", help="unmount everything and remove caches")
    s.add_argument("--unmount-only", action="store_true")
    s.add_argument("--all", action="store_true", help="also remove rootfs and ISO tree")
    s.set_defaults(func=cmd_clean)

    s = sub.add_parser("doctor", help="check host tools")
    s.add_argument("--fix", action="store_true", help="install missing packages with apt")
    s.set_defaults(func=cmd_doctor)

    s = sub.add_parser("download", help="download an official Debian live ISO")
    s.add_argument("--suite", choices=["stable", "testing"], default="stable")
    s.add_argument("--list", action="store_true")
    s.add_argument("--output")
    s.add_argument("file", nargs="?")
    s.set_defaults(func=cmd_download)
    return ap


def main(argv=None):
    ap = build_parser()
    args = ap.parse_args(argv)
    logmod.setup_console(args.debug)
    logmod.setup_debug_log(args.command or "gui")
    if not getattr(args, "func", None):
        args.func = cmd_gui
        args.command = "gui"
    if args.command not in NO_ROOT and os.geteuid() != 0:
        log.error("This command needs administrator rights. Run it with sudo or pkexec.")
        return 2
    from eduka_customizer.core import runner
    from eduka_customizer.core.distro import UnsupportedDistro
    from eduka_customizer.core.project import ProjectLocked
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        runner.CANCEL.set()
        log.error("Interrupted")
        return 130
    except (UnsupportedDistro, ProjectLocked, runner.CommandError, runner.Cancelled,
            FileNotFoundError, ValueError, RuntimeError) as e:
        log.error("%s", e, exc_info=True)
        if args.debug:
            raise
        return 1
    except Exception as e:
        log.critical("Unexpected error: %s (details in %s)", e, logmod.ERROR_LOG, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
