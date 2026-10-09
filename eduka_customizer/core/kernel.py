"""Kernels of the image: Debian, backports, third-party repositories and .deb files.

Also the GRUB defaults of the installed system (/etc/default/grub.d), the
initramfs, DKMS modules and firmware.
"""

import re
import shutil
from pathlib import Path

from eduka_customizer.core import cleanup
from eduka_customizer.core.apt import APT, Packages, Sources, is_installed_status, parse_deb822
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

GRUB_DROPIN = "etc/default/grub.d/95-eduka-customizer.cfg"
GRUB_KEYS = ["GRUB_DEFAULT", "GRUB_SAVEDEFAULT", "GRUB_TIMEOUT", "GRUB_TIMEOUT_STYLE", "GRUB_CMDLINE_LINUX_DEFAULT",
             "GRUB_CMDLINE_LINUX", "GRUB_DISABLE_OS_PROBER", "GRUB_GFXMODE", "GRUB_DISABLE_RECOVERY"]

# id: (title, description, repository or None, packages, architectures)
THIRD_PARTY = {
    "backports": ("Debian backports", "Newer Debian kernel for stable (official, signed for Secure Boot).",
                  None, ["linux-image-{arch}", "linux-headers-{arch}"], None),
    "liquorix": ("Liquorix", "Desktop and gaming tuned kernel (liquorix.net). Not signed for Secure Boot.",
                 {"name": "liquorix", "uri": "https://liquorix.net/debian", "suite": "{codename}",
                  "components": "main", "key": "https://liquorix.net/liquorix-keyring.gpg"},
                 ["linux-image-liquorix-amd64", "linux-headers-liquorix-amd64"], ["amd64"]),
    "xanmod": ("XanMod (x86-64-v3)", "Performance kernel (xanmod.org) for CPUs from about 2015 on. "
               "Not signed for Secure Boot.",
               {"name": "xanmod", "uri": "http://deb.xanmod.org", "suite": "{codename}",
                "components": "main non-free", "key": "https://dl.xanmod.org/archive.key"},
               ["linux-xanmod-x64v3"], ["amd64"]),
    "xanmod-lts": ("XanMod LTS (x86-64-v2)", "Long-term XanMod kernel for older 64-bit CPUs.",
                   {"name": "xanmod", "uri": "http://deb.xanmod.org", "suite": "{codename}",
                    "components": "main non-free", "key": "https://dl.xanmod.org/archive.key"},
                   ["linux-xanmod-lts-x64v2"], ["amd64"]),
}

FIRMWARE = ["firmware-linux", "firmware-linux-nonfree", "firmware-misc-nonfree", "firmware-iwlwifi",
            "firmware-realtek", "firmware-atheros", "firmware-brcm80211", "firmware-sof-signed",
            "firmware-amd-graphics", "intel-microcode", "amd64-microcode"]

_VERSION = re.compile(r"^[A-Za-z0-9.+~_-]+$")


class Kernels:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.chroot = Chroot(project.rootfs)
        self.pkgs = Packages(project)

    # Information --------------------------------------------------------------
    def _status(self):
        p = self.rootfs / "var/lib/dpkg/status"
        if not p.exists():
            return []
        return [s for s in parse_deb822(p.read_text(errors="replace"))
                if is_installed_status(s.get("Status", ""))]

    def installed(self):
        """Installed kernels, oldest first."""
        pkgs = {}
        meta = []
        held = self.held()
        for st in self._status():
            name = st.get("Package", "")
            m = re.match(r"^linux-image-(?:unsigned-)?(\d[^\s]*)$", name)
            if m:
                pkgs[m.group(1)] = st
            elif name.startswith("linux-image-") or name.startswith("linux-xanmod"):
                meta.append({"package": name, "version": st.get("Version", ""), "held": name in held})
        boot = self.project.state.get("boot", {}).get("kernel") or ""
        versions = cleanup.kernels(self.rootfs)
        result = []
        for v in versions:
            st = pkgs.get(v, {})
            vm = self.rootfs / "boot" / ("vmlinuz-" + v)
            result.append({
                "version": v, "package": st.get("Package", ""),
                "package_version": st.get("Version", ""),
                "size": int(st.get("Installed-Size", "0") or 0) * 1024 or (vm.stat().st_size if vm.exists() else 0),
                "initrd": (self.rootfs / "boot" / ("initrd.img-" + v)).exists(),
                "origin": "Debian" if "debian.org" in st.get("Maintainer", "") else (
                    st.get("Maintainer", "").split("<")[0].strip() or "copied by hand"),
                "iso": (v == boot) or (not boot and v == (versions[-1] if versions else "")),
                "headers": (self.rootfs / "usr/src" / ("linux-headers-" + v)).is_dir(),
                "held": st.get("Package", "") in held,
                "description": st.get("Description", "").split("\n")[0],
            })
        return result, meta

    def held(self):
        out = set()
        for st in self._status():
            if st.get("Status", "").startswith("hold "):
                out.add(st.get("Package"))
        return out

    def available(self):
        """Kernel packages APT can install: (name, description)."""
        found = self.pkgs.search("^linux-image-", limit=400)
        return [(n, d) for n, d in found if n.startswith("linux-image-") and "-dbg" not in n]

    # Install -----------------------------------------------------------------------
    def install(self, packages, headers=False, target_release=None):
        packages = list(packages)
        if headers:
            extra = []
            for p in packages:
                if p.startswith("linux-image-"):
                    extra.append("linux-headers-" + p[len("linux-image-"):])
            packages += extra
        if target_release:
            if not re.match(r"^[a-z0-9-]+$", target_release):
                raise ValueError("Invalid target release")
            with self.chroot:
                self.pkgs.recover()
                self.pkgs.update()
                avail = self.pkgs.available(packages)
                packages = [p for p in packages if p in avail or not p.startswith("linux-headers-")]
                self.chroot.run(APT + ["install", "-t", target_release] + packages)
            self.project.mark_initramfs_dirty()
            self.project.record("kernel-install", " ".join(packages) + " (" + target_release + ")")
        else:
            if headers:
                with self.chroot:
                    self.pkgs.update()
                    avail = self.pkgs.available(packages)
                packages = [p for p in packages if p in avail or not p.startswith("linux-headers-")]
            self.pkgs.install(packages)
            self.project.record("kernel-install", " ".join(packages))

    def install_third_party(self, preset, headers=True):
        if preset not in THIRD_PARTY:
            raise ValueError("Unknown kernel source: {}".format(preset))
        title, _desc, repo, packages, arches = THIRD_PARTY[preset]
        from eduka_customizer.core import distro
        info = distro.detect(self.rootfs)
        arch = info.arch or self.project.distro.arch or "amd64"
        if arches and arch not in arches:
            raise ValueError("{} is only available for {}".format(title, ", ".join(arches)))
        codename = info.debian_codename or info.codename
        if not codename:
            raise RuntimeError("Unknown Debian codename of the image")
        packages = [p.format(arch=arch) for p in packages if headers or "headers" not in p]
        if preset == "backports":
            if info.suite in ("testing", "sid") or codename == "sid":
                raise ValueError("Backports exist only for Debian stable")
            suite = codename + "-backports"
            comps = self._debian_components()
            Sources(self.rootfs).add_repository("debian-backports", "http://deb.debian.org/debian", suite, comps,
                                                key=None)
            self._signed_by_debian("debian-backports")
            self.install(packages, target_release=suite)
        else:
            Sources(self.rootfs).add_repository(repo["name"], repo["uri"], repo["suite"].format(codename=codename),
                                                repo["components"], key=repo["key"])
            self.install(packages)
        log.info("%s kernel installed", title)

    def _debian_components(self):
        for p in (self.rootfs / "etc/apt/sources.list.d").glob("*.sources"):
            for st in parse_deb822(p.read_text(errors="replace")):
                if "deb.debian.org" in st.get("URIs", "") and st.get("Components"):
                    return st["Components"]
        return "main contrib non-free non-free-firmware"

    def _signed_by_debian(self, name):
        p = self.rootfs / "etc/apt/sources.list.d" / (name + ".sources")
        key = "/usr/share/keyrings/debian-archive-keyring.gpg"
        if p.exists() and (self.rootfs / key.lstrip("/")).exists() and "Signed-By" not in p.read_text():
            p.write_text(p.read_text().rstrip("\n") + "\nSigned-By: {}\n".format(key))

    def add_repository(self, name, uri, suite, components, key, packages):
        Sources(self.rootfs).add_repository(name, uri, suite, components, key=key or None)
        self.install(packages)

    def install_debs(self, files):
        files = [Path(f) for f in files]
        bad = [f.name for f in files if not re.match(r"^linux-(image|headers|modules|firmware|libc)", f.name)]
        if bad:
            log.warning("These files do not look like kernel packages: %s", ", ".join(bad))
        self.pkgs.install_debs(files)
        self.project.record("kernel-deb", " ".join(f.name for f in files))

    # Third-party repositories typed in the console --------------------------------------
    # Repositories added in the kernel console are temporary: they stay in the system only
    # when a kernel from them is installed; otherwise they are removed again (with their
    # keys and package lists), so a test never ends up in the ISO.
    APT_DIRS = ("etc/apt/sources.list.d", "etc/apt/keyrings", "etc/apt/trusted.gpg.d", "usr/share/keyrings")

    def _apt_files(self):
        out = set()
        for d in self.APT_DIRS:
            base = self.rootfs / d
            if base.is_dir():
                out |= {str(p.relative_to(self.rootfs)) for p in base.iterdir() if p.is_file()}
        return out

    def _sources_list_lines(self):
        p = self.rootfs / "etc/apt/sources.list"
        return p.read_text(errors="replace").splitlines() if p.exists() else []

    def temp_files(self):
        return list(self.project.state.get("kernel", {}).get("temp_repos", []))

    def _set_temp(self, files):
        self.project.state.setdefault("kernel", {})["temp_repos"] = sorted(set(files))
        self.project.save()

    def console(self, command):
        """Run a shell command inside the image (as root) and return its output. Repository
        files and keys it creates are remembered as temporary."""
        if not command.strip():
            return ""
        before, lines = self._apt_files(), self._sources_list_lines()
        with self.chroot:
            out = self.chroot.output(["/bin/bash", "-c", command + " 2>&1"], check=False) or ""
        new = sorted(self._apt_files() - before)
        added = [l for l in self._sources_list_lines() if l not in lines and l.strip().startswith("deb")]
        if added:
            # Lines appended to sources.list move to a file of their own, so they can be removed again.
            p = self.rootfs / "etc/apt/sources.list"
            p.write_text("\n".join(l for l in self._sources_list_lines() if l not in added) + "\n")
            n = 1
            while (self.rootfs / "etc/apt/sources.list.d" / "kernel-console-{}.list".format(n)).exists():
                n += 1
            f = self.rootfs / "etc/apt/sources.list.d" / "kernel-console-{}.list".format(n)
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text("\n".join(added) + "\n")
            new.append(str(f.relative_to(self.rootfs)))
        if new:
            self._set_temp(self.temp_files() + new)
            log.info("Temporary repository files: %s", ", ".join(new))
        self.project.record("kernel-console", command[:200])
        return out

    @staticmethod
    def repo_uris(path):
        """URIs of a .list or .sources file."""
        text = Path(path).read_text(errors="replace") if Path(path).is_file() else ""
        uris = []
        if str(path).endswith(".sources"):
            for st in parse_deb822(text):
                uris += st.get("URIs", "").split()
        else:
            for line in text.splitlines():
                line = re.sub(r"\[[^\]]*\]", "", line.split("#")[0]).split()
                if len(line) >= 2 and line[0] in ("deb", "deb-src"):
                    uris.append(line[1])
        return [u for u in uris if u]

    @staticmethod
    def list_prefix(uri):
        """The file name prefix APT uses for the package lists of *uri*."""
        u = re.sub(r"^[a-z0-9+.-]+://", "", uri.strip()).rstrip("/")
        u = re.sub(r"^[^@/]*@", "", u)
        return u.replace(":", "%3a").replace("/", "_") + "_"

    def repo_packages(self, uri, prefix="linux-"):
        """{package: [versions]} of the package lists that came from *uri*."""
        lists = self.rootfs / "var/lib/apt/lists"
        out = {}
        if not lists.is_dir():
            return out
        start = self.list_prefix(uri)
        for f in lists.iterdir():
            if f.name.startswith(start) and f.name.endswith("_Packages"):
                for st in parse_deb822(f.read_text(errors="replace")):
                    name = st.get("Package", "")
                    if name.startswith(prefix):
                        out.setdefault(name, []).append(st.get("Version", ""))
        return out

    def temp_repos(self):
        """[{file, uris, kernels: {package: [versions]}}] of the temporary repositories."""
        out = []
        for rel in self.temp_files():
            p = self.rootfs / rel
            if p.suffix in (".list", ".sources") and p.exists():
                kernels = {}
                for uri in self.repo_uris(p):
                    for name, versions in self.repo_packages(uri).items():
                        if name.startswith("linux-image-") or name.startswith("linux-xanmod"):
                            kernels.setdefault(name, []).extend(versions)
                out.append({"file": rel, "uris": self.repo_uris(p), "kernels": kernels})
        return out

    def finalize_temp_repos(self):
        """Keep the temporary repositories a kernel was installed from; remove the others
        (source file, unused keys and package lists). Returns (kept, removed) file lists."""
        temp = self.temp_files()
        if not temp:
            return [], []
        installed = {st.get("Package"): st.get("Version", "") for st in self._status()}
        kept, removed = [], []
        for rel in temp:
            p = self.rootfs / rel
            if p.suffix not in (".list", ".sources") or not p.exists():
                continue
            used = False
            for uri in self.repo_uris(p):
                for name, versions in self.repo_packages(uri).items():
                    if installed.get(name) in versions and (name.startswith("linux-image-") or
                                                            name.startswith("linux-xanmod") or
                                                            name.startswith("linux-headers-")):
                        used = True
            if used:
                kept.append(rel)
            else:
                for uri in self.repo_uris(p):
                    lists = self.rootfs / "var/lib/apt/lists"
                    if lists.is_dir():
                        for f in lists.iterdir():
                            if f.name.startswith(self.list_prefix(uri)):
                                f.unlink()
                p.unlink()
                removed.append(rel)
        # Keys of the temporary repositories: kept only when a kept source file uses them.
        kept_text = " ".join((self.rootfs / k).read_text(errors="replace") for k in kept if (self.rootfs / k).exists())
        for rel in temp:
            p = self.rootfs / rel
            if p.suffix in (".list", ".sources") or not p.exists():
                continue
            if Path(rel).name in kept_text or ("trusted.gpg.d" in rel and kept):
                kept.append(rel)
            else:
                p.unlink()
                removed.append(rel)
        self._set_temp([])
        if kept:
            log.info("Repositories kept (a kernel was installed from them): %s", ", ".join(kept))
        if removed:
            log.info("Temporary repositories removed: %s", ", ".join(removed))
        self.project.record("kernel-repos", "kept {} removed {}".format(len(kept), len(removed)))
        return kept, removed

    # Remove / hold --------------------------------------------------------------------
    def remove(self, version):
        kernels, _meta = self.installed()
        # Only versions that really exist: never a path like ".." (rmtree below).
        if not _VERSION.match(version or "") or version not in [k["version"] for k in kernels]:
            raise ValueError("No installed kernel {}".format(version))
        if len(kernels) <= 1:
            raise ValueError("This is the only kernel of the image: install another one first")
        names = {s.get("Package") for s in self._status()}
        targets = [n for n in ("linux-image-" + version, "linux-image-unsigned-" + version,
                               "linux-headers-" + version, "linux-modules-" + version,
                               "linux-modules-extra-" + version) if n in names]
        if targets:
            self.pkgs.remove(targets)
        else:
            # A kernel copied into /boot by hand.
            for f in ("vmlinuz-", "initrd.img-", "System.map-", "config-"):
                (self.rootfs / "boot" / (f + version)).unlink(missing_ok=True)
            shutil.rmtree(self.rootfs / "lib/modules" / version, ignore_errors=True)
            shutil.rmtree(self.rootfs / "usr/lib/modules" / version, ignore_errors=True)
        boot = self.project.state.get("boot", {})
        if boot.get("kernel") == version:
            boot["kernel"] = ""
            self.project.save()
        self.project.record("kernel-remove", version)

    def hold(self, package, on=True):
        if not re.match(r"^[a-z0-9][a-z0-9+.-]*$", package):
            raise ValueError("Invalid package name")
        with self.chroot:
            self.chroot.run(["apt-mark", "hold" if on else "unhold", package])

    def use_for_iso(self, version):
        self.project.state.setdefault("boot", {})["kernel"] = version
        self.project.save()

    # Maintenance -------------------------------------------------------------------------
    def update_initramfs(self, version=None):
        with self.chroot:
            if version:
                exists = (self.rootfs / "boot" / ("initrd.img-" + version)).exists()
                self.chroot.run(["update-initramfs", "-u" if exists else "-c", "-k", version])
            else:
                self.chroot.run(["update-initramfs", "-u", "-k", "all"])
        self.project.state["initramfs_dirty"] = False
        self.project.save()

    def dkms(self):
        if not (self.rootfs / "usr/sbin/dkms").exists():
            raise RuntimeError("DKMS is not installed in the image")
        kernels, _ = self.installed()
        with self.chroot:
            for k in kernels:
                if k["headers"]:
                    self.chroot.run(["dkms", "autoinstall", "-k", k["version"]], check=False)

    def install_firmware(self):
        comps = self._debian_components()
        if "non-free-firmware" not in comps:
            log.warning("Enable the non-free-firmware component on the Repositories page for most firmware")
        with self.chroot:
            self.pkgs.update()
            found = self.pkgs.available(FIRMWARE)
        todo = [p for p in FIRMWARE if p in found]
        if not todo:
            raise RuntimeError("No firmware packages available: enable non-free-firmware first")
        self.pkgs.install(todo, update=False)
        return todo

    # GRUB of the installed system ------------------------------------------------------------
    def grub_defaults(self):
        values = {}
        for p in [self.rootfs / "etc/default/grub"] + sorted((self.rootfs / "etc/default/grub.d").glob("*.cfg")):
            if p.exists():
                for m in re.finditer(r'(?m)^\s*(GRUB_[A-Z_]+)=(?:"([^"]*)"|\'([^\']*)\'|(\S*))', p.read_text(errors="replace")):
                    values[m.group(1)] = next(g for g in m.groups()[1:] if g is not None)
        return values

    def set_grub_defaults(self, values):
        """Write a drop-in that wins over /etc/default/grub and the branding package."""
        lines = ["# Written by DistroForge (Kernel page). Used when GRUB is installed or updated."]
        for key in GRUB_KEYS:
            v = values.get(key)
            if v is None or v == "":
                continue
            if any(c in str(v) for c in '"`$\\\n'):
                raise ValueError("{} contains characters that are not allowed".format(key))
            lines.append('{}="{}"'.format(key, v))
        p = self.rootfs / GRUB_DROPIN
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines) + "\n")
        self.project.record("grub-defaults", ", ".join(k for k in GRUB_KEYS if values.get(k)))

    def update_grub(self):
        """Run update-grub when the image has an installed GRUB menu.

        A live image usually has none: Calamares installs GRUB and runs
        update-grub on the target disk, using the defaults written here.
        """
        if not (self.rootfs / "boot/grub/grub.cfg").exists() or not (self.rootfs / "usr/sbin/update-grub").exists():
            log.info("The image has no installed GRUB menu; the installer creates it from these defaults.")
            return False
        with self.chroot:
            self.chroot.run(["update-grub"], check=False)
        return True

    def copy_to_iso(self, version=None):
        """Put the chosen kernel and initrd into the ISO tree now (/live)."""
        kernels = cleanup.kernels(self.rootfs)
        version = version or self.project.state.get("boot", {}).get("kernel") or (kernels[-1] if kernels else None)
        if not version:
            raise RuntimeError("No kernel installed")
        vm = self.rootfs / "boot" / ("vmlinuz-" + version)
        rd = self.rootfs / "boot" / ("initrd.img-" + version)
        if not rd.exists():
            raise RuntimeError("initrd.img-{} is missing: update the initramfs first".format(version))
        live = self.project.isodir / "live"
        live.mkdir(parents=True, exist_ok=True)
        shutil.copy2(vm, live / "vmlinuz")
        shutil.copy2(rd, live / "initrd.img")
        log.info("Kernel %s copied to the ISO tree", version)
        return version
