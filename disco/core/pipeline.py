"""Automated builds from the command line (disco step, disco build-all), step by step:

  1. Prepare      check the choices and this computer, write the first package lists
  2. Build base   a new Debian or Devuan system (mmdebstrap or debootstrap), its init
                  system and its name
  3. Packages     the desktop, the package lists and the installer
  4. Overlay      copy <project>/overlay into the system, run <project>/hooks/*.sh
  5. Make image   the ISO (squashfs + xorriso, or live-build) or the SD-card image

"Build all" runs them in this order and starts again where it stopped. Every
step can also be run on its own (again), for example after changing a list.
"""

import os
import shutil
import stat
import time
from pathlib import Path

from disco.core import platforms
from disco.core.log import log

STEPS = [
    ("prepare", "Prepare", "Checks the choices and this computer, writes the first package lists."),
    ("base", "Build base", "Makes a new Debian or Devuan system with debootstrap/mmdebstrap."),
    ("packages", "Install packages", "Installs the desktop, the package lists and the installer."),
    ("overlay", "Overlay & scripts", "Copies the overlay folder into the system and runs your scripts."),
    ("image", "Make image", "Builds the ISO, or the SD-card image for boards."),
]
FOLDERS = {"lists": "package lists (NN-name.list)", "overlay": "files copied into the system as they are",
           "hooks": "your scripts (*.sh), run inside the system in name order",
           "debs": "your own .deb packages (installed when the installer is 'my own packages')"}


class Pipeline:
    def __init__(self, project, progress=None, stage=None):
        self.project = project
        self.progress = progress or (lambda pct: None)
        self.stage = stage or (lambda text: log.info("== %s ==", text))

    # Choices ---------------------------------------------------------------------------------
    @property
    def builder(self):
        from disco.core.presets import normalize
        b = self.project.state.get("builder") or {}
        return normalize({"name": "x", "builder": b})["builder"]

    @property
    def platform(self):
        return platforms.get(self.builder["platform"])

    def _done(self, step):
        self.project.state.setdefault("pipeline", {})[step] = time.strftime("%Y-%m-%d %H:%M")
        self.project.save()

    def status(self):
        """{step: time it was last finished or ''}."""
        done = self.project.state.get("pipeline", {})
        return {k: done.get(k, "") for k, _n, _d in STEPS}

    # 1. Prepare ------------------------------------------------------------------------------
    def check(self):
        """[(ok, text)] about the choices and this computer."""
        b, p = self.builder, self.platform
        out = []
        from disco.core.apt import devuan_codenames
        from disco.core.config import settings
        if b["family"] == "devuan":
            codename = devuan_codenames().get(b["suite"], b["suite"])
        else:
            codename = settings().suite_codenames().get(b["suite"], b["suite"]) if b["suite"] != "sid" else "sid"
        ok, why = platforms.release_ok(p, codename)
        out.append((ok, why or "{} {} ({}) can be built for {}".format(b["family"].capitalize(), b["suite"],
                                                                      codename, p.name)))
        if b["method"] == "live-build":
            from disco.core import livebuild
            lb_ok, lb_why = livebuild.usable()
            out.append((lb_ok, lb_why))
            if p.output != "iso":
                out.append((False, "live-build makes ISO images only: use the D!sco method for {}".format(p.name)))
            if b["family"] == "devuan":
                out.append((False, "live-build is Debian's tool: use the D!sco method for Devuan"))
            if b["init"] == "openrc":
                out.append((False, "live-build cannot set up OpenRC: choose systemd, sysvinit or runit, or use "
                                   "the D!sco method"))
        for tool, package, why in platforms.host_requirements(p, b["method"]):
            out.append((False, "{} is missing ({}): sudo apt install {}".format(tool, why, package)))
        if platforms.is_foreign(p.arch):
            out.append((platforms.can_run(p.arch),
                        "{} programs run through qemu-user on this {} computer".format(p.arch, platforms.host_arch())
                        if platforms.can_run(p.arch) else
                        "{} programs cannot run here yet: Prepare switches qemu-user on (binfmt)".format(p.arch)))
        if b["installer"] == "debs":
            debs = sorted((Path(self.project.path) / "debs").glob("*.deb"))
            out.append((bool(debs), "{} own package(s) in the debs folder".format(len(debs)) if debs else
                        "Put your installer's .deb files into {}".format(Path(self.project.path) / "debs")))
        if b["desktop"]:
            from disco.core import desktop as dsk
            try:
                dsk.desktop(b["desktop"])
                if b["init"] != "systemd":
                    from disco.core.initsystem import NEEDS_SYSTEMD
                    names = {v for v in NEEDS_SYSTEMD.values()}
                    if dsk.desktop(b["desktop"])["name"] in names:
                        out.append((False, "{} needs systemd: choose another desktop or systemd".format(
                            dsk.desktop(b["desktop"])["name"])))
            except KeyError:
                out.append((False, "Unknown desktop: {}".format(b["desktop"])))
        return out

    def prepare(self):
        self.stage("Preparing the project")
        p = self.project
        for name in FOLDERS:
            (Path(p.path) / name).mkdir(exist_ok=True)
        readme = Path(p.path) / "overlay" / "README.txt"
        if readme.is_symlink():
            readme.unlink()          # never write through a link put in a folder of the user
        if not readme.exists():
            readme.write_text("Files in this folder are copied into the system as they are, for example\n"
                              "overlay/etc/skel/.bashrc becomes /etc/skel/.bashrc (owner root).\n"
                              "This README.txt itself is not copied.\n")
        b, plat = self.builder, self.platform
        from disco.core.pkglists import Lists
        Lists(p).ensure_defaults(plat, b["profile"] or None, b["installer"])
        if platforms.is_foreign(plat.arch) and not platforms.can_run(plat.arch):
            ok, how = platforms.enable_binfmt(plat.arch)
            if not ok:
                raise RuntimeError(how)
        p.state["name"] = p.state.get("name") or b["distro_name"]
        p.save()
        problems = [text for ok, text in self.check() if not ok]
        self._done("prepare")
        return problems

    # 2. Base -------------------------------------------------------------------------------------
    def base(self):
        b, p = self.builder, self.project
        if b["method"] == "live-build":
            raise RuntimeError("With live-build the whole system is made by 'Make image' (lb build)")
        self.stage("Building the base system ({} {}, {})".format(b["family"].capitalize(), b["suite"],
                                                                  self.platform.name))
        from disco.core.bootstrap import bootstrap
        bootstrap(p, suite=b["suite"], variant=b["variant"], mirror=b["mirror"] or None,
                  devuan=b["family"] == "devuan", platform_id=b["platform"])
        self.progress(40)
        from disco.core import initsystem
        if b["init"] != initsystem.current(p.rootfs):
            self.stage("Switching the init system to {}".format(initsystem.INITS[b["init"]][0]))
            initsystem.use(p, b["init"])
        self.progress(70)
        ident = dict(p.state.get("identity") or {})
        if not ident.get("name") and b["distro_name"]:
            self.stage("Naming the system {}".format(b["distro_name"]))
            from disco.core.branding import Branding
            ident["name"] = b["distro_name"]
            br = Branding(p)
            with br.chroot:
                br.apply_identity(ident)
        p.save()
        self._done("base")
        self.progress(100)

    # 3. Packages ---------------------------------------------------------------------------------
    def packages(self):
        b, p = self.builder, self.project
        if not p.has_rootfs():
            raise RuntimeError("Build the base system first")
        from disco.core.pkglists import Lists
        lists = Lists(p)
        if not lists.all():
            lists.ensure_defaults(self.platform, b["profile"] or None, b["installer"])
        if b["desktop"]:
            from disco.core import desktop as dsk
            if b["desktop"] not in dsk.installed_desktops(p.rootfs):
                self.stage("Installing the desktop {}".format(dsk.desktop(b["desktop"])["name"]))
                dsk.DesktopManager(p).install(b["desktop"], b["dm"] or None)
        self.progress(40)
        installed, skipped = lists.install(stage=self.stage)
        self.progress(80)
        if b["installer"] == "debs":
            debs = sorted((Path(p.path) / "debs").glob("*.deb"))
            if debs:
                self.stage("Installing your own packages ({})".format(len(debs)))
                from disco.core.apt import Packages
                Packages(p).install_debs(debs)
        elif b["installer"] == "calamares" and self.platform.output == "iso":
            from disco.core.calamares import Calamares
            cal = Calamares(p)
            if not cal.installed():
                self.stage("Installing the Calamares installer")
                cal.install()
        elif b["installer"] == "none":
            from disco.core.calamares import Calamares
            cal = Calamares(p)
            if cal.installed():
                self.stage("Removing the Calamares installer (live system only)")
                cal.remove()
        self._done("packages")
        self.progress(100)
        return installed, skipped

    # 4. Overlay and scripts ----------------------------------------------------------------------
    def overlay(self):
        p = self.project
        if not p.has_rootfs():
            raise RuntimeError("Build the base system first")
        src = Path(p.path) / "overlay"
        copied = copy_overlay(src, p.rootfs) if src.is_dir() else 0
        if copied:
            self.stage("Copied {} file(s) from the overlay folder".format(copied))
        from disco.core import hooks
        scripts = [s for s in hooks.hook_dirs(p) if s.suffix in (".sh", "")]
        for i, script in enumerate(scripts):
            self.stage("Running {}".format(script.name))
            hooks.run_hook(p, script)
            self.progress(int(100 * (i + 1) / max(1, len(scripts))))
        self._done("overlay")
        return copied, len(scripts)

    # 5. Image --------------------------------------------------------------------------------------
    def image(self, opts=None):
        b, p = self.builder, self.project
        if b["method"] == "live-build":
            from disco.core import livebuild
            out = livebuild.build(p, progress=self.progress, stage=self.stage)
        elif self.platform.output == "img":
            from disco.core import imgbuild
            out = imgbuild.build(p, opts, self.progress, self.stage)
        else:
            from disco.core import isobuild
            out = isobuild.build(p, opts, self.progress, self.stage)
        self._done("image")
        return out

    # Everything ------------------------------------------------------------------------------------
    def run(self, step):
        return {"prepare": self.prepare, "base": self.base, "packages": self.packages, "overlay": self.overlay,
                "image": self.image}[step]()

    def build_all(self, rebuild_base=False):
        """All steps; the base is only made again when asked (or when there is none)."""
        b, p = self.builder, self.project
        problems = self.prepare()
        if problems:
            raise RuntimeError("Fix these first:\n- " + "\n- ".join(problems))
        if b["method"] == "live-build":
            return self.image()
        if rebuild_base or not p.has_rootfs():
            self.base()
        self.packages()
        self.overlay()
        return self.image()


def copy_overlay(src, rootfs):
    """Copy *src* into the system (owner root, modes kept, symbolic links kept). Returns the number of files."""
    src, rootfs = Path(src), Path(rootfs).resolve()
    count = 0
    for top, dirs, files in os.walk(src):
        rel = Path(top).relative_to(src)
        dest_dir = _inside(rootfs, rel)
        if not dest_dir.exists():
            dest_dir.mkdir(parents=True)
            os.chown(dest_dir, 0, 0) if os.geteuid() == 0 else None
            dest_dir.chmod(stat.S_IMODE(os.stat(top).st_mode) | 0o755)
        for d in list(dirs):
            if Path(top, d).is_symlink():
                files.append(d)
                dirs.remove(d)
        for name in files:
            if rel == Path(".") and name == "README.txt":
                continue
            s = Path(top, name)
            d = _inside(rootfs, rel / name)
            if d.is_symlink() or (d.exists() and not d.is_dir()):
                d.unlink()
            if s.is_symlink():
                os.symlink(os.readlink(s), d)
                if os.geteuid() == 0:
                    os.lchown(d, 0, 0)
            else:
                shutil.copy2(s, d)
                if os.geteuid() == 0:
                    os.chown(d, 0, 0)
            count += 1
    return count


def _inside(rootfs, rel):
    """rootfs/rel, refusing any path that would leave the system (.. or symbolic links)."""
    if str(rel) in (".", ""):
        return rootfs
    target = rootfs / rel
    parent = target.parent.resolve()
    if parent != rootfs and rootfs not in parent.parents:
        raise RuntimeError("The overlay path {} would leave the system".format(rel))
    return target


def build_all(project, progress=None, stage=None, rebuild_base=False):
    return Pipeline(project, progress, stage).build_all(rebuild_base)
