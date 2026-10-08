"""Distro Branding Studio: turn Debian into your own distribution.

Instead of patching Debian's packages (base-files, lsb-release,
distro-info-data, desktop-base, Debian logos, GRUB, the installer and
debian-archive-keyring), Eduka-Customizer generates two packages of your
own that replace their identity with dpkg diversions:

  <id>-branding         os-release, issue, lsb-release, distro-info, logos,
                        desktop-base theme, GRUB menu (installed system),
                        Calamares installer branding
  <id>-archive-keyring  your APT signing key (optional)

Diversions survive Debian updates: when Debian upgrades base-files, the new
Debian file lands next to yours (*.distrib) and your branding stays. No
package repository is needed - the packages are built locally and
installed into the image. Their Debian source trees live in
PROJECT/branding/ and can be edited and rebuilt, or published later.
"""

import glob
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from eduka_customizer.core import debpkg, imaging, runner
from eduka_customizer.core.apt import Packages
from eduka_customizer.core.distro import format_os_release
from eduka_customizer.core.log import log

SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,30}$")

# Images shipped by Debian (desktop-base, plymouth, icon themes) that show
# the Debian swirl. Each one found in the image is replaced by your logo.
DEBIAN_LOGOS = [
    "usr/share/pixmaps/debian-logo*",
    "usr/share/desktop-base/debian-logos/*",
    "usr/share/icons/*/*/apps/debian-logo*",
    "usr/share/icons/*/*/places/start-here-debian*",
    "usr/share/icons/*/*/places/debian-swirl*",
    "usr/share/icons/*/*/emblems/emblem-debian*",
    "usr/share/icons/vendor/*/*/*",
    "usr/share/plymouth/debian-logo.png",
    "usr/share/images/vendor-logos/*",
]
IMAGE_EXT = (".png", ".svg", ".jpg", ".jpeg")
ALTERNATIVES = [
    # name, link, file in our theme, priority
    ("desktop-background", "/usr/share/images/desktop-base/desktop-background", "wallpaper.png"),
    ("desktop-grub", "/usr/share/images/desktop-base/desktop-grub.png", "grub.png"),
    ("desktop-login-background", "/usr/share/images/desktop-base/login-background.png", "login.png"),
]


@dataclass
class BrandingSpec:
    # Nothing is preset: the Identity page (or the image itself) names the distribution.
    name: str = ""
    os_id: str = ""
    version: str = ""
    codename: str = ""
    home_url: str = ""
    support_url: str = ""
    bug_url: str = ""
    maintainer: str = ""
    logo: str = ""
    accent: str = "#00a879"
    dark: str = "#0f2f27"
    wallpaper: str = ""
    login_background: str = ""
    grub_background: str = ""
    replace_logos: bool = True
    desktop_theme: bool = True
    grub: bool = True
    grub_name: bool = True
    grub_timeout: int = 5
    kernel_options: str = "quiet splash"
    secure_boot_safe: bool = True
    calamares: bool = True
    keyring: bool = False

    @classmethod
    def from_project(cls, project):
        ident = project.state.get("identity", {})
        spec = cls(name=ident.get("name") or project.display_name(), os_id=project.os_id(),
                   version=ident.get("version") or project.distro.version_id or "1.0",
                   codename=ident.get("codename", ""), home_url=ident.get("home_url", ""),
                   support_url=ident.get("support_url", ""), bug_url=ident.get("bug_url", ""))
        for k, v in project.state.get("branding", {}).get("spec", {}).items():
            if hasattr(spec, k):
                setattr(spec, k, v)
        if not spec.maintainer:
            spec.maintainer = "{} developers <{}@localhost>".format(spec.name or "Distribution", spec.os_id or "root")
        return spec

    def validate(self):
        if not SAFE_ID.match(self.os_id):
            raise ValueError("The OS ID must be lower case letters, digits and '-' (e.g. mylinux)")
        if not self.name.strip():
            raise ValueError("The system name is empty")
        for c in (self.accent, self.dark):
            if not re.match(r"^#[0-9a-fA-F]{6}$", c):
                raise ValueError("Colors must look like #RRGGBB")
        for f in (self.logo, self.wallpaper, self.login_background, self.grub_background):
            if f and not Path(f).is_file():
                raise ValueError("File not found: {}".format(f))


class DistroBranding:
    def __init__(self, project):
        self.project = project
        self.base = project.path / "branding"
        self.debs = self.base / "debs"

    def spec(self):
        return BrandingSpec.from_project(self.project)

    def tree(self, spec=None):
        spec = spec or self.spec()
        return self.base / (spec.os_id + "-branding")

    def keyring_tree(self, spec=None):
        spec = spec or self.spec()
        return self.base / (spec.os_id + "-archive-keyring")

    # ------------------------------------------------------------------
    def generate(self, spec):
        """Write (or refresh) the editable Debian source tree."""
        spec.validate()
        rootfs = self.project.rootfs
        pkg = spec.os_id + "-branding"
        tree = self.tree(spec)
        files = tree / "files"
        if files.exists():
            shutil.rmtree(files)
        data = files / "usr/share" / pkg
        data.mkdir(parents=True)
        diverts, alternatives = [], []

        def divert(target, content=None, source_file=None):
            name = re.sub(r"[^A-Za-z0-9._-]", "_", target.strip("/"))
            dest = data / "divert" / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            if source_file:
                shutil.copy2(source_file, dest)
            else:
                dest.write_text(content)
            diverts.append((target, "/usr/share/{}/divert/{}".format(pkg, name)))
            return dest

        # Identity (base-files, lsb-release, distro-info-data) -----------
        info = self.project.distro
        pretty = "{} {}{}".format(spec.name, spec.version, " ({})".format(spec.codename) if spec.codename else "")
        osr = {"PRETTY_NAME": pretty, "NAME": spec.name, "VERSION_ID": spec.version,
               "VERSION": spec.version + (" ({})".format(spec.codename) if spec.codename else ""),
               "VERSION_CODENAME": info.debian_codename or "", "ID": spec.os_id, "ID_LIKE": "debian",
               "DISTRO_CODENAME": spec.codename, "DEBIAN_SUITE": info.suite,
               "HOME_URL": spec.home_url, "SUPPORT_URL": spec.support_url,
               "BUG_REPORT_URL": spec.bug_url, "LOGO": spec.os_id + "-logo"}
        osr = {k: v for k, v in osr.items() if v}
        divert("/usr/lib/os-release", format_os_release(osr))
        divert("/etc/issue", "{} \\n \\l\n\n".format(pretty))
        divert("/etc/issue.net", pretty + "\n")
        etc = files / "etc"
        etc.mkdir(parents=True, exist_ok=True)
        divert("/etc/lsb-release", 'DISTRIB_ID="{}"\nDISTRIB_RELEASE="{}"\nDISTRIB_CODENAME="{}"\n'
                                   'DISTRIB_DESCRIPTION="{}"\n'.format(spec.name, spec.version,
                                                                      info.debian_codename, pretty))
        (etc / (spec.os_id + "_version")).write_text(spec.version + "\n")
        di = files / "usr/share/distro-info"
        di.mkdir(parents=True)
        (di / (spec.os_id + ".csv")).write_text(
            "version,codename,series,created,release,eol\n{},{},{},,,\n".format(
                spec.version, spec.codename or spec.version, (spec.codename or spec.os_id).lower()))

        # Logos (debian-logos, desktop-base, icon themes) --------------------
        if spec.logo:
            self._own_logos(spec, files)
            if spec.replace_logos:
                for target in self.debian_logo_files():
                    dest = data / "logos" / re.sub(r"[^A-Za-z0-9._-]", "_", target.strip("/"))
                    imaging.replace_image(spec.logo, rootfs / target.lstrip("/"), dest)
                    diverts.append((target, "/usr/share/{}/logos/{}".format(pkg, dest.name)))

        # desktop-base theme ---------------------------------------------------
        theme = files / "usr/share/desktop-base" / (spec.os_id + "-theme")
        if spec.desktop_theme:
            for key, fname, size in (("wallpaper", "wallpaper.png", (1920, 1080)),
                                     ("login_background", "login.png", (1920, 1080)),
                                     ("grub_background", "grub.png", (1920, 1080))):
                src = getattr(spec, key) or spec.wallpaper
                if src:
                    imaging.write_png(src, theme / fname, size)
            for name, link, fname in ALTERNATIVES:
                if (theme / fname).exists():
                    alternatives.append((name, link, "/usr/share/desktop-base/{}-theme/{}".format(
                        spec.os_id, fname), "90"))

        # GRUB of the installed system ------------------------------------------
        scripts_extra = ""
        if spec.grub:
            lines = ["# {} boot menu, from {}. Edit, then run update-grub.".format(spec.name, pkg)]
            if spec.grub_name:
                lines.append('GRUB_DISTRIBUTOR="{}"'.format(spec.name.replace('"', "")))
            if (theme / "grub.png").exists():
                lines.append('GRUB_BACKGROUND="/usr/share/desktop-base/{}-theme/grub.png"'.format(spec.os_id))
            lines += ["GRUB_TIMEOUT={}".format(int(spec.grub_timeout)),
                      'GRUB_CMDLINE_LINUX_DEFAULT="{}"'.format(spec.kernel_options.replace('"', "")),
                      "GRUB_GFXMODE=auto"]
            grubd = etc / "default/grub.d"
            grubd.mkdir(parents=True)
            (grubd / "90-{}.cfg".format(spec.os_id)).write_text("\n".join(lines) + "\n")
            if spec.grub_name and spec.secure_boot_safe:
                efi_id = spec.name.split()[0].lower()
                if efi_id != "debian":
                    self._efi_sync(spec, files, data, efi_id)
                    scripts_extra = "    /usr/share/{}/efi-sync || true\n".format(pkg)

        # Calamares (graphical installer) ---------------------------------------
        if spec.calamares and spec.logo:
            self._calamares(spec, files, divert)
        elif spec.calamares:
            log.warning("Calamares branding needs a logo; skipped")

        (data / "divert.list").write_text("".join("{}\t{}\n".format(t, s) for t, s in diverts))
        (data / "alternatives.list").write_text("".join("\t".join(a) + "\n" for a in alternatives))
        (data / "spec.json").write_text(json.dumps(asdict(spec), indent=1))

        depends = "dpkg (>= 1.19)"
        version = self._next_version(spec)
        debpkg.write_tree(
            tree, pkg, spec.maintainer,
            [{"Package": pkg, "Depends": depends,
              "Description": "{} branding and identity\n Replaces the identity of Debian (os-release, "
                             "issue, lsb-release, logos, desktop-base\n artwork, GRUB menu and installer "
                             "branding) with {} using dpkg\n diversions.".format(spec.name, spec.name),
              "install": ["files/usr /", "files/etc /"],
              "scripts": {"postinst": POSTINST.format(pkg=pkg, extra=scripts_extra),
                          "prerm": PRERM.format(pkg=pkg)}}],
            version, ["Branding for {} generated by Eduka-Customizer".format(pretty)],
            homepage=spec.home_url)
        self.project.state.setdefault("branding", {})["spec"] = asdict(spec)
        self.project.save()
        log.info("Branding package source written to %s (%d diversions)", tree, len(diverts))
        return tree

    def _next_version(self, spec):
        st = self.project.state.setdefault("branding", {})
        n = int(st.get("build_number", 0)) + 1
        st["build_number"] = n
        return "{}+{}".format(spec.version, n)

    def _own_logos(self, spec, files):
        icons = files / "usr/share/icons/hicolor"
        for size in (16, 22, 24, 32, 48, 64, 128, 256, 512):
            for name in (spec.os_id + "-logo", "distributor-logo-" + spec.os_id):
                imaging.write_png(spec.logo, icons / "{0}x{0}/apps/{1}.png".format(size, name),
                                  (size, size), fit="contain")
        if spec.logo.lower().endswith(".svg"):
            dest = icons / "scalable/apps" / (spec.os_id + "-logo.svg")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(spec.logo, dest)
        imaging.write_png(spec.logo, files / "usr/share/pixmaps" / (spec.os_id + "-logo.png"),
                          (256, 256), fit="contain")
        imaging.write_png(spec.logo, files / "usr/share/plymouth" / (spec.os_id + "-logo.png"),
                          (256, 256), fit="contain")

    def debian_logo_files(self):
        rootfs = self.project.rootfs
        found = set()
        for pattern in DEBIAN_LOGOS:
            for p in glob.glob(str(rootfs / pattern)):
                path = Path(p)
                if path.suffix.lower() in IMAGE_EXT and (path.is_file() or path.is_symlink()):
                    found.add("/" + str(path.relative_to(rootfs)))
        return sorted(found)

    def _efi_sync(self, spec, files, data, efi_id):
        """Debian's signed GRUB always reads EFI/debian/grub.cfg. When GRUB is
        installed to EFI/<name>, keep a copy there so Secure Boot still works."""
        script = data / "efi-sync"
        script.write_text(EFI_SYNC.format(efi=efi_id))
        script.chmod(0o755)
        apt = files / "etc/apt/apt.conf.d"
        apt.mkdir(parents=True, exist_ok=True)
        (apt / "90-{}-efi-sync".format(spec.os_id)).write_text(
            'DPkg::Post-Invoke {{ "if [ -x /usr/share/{0}-branding/efi-sync ]; then '
            '/usr/share/{0}-branding/efi-sync || true; fi"; }};\n'.format(spec.os_id))
        kernel = files / "etc/kernel/postinst.d"
        kernel.mkdir(parents=True, exist_ok=True)
        hook = kernel / "zz-{}-efi-sync".format(spec.os_id)
        hook.write_text("#!/bin/sh\nexec /usr/share/{}-branding/efi-sync\n".format(spec.os_id))
        hook.chmod(0o755)

    def _calamares(self, spec, files, divert):
        """Brand the installer. When the ISO has a Calamares branding, its component name and
        files stay what they are (settings.conf, module ids, efiBootloaderId untouched): only
        texts, colors and our images are added, so the installer keeps working."""
        from eduka_customizer.core import yamlconf
        from eduka_customizer.core.calamares import Calamares
        rootfs = self.project.rootfs
        cal = Calamares(self.project)
        iso_desc = cal.branding_dir() / "branding.desc" if cal.settings_path().exists() else None
        if iso_desc is not None and iso_desc.exists():
            comp = cal.branding_name()
            bdir = files / "etc/calamares/branding" / comp
            bdir.mkdir(parents=True, exist_ok=True)
            images = {}
            if spec.logo:
                imaging.write_png(spec.logo, bdir / "{}-logo.png".format(spec.os_id), (256, 256), fit="contain")
                imaging.write_png(spec.logo, bdir / "{}-welcome.png".format(spec.os_id), (480, 300), fit="contain")
                images = {"productLogo": "{}-logo.png".format(spec.os_id),
                          "productIcon": "{}-logo.png".format(spec.os_id),
                          "productWelcome": "{}-welcome.png".format(spec.os_id)}
            text = iso_desc.read_text(errors="replace")
            data = yamlconf.load(text)
            strings = dict(data.get("strings") or {})
            strings.update({k: v for k, v in (
                ("productName", spec.name), ("shortProductName", spec.name), ("version", spec.version),
                ("shortVersion", spec.version), ("versionedName", "{} {}".format(spec.name, spec.version)),
                ("shortVersionedName", "{} {}".format(spec.name, spec.version)),
                ("productUrl", spec.home_url), ("supportUrl", spec.support_url or spec.home_url),
                ("knownIssuesUrl", spec.bug_url or spec.home_url), ("releaseNotesUrl", spec.home_url)) if v})
            values = {"strings": strings}
            if images:
                values["images"] = dict(data.get("images") or {}, **images)
            style = dict(data.get("style") or {})
            for key, value in (("SidebarBackground", spec.dark), ("SidebarBackgroundCurrent", spec.accent)):
                style[cal._style_key(style, key)] = value
            values["style"] = style
            divert("/etc/calamares/branding/{}/branding.desc".format(comp), yamlconf.update(text, values))
            return
        bdir = files / "etc/calamares/branding" / spec.os_id
        bdir.mkdir(parents=True, exist_ok=True)
        if spec.logo:
            imaging.write_png(spec.logo, bdir / "logo.png", (256, 256), fit="contain")
            imaging.write_png(spec.logo, bdir / "welcome.png", (480, 300), fit="contain")
        if spec.wallpaper:
            imaging.write_png(spec.wallpaper, bdir / "slide.png", (800, 440))
        entry = "debian" if spec.secure_boot_safe else spec.os_id
        (bdir / "branding.desc").write_text(CALAMARES_DESC.format(
            id=spec.os_id, name=spec.name, version=spec.version, entry=entry,
            url=spec.home_url, support=spec.support_url or spec.home_url,
            bugs=spec.bug_url or spec.home_url, accent=spec.accent, dark=spec.dark,
            logo="logo.png" if spec.logo else "", welcome="welcome.png" if spec.logo else ""))
        (bdir / "show.qml").write_text(CALAMARES_SHOW.format(name=spec.name, dark=spec.dark,
                                                             accent=spec.accent,
                                                             slide="slide.png" if spec.wallpaper else ""))
        settings = rootfs / "etc/calamares/settings.conf"
        if settings.exists():
            text = settings.read_text(errors="replace")
            if re.search(r"(?m)^branding:", text):
                text = re.sub(r"(?m)^branding:.*$", "branding: " + spec.os_id, text)
            else:
                text += "\nbranding: {}\n".format(spec.os_id)
            divert("/etc/calamares/settings.conf", text)
        boot = rootfs / "etc/calamares/modules/bootloader.conf"
        if boot.exists() and spec.secure_boot_safe:
            text = boot.read_text(errors="replace")
            if re.search(r"(?m)^efiBootloaderId:", text):
                text = re.sub(r"(?m)^efiBootloaderId:.*$", 'efiBootloaderId: "debian"', text)
            else:
                text += '\nefiBootloaderId: "debian"\n'
            divert("/etc/calamares/modules/bootloader.conf", text)

    # Keyring -------------------------------------------------------------
    @property
    def gnupg(self):
        return self.base / "gnupg"

    def _gpg(self, args, **kw):
        """Run gpg on the project keyring.

        gpg-agent's socket lives in the home directory and UNIX socket paths
        are limited to 108 bytes, so a short symlink is used as --homedir.
        """
        import tempfile
        self.gnupg.mkdir(parents=True, exist_ok=True)
        os.chmod(self.gnupg, 0o700)
        tmp = tempfile.mkdtemp(prefix="egpg-", dir="/tmp")
        home = os.path.join(tmp, "h")
        os.symlink(str(self.gnupg), home)
        try:
            return runner.run(["gpg", "--homedir", home] + list(args), **kw)
        finally:
            runner.run(["gpgconf", "--homedir", home, "--kill", "gpg-agent"], check=False, quiet=True)
            shutil.rmtree(tmp, ignore_errors=True)

    def key_fingerprint(self):
        if not (self.gnupg / "pubring.kbx").exists():
            return ""
        out = self._gpg(["--batch", "--with-colons", "--list-secret-keys"], check=False, capture=True)
        for line in out.splitlines():
            if line.startswith("fpr:"):
                return line.split(":")[9]
        return ""

    def generate_key(self, spec, email):
        runner.require("gpg")
        if not re.match(r"^[^@\s<>]+@[^@\s<>]+$", email):
            raise ValueError("Invalid e-mail address")
        if self.key_fingerprint():
            raise RuntimeError("A signing key already exists for this project")
        uid = "{} Archive Signing Key <{}>".format(spec.name, email)
        self._gpg(["--batch", "--pinentry-mode", "loopback", "--passphrase", "",
                   "--quick-generate-key", uid, "ed25519", "sign", "5y"])
        fpr = self.key_fingerprint()
        log.info("Created signing key %s", fpr)
        self.project.state.setdefault("branding", {})["key"] = fpr
        self.project.save()
        return fpr

    def export_key(self, dest, secret=False):
        fpr = self.key_fingerprint()
        cmd = ["--batch", "--yes", "--pinentry-mode", "loopback", "--passphrase", "", "--output", str(dest)]
        cmd += ["--armor", "--export-secret-keys"] if secret else ["--export"]
        self._gpg(cmd + [fpr])
        if secret:
            os.chmod(dest, 0o600)
        return dest

    def generate_keyring(self, spec):
        if not self.key_fingerprint():
            raise RuntimeError("Create a signing key first")
        pkg = spec.os_id + "-archive-keyring"
        tree = self.keyring_tree(spec)
        target = tree / "files/usr/share/keyrings" / (pkg + ".gpg")
        target.parent.mkdir(parents=True, exist_ok=True)
        self.export_key(str(target))
        debpkg.write_tree(tree, pkg, spec.maintainer,
                          [{"Package": pkg, "Description": "GnuPG archive key of the {} repository\n "
                                                           "Verifies packages published by {}.".format(
                                                               spec.name, spec.name),
                            "install": ["files/usr /"]}],
                          spec.version + "+" + str(self.project.state["branding"].get("build_number", 1)),
                          ["Archive key for {}".format(spec.name)], homepage=spec.home_url)
        return tree

    # Build and install --------------------------------------------------
    def build(self):
        debs = []
        for tree in (self.tree(), self.keyring_tree()):
            if (tree / "debian/control").exists():
                debs += debpkg.build_tree(tree, self.debs)
        if not debs:
            raise RuntimeError("Generate the branding package first")
        return debs

    def install(self, debs):
        Packages(self.project).install_debs(debs, reinstall=True)
        self.project.mark_initramfs_dirty()
        self.project.record("distro-branding", " ".join(Path(d).name for d in debs))

    def apply(self, spec, with_keyring=False, email=""):
        """Generate, build and install in one go (the 'Apply' button)."""
        self.generate(spec)
        if with_keyring:
            if not self.key_fingerprint():
                self.generate_key(spec, email or "archive@{}.org".format(spec.os_id))
            self.generate_keyring(spec)
        debs = self.build()
        self.install(debs)
        return debs

    def installed(self):
        pkgs = dict((n, v) for n, v, _s, _d in Packages(self.project).installed())
        spec = self.spec()
        return {name: pkgs.get(name, "") for name in (spec.os_id + "-branding",
                                                      spec.os_id + "-archive-keyring")}


POSTINST = """#!/bin/sh
# Generated by Eduka-Customizer: replace Debian's identity with dpkg diversions.
set -e
PKG={pkg}
DATA=/usr/share/$PKG
if [ "$1" = "configure" ]; then
    while IFS="$(printf '\\t')" read -r target source; do
        [ -n "$target" ] || continue
        # Diversions made by older Eduka-Customizer versions (dpkg-divert --local).
        if dpkg-divert --listpackage "$target" | grep -qx LOCAL; then
            dpkg-divert --local --no-rename --remove "$target" >/dev/null
            [ -e "$target.debian" ] && mv -f "$target.debian" "$target"
        fi
        if [ "$(dpkg-divert --listpackage "$target")" != "$PKG" ]; then
            dpkg-divert --package "$PKG" --add --rename --divert "$target.distrib" "$target" >/dev/null
        fi
        mkdir -p "$(dirname "$target")"
        rm -f "$target"
        cp -f "$source" "$target"
    done < "$DATA/divert.list"
    while IFS="$(printf '\\t')" read -r name link path prio; do
        [ -n "$name" ] || continue
        [ -e "$path" ] || continue
        mkdir -p "$(dirname "$link")"
        update-alternatives --install "$link" "$name" "$path" "$prio" >/dev/null 2>&1 || true
        update-alternatives --set "$name" "$path" >/dev/null 2>&1 || true
    done < "$DATA/alternatives.list"
    if [ -e /etc/os-release ] && [ ! -L /etc/os-release ]; then
        ln -sf ../usr/lib/os-release /etc/os-release
    fi
    command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -f /usr/share/icons/hicolor || true
    if [ -x /usr/sbin/update-grub ] && [ -e /boot/grub/grub.cfg ]; then
        update-grub || true
    fi
{extra}fi
#DEBHELPER#
exit 0
"""

PRERM = """#!/bin/sh
# Generated by Eduka-Customizer: give Debian its files back.
set -e
PKG={pkg}
DATA=/usr/share/$PKG
if [ "$1" = "remove" ] || [ "$1" = "deconfigure" ]; then
    while IFS="$(printf '\\t')" read -r name link path prio; do
        [ -n "$name" ] && update-alternatives --remove "$name" "$path" >/dev/null 2>&1 || true
    done < "$DATA/alternatives.list"
    while IFS="$(printf '\\t')" read -r target source; do
        [ -n "$target" ] || continue
        rm -f "$target"
        dpkg-divert --package "$PKG" --remove --rename --divert "$target.distrib" "$target" >/dev/null || true
    done < "$DATA/divert.list"
fi
#DEBHELPER#
exit 0
"""

EFI_SYNC = """#!/bin/sh
# Debian's signed GRUB (Secure Boot) reads EFI/debian/grub.cfg even when it
# is installed in EFI/{efi}. Keep that file in sync.
for esp in /boot/efi /efi; do
    src="$esp/EFI/{efi}/grub.cfg"
    [ -f "$src" ] || continue
    mkdir -p "$esp/EFI/debian"
    cmp -s "$src" "$esp/EFI/debian/grub.cfg" 2>/dev/null || cp "$src" "$esp/EFI/debian/grub.cfg"
done
exit 0
"""

CALAMARES_DESC = """---
# Calamares branding generated by Eduka-Customizer
componentName:  {id}
welcomeStyleCalamares: false
welcomeExpandingLogo: true
windowExpanding: normal
windowSize: 900px,620px
windowPlacement: center
sidebar: widget
navigation: widget

strings:
    productName:         "{name}"
    shortProductName:    "{name}"
    version:             "{version}"
    shortVersion:        "{version}"
    versionedName:       "{name} {version}"
    shortVersionedName:  "{name} {version}"
    bootloaderEntryName: "{entry}"
    productUrl:          "{url}"
    supportUrl:          "{support}"
    knownIssuesUrl:      "{bugs}"
    releaseNotesUrl:     "{url}"
    donateUrl:           ""

images:
    productLogo:         "{logo}"
    productIcon:         "{logo}"
    productWelcome:      "{welcome}"

slideshowAPI: 2
slideshow:               "show.qml"

style:
    SidebarBackground:        "{dark}"
    SidebarText:              "#FFFFFF"
    SidebarTextCurrent:       "#FFFFFF"
    SidebarBackgroundCurrent: "{accent}"
"""

CALAMARES_SHOW = """/* Calamares slideshow generated by Eduka-Customizer */
import QtQuick 2.0
import calamares.slideshow 1.0

Presentation {{
    id: presentation
    function nextSlide() {{ presentation.goToNextSlide(); }}
    Timer {{
        interval: 7000; repeat: true
        running: presentation.activatedInCalamares
        onTriggered: nextSlide()
    }}
    Slide {{
        Rectangle {{ anchors.fill: parent; color: "{dark}" }}
        Image {{ anchors.fill: parent; source: "{slide}"; fillMode: Image.PreserveAspectCrop; opacity: 0.35 }}
        Text {{
            anchors.centerIn: parent; width: parent.width * 0.8
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            color: "white"; font.pixelSize: 26
            text: "Welcome to {name}"
        }}
    }}
    Slide {{
        Rectangle {{ anchors.fill: parent; color: "{dark}" }}
        Text {{
            anchors.centerIn: parent; width: parent.width * 0.8
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            color: "{accent}"; font.pixelSize: 22
            text: "{name} is being installed. This takes a few minutes."
        }}
    }}
    function onActivate() {{ presentation.currentSlide = 0; }}
    function onLeave() {{ }}
}}
"""
