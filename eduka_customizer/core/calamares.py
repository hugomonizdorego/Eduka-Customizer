"""Calamares installer: branding, images, slideshow, users, partitions and more.

Debian's calamares-settings-debian keeps its configuration in /etc/calamares
(settings.conf, modules/*.conf, branding/<name>/). Modules without a file in
/etc fall back to /usr/share/calamares/modules, so such a file is copied to
/etc before it is changed. Every edit keeps the comments of the file.
"""

import re
import shutil
from pathlib import Path

from eduka_customizer.core import imaging, yamlconf
from eduka_customizer.core.apt import Packages
from eduka_customizer.core.chroot import Chroot
from eduka_customizer.core.log import log

ETC = "etc/calamares"
SHARE = "usr/share/calamares"
SAFE = re.compile(r"^[A-Za-z0-9_.-]+$")
COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

FILESYSTEMS = ["ext4", "btrfs", "xfs", "f2fs"]
SWAP_CHOICES = [("none", "No swap"), ("small", "Small swap partition"),
                ("suspend", "Swap for hibernation"), ("file", "Swap file")]
PARTITION_CHOICES = [("none", "Let the user choose"), ("erase", "Erase disk"),
                     ("alongside", "Install alongside"), ("replace", "Replace a partition"),
                     ("manual", "Manual partitioning")]
RESTART_MODES = [("user-unchecked", "Offer restart, unchecked"), ("user-checked", "Offer restart, checked"),
                 ("always", "Always restart"), ("never", "Never restart")]
LIVE_PACKAGES = ["calamares", "calamares-settings-debian", "live-boot", "live-boot-doc",
                 "live-config", "live-config-doc", "live-config-systemd", "live-tools", "live-task-localisation",
                 "live-task-recommended"]


class Calamares:
    def __init__(self, project):
        self.project = project
        self.rootfs = project.rootfs
        self.etc = self.rootfs / ETC
        self.chroot = Chroot(project.rootfs)

    # State ---------------------------------------------------------------
    def installed(self):
        return (self.rootfs / "usr/bin/calamares").exists() or (self.etc / "settings.conf").exists()

    def install(self):
        Packages(self.project).install(["calamares", "calamares-settings-debian"])
        # The installer suggests the project's time zone (Asia/Dili unless changed).
        from eduka_customizer.core.config import DEFAULT_TIMEZONE
        tz = self.project.state.get("language", {}).get("timezone") or \
            self.project.state.get("locale", {}).get("timezone") or DEFAULT_TIMEZONE
        try:
            self.set_locale(tz)
        except (OSError, ValueError) as e:
            log.warning("Could not set the installer's time zone: %s", e)

    def version(self):
        status = self.rootfs / "var/lib/dpkg/status"
        if status.exists():
            m = re.search(r"(?ms)^Package: calamares\n.*?^Version: (\S+)", status.read_text(errors="replace"))
            if m:
                return m.group(1)
        return ""

    # Files -----------------------------------------------------------------
    def settings_path(self):
        return self.etc / "settings.conf"

    def module_path(self, name, create=True):
        """Path of modules/<name>.conf in /etc, copied from /usr/share when needed."""
        if not SAFE.match(name):
            raise ValueError("Invalid module name: {}".format(name))
        etc = self.etc / "modules" / (name + ".conf")
        if etc.exists() or not create:
            return etc
        share = self.rootfs / SHARE / "modules" / (name + ".conf")
        etc.parent.mkdir(parents=True, exist_ok=True)
        if share.exists():
            shutil.copy2(share, etc)
        else:
            etc.write_text("---\n")
        return etc

    def modules(self):
        names = set()
        for base in (self.etc / "modules", self.rootfs / SHARE / "modules"):
            if base.is_dir():
                names |= {p.stem for p in base.glob("*.conf")}
        return sorted(names)

    def read(self, name):
        p = self.settings_path() if name == "settings" else self.module_path(name, create=False)
        if not p.exists() and name != "settings":
            p = self.rootfs / SHARE / "modules" / (name + ".conf")
        return yamlconf.load(p.read_text(errors="replace")) if p.exists() else {}

    def write(self, name, values):
        """Set top-level keys of settings.conf or modules/<name>.conf."""
        p = self.settings_path() if name == "settings" else self.module_path(name)
        if not p.exists():
            raise FileNotFoundError("{} does not exist: install Calamares first".format(p))
        p.write_text(yamlconf.update(p.read_text(errors="replace"), values))
        self.project.record("calamares", "{}: {}".format(name, ", ".join(values)))

    # Branding ----------------------------------------------------------------
    def branding_name(self):
        return str(self.read("settings").get("branding") or "debian")

    def branding_dir(self):
        return self.etc / "branding" / self.branding_name()

    def brandings(self):
        base = self.etc / "branding"
        return sorted(p.name for p in base.iterdir() if (p / "branding.desc").exists()) if base.is_dir() else []

    def branding(self):
        p = self.branding_dir() / "branding.desc"
        return yamlconf.load(p.read_text(errors="replace")) if p.exists() else {}

    def use_branding(self, name):
        if name not in self.brandings():
            raise ValueError("No Calamares branding called {}".format(name))
        self.write("settings", {"branding": name})

    def set_branding(self, strings=None, colors=None, images=None, slides=None, slide_seconds=8):
        """Change texts, colors, images (logo, icon, welcome) and the slideshow."""
        d = self.branding_dir()
        desc = d / "branding.desc"
        if not desc.exists():
            raise FileNotFoundError("Branding {} has no branding.desc".format(self.branding_name()))
        text = desc.read_text(errors="replace")
        data = yamlconf.load(text)
        values = {}
        if strings:
            merged = dict(data.get("strings") or {})
            merged.update({k: v for k, v in strings.items() if v is not None})
            values["strings"] = merged
        if colors:
            bad = [v for v in colors.values() if v and not COLOR.match(v)]
            if bad:
                raise ValueError("Colors must look like #00a879: {}".format(", ".join(bad)))
            merged = dict(data.get("style") or {})
            for k, v in colors.items():
                if v:
                    merged[self._style_key(merged, k)] = v
            values["style"] = merged
        if images:
            merged = dict(data.get("images") or {})
            sizes = {"productLogo": (256, 256), "productIcon": (128, 128), "productWelcome": (600, 400)}
            for key, src in images.items():
                if not src:
                    continue
                name = {"productLogo": "logo.png", "productIcon": "icon.png",
                        "productWelcome": "welcome.png"}.get(key, key + ".png")
                imaging.write_png(src, d / name, sizes.get(key, (256, 256)), fit="contain")
                merged[key] = name
            values["images"] = merged
        if slides is not None:
            self._slideshow(d, slides, slide_seconds)
            values["slideshow"] = "show.qml"
            values["slideshowAPI"] = 2
        if values:
            desc.write_text(yamlconf.update(text, values))
        self.project.record("calamares-branding", self.branding_name())

    def _style_key(self, style, key):
        """Calamares 3.3 spells style keys SidebarBackground, 3.2 sidebarBackground."""
        for existing in style:
            if existing.lower() == key.lower():
                return existing
        major_minor = re.match(r"(\d+)\.(\d+)", self.version() or "3.3")
        old = major_minor and (int(major_minor.group(1)), int(major_minor.group(2))) < (3, 3)
        return key[0].lower() + key[1:] if old else key[0].upper() + key[1:]

    def _is_32(self):
        m = re.match(r"(\d+)\.(\d+)", self.version() or "")
        return bool(m) and (int(m.group(1)), int(m.group(2))) < (3, 3)

    def style(self):
        """Branding colors with lower-case keys, whatever the Calamares version."""
        return {k[0].lower() + k[1:]: v for k, v in (self.branding().get("style") or {}).items()}

    def _slideshow(self, d, slides, seconds):
        """Write show.qml. A slide is an image path, or a dict with title, text (**bold**,
        *italic*, [links](https://...)), image, background and color, so people can read
        about the system while it installs."""
        import tempfile
        tmp = Path(tempfile.mkdtemp(prefix="eduka-slides-"))
        try:
            # Copy first: the old slide-NN.png files may be the sources.
            norm = []
            for i, sl in enumerate(slides, 1):
                sl = {"image": sl} if isinstance(sl, (str, Path)) else dict(sl)
                if sl.get("image") and Path(sl["image"]).is_file():
                    copy = tmp / "{}{}".format(i, Path(sl["image"]).suffix)
                    shutil.copy2(sl["image"], copy)
                    sl["image"] = str(copy)
                else:
                    sl["image"] = ""
                norm.append(sl)
            for old in d.glob("slide-*.png"):
                old.unlink()
            style = self.style()
            default_bg = style.get("sidebarBackground", "#0f2f27")
            items, stored = [], []
            for i, sl in enumerate(norm, 1):
                image = ""
                if sl["image"]:
                    image = "slide-{:02d}.png".format(i)
                    imaging.write_png(sl["image"], d / image, (800, 440), fit="contain")
                bg = sl.get("background") if COLOR.match(sl.get("background") or "") else default_bg
                fg = sl.get("color") if COLOR.match(sl.get("color") or "") else "#ffffff"
                items.append(slide_qml(sl.get("title", ""), sl.get("text", ""), image, bg, fg))
                stored.append({"title": sl.get("title", ""), "text": sl.get("text", ""),
                               "image": str(d / image) if image else "", "background": bg, "color": fg})
            if not items:
                items.append(slide_qml((self.branding().get("strings") or {}).get("productName") or
                                       self.project.display_name(), "", "", default_bg, "#ffffff"))
            (d / "show.qml").write_text(SHOW_QML.format(slides="\n".join(items), ms=max(2, int(seconds)) * 1000,
                                                        background=default_bg))
            self.project.state["calamares_slides"] = {"slides": stored, "seconds": int(seconds)}
            self.project.save()
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def slides(self):
        return sorted(str(p) for p in self.branding_dir().glob("slide-*.png"))

    def slide_data(self):
        """The slides as dicts (text slides of this project, or the images found in the branding)."""
        saved = self.project.state.get("calamares_slides", {}).get("slides")
        if saved:
            return saved
        return [{"title": "", "text": "", "image": p, "background": "", "color": ""} for p in self.slides()]

    # Installer launcher ------------------------------------------------------
    def launcher(self):
        for p in sorted((self.rootfs / "usr/share/applications").glob("*.desktop")):
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            # Debian's launcher runs the install-debian wrapper, which starts Calamares.
            if re.search(r"(?m)^Exec=.*(calamares|install-debian)", text):
                return p
        return None

    def set_launcher_name(self, name):
        p = self.launcher()
        if not p:
            raise FileNotFoundError("No Calamares launcher (.desktop file) found")
        from eduka_customizer.core.branding import Branding
        rel = "/" + str(p.relative_to(self.rootfs))
        with self.chroot:
            Branding(self.project)._divert(rel)
        text = re.sub(r"(?m)^Name(\[[^\]]+\])?=.*\n", "", p.read_text(errors="replace"))
        text = re.sub(r"(?m)^(\[Desktop Entry\]\n)", lambda m: m.group(1) + "Name={}\n".format(name), text, count=1)
        p.write_text(text)

    # Live user password: kept for recipes and the CLI, managed by core/users.py ----
    def set_live_password(self, password):
        """Password of the live user; empty restores Debian's default ('live')."""
        from eduka_customizer.core.users import Users
        u = Users(self.project)
        u._write_password_script("custom" if password else "default", password)
        self.project.record("live-password", "changed" if password else "default")

    def live_password_set(self):
        from eduka_customizer.core.users import Users
        return Users(self.project).live()["password"] != "default"

    def _live_script(self):
        from eduka_customizer.core.users import Users
        return Users(self.project)._script()

    # Summary used by the GUI -----------------------------------------------------
    def summary(self):
        users, part = self.read("users"), self.read("partition")
        welcome, fin, boot = self.read("welcome"), self.read("finished"), self.read("bootloader")
        locale, packages = self.read("locale"), self.read("packages")
        req = welcome.get("requirements") or {}
        pw = users.get("passwordRequirements") or {}
        efi = part.get("efi") or {}
        removed = []
        for op in packages.get("operations") or []:
            if isinstance(op, dict):
                for key in ("remove", "try_remove"):
                    removed += [p if isinstance(p, str) else p.get("package", "") for p in op.get(key) or []]
        return {
            "users": {
                "autologin": bool(users.get("doAutologin", False)),
                "root_password": bool(users.get("setRootPassword", True)),
                "reuse_password": bool(users.get("doReusePassword", True)),
                "min_length": int(pw.get("minLength", 6) or 0),
                "max_length": int(pw.get("maxLength", -1) or -1),
                "weak": bool(users.get("allowWeakPasswords", False)),
                "weak_default": bool(users.get("allowWeakPasswordsDefault", False)),
                "groups": _unique(_groups(users.get("defaultGroups") or [])),
                "shell": (users.get("user") or {}).get("shell") or users.get("userShell") or "/bin/bash",
                "sudo_group": users.get("sudoersGroup", "sudo"),
                "hostname": (users.get("hostname") or {}).get("template", "") if isinstance(
                    users.get("hostname"), dict) else "",
            },
            "partition": {
                "efi_size": efi.get("recommendedSize") or part.get("efiSystemPartitionSize") or "300MiB",
                "fs": part.get("defaultFileSystemType", "ext4"),
                "filesystems": part.get("availableFileSystemTypes") or ["ext4"],
                "swap": part.get("userSwapChoices") or ["none", "small", "suspend", "file"],
                "initial_swap": part.get("initialSwapChoice", "small"),
                "initial": part.get("initialPartitioningChoice", "none"),
                "luks": bool(part.get("enableLuksAutomatedPartitioning", True)),
                "luks2": part.get("luksGeneration", "luks1") == "luks2",
            },
            "welcome": {
                "storage": float(req.get("requiredStorage", 10)),
                "ram": float(req.get("requiredRam", 1)),
                "internet": "internet" in (req.get("required") or []),
                "power": "power" in (req.get("required") or []),
            },
            "finished": {"restart": fin.get("restartNowMode", "user-unchecked")},
            "bootloader": {"timeout": str(boot.get("timeout", "")), "efi_id": boot.get("efiBootloaderId", "")},
            "locale": {"region": locale.get("region", ""), "zone": locale.get("zone", ""),
                       "geoip": bool(locale.get("geoip"))},
            "remove": _unique(r for r in removed if r),
        }

    # Structured edits ---------------------------------------------------------
    def set_users(self, autologin=False, root_password=True, reuse_password=True, min_length=6,
                  max_length=-1, weak=False, weak_default=False, groups=None, shell="/bin/bash",
                  sudo_group="sudo", hostname=""):
        data = self.read("users")
        pw = dict(data.get("passwordRequirements") or {})
        pw.update({"nonempty": True, "minLength": int(min_length), "maxLength": int(max_length)})
        values = {"doAutologin": bool(autologin), "setRootPassword": bool(root_password),
                  "doReusePassword": bool(reuse_password), "passwordRequirements": pw,
                  "allowWeakPasswords": bool(weak), "allowWeakPasswordsDefault": bool(weak and weak_default),
                  "sudoersGroup": sudo_group or "sudo"}
        if groups is not None:
            values["defaultGroups"] = _merge_groups(data.get("defaultGroups") or [], groups)
        if self._is_32():
            values["userShell"] = shell or "/bin/bash"  # Calamares 3.2
        else:
            user = dict(data.get("user") or {})
            user["shell"] = shell or "/bin/bash"
            values["user"] = user
            if "userShell" in data:
                values["userShell"] = None
        if hostname:
            host = dict(data["hostname"]) if isinstance(data.get("hostname"), dict) else {
                "location": "EtcFile", "writeHostsFile": True}
            host["template"] = hostname
            values["hostname"] = host
        self.write("users", values)

    def set_partition(self, efi_size="300MiB", fs="ext4", filesystems=None, swap=None,
                      initial_swap="small", initial="none", luks=True, luks2=False):
        if fs not in FILESYSTEMS:
            raise ValueError("Unsupported file system: {}".format(fs))
        if not re.match(r"^\d+(\.\d+)?\s*(MiB|GiB|MB|GB|M|G)$", efi_size or ""):
            raise ValueError("EFI size must look like 300MiB or 1GiB")
        swap = [s for s in (swap or []) if s in dict(SWAP_CHOICES)] or ["none"]
        if initial_swap not in swap:
            initial_swap = swap[0]
        data = self.read("partition")
        values = {"defaultFileSystemType": fs,
                  "availableFileSystemTypes": sorted(set((filesystems or []) + [fs]), key=FILESYSTEMS.index),
                  "userSwapChoices": swap, "initialSwapChoice": initial_swap,
                  "initialPartitioningChoice": initial, "enableLuksAutomatedPartitioning": bool(luks),
                  "luksGeneration": "luks2" if luks2 else "luks1"}
        if self._is_32() or ("efiSystemPartitionSize" in data and "efi" not in data):
            values["efiSystemPartitionSize"] = efi_size
        else:
            efi = dict(data.get("efi") or {"mountPoint": data.get("efiSystemPartition", "/boot/efi")})
            efi["recommendedSize"] = efi_size
            values["efi"] = efi
        self.write("partition", values)

    def set_requirements(self, storage=10, ram=1, internet=False, power=False):
        data = self.read("welcome")
        req = dict(data.get("requirements") or {})
        check = list(req.get("check") or ["storage", "ram", "power", "internet", "root", "screen"])
        required = [r for r in (req.get("required") or ["storage", "ram", "root"])
                    if r not in ("internet", "power")]
        for flag, name in ((internet, "internet"), (power, "power")):
            if flag:
                required.append(name)
                if name not in check:
                    check.append(name)
        req.update({"requiredStorage": float(storage), "requiredRam": float(ram),
                    "check": check, "required": required})
        self.write("welcome", {"requirements": req})

    def set_finished(self, restart="user-unchecked"):
        if restart not in dict(RESTART_MODES):
            raise ValueError("Unknown restart mode: {}".format(restart))
        self.write("finished", {"restartNowMode": restart})

    def set_bootloader(self, timeout=None, efi_id=None):
        values = {}
        if timeout not in (None, ""):
            values["timeout"] = str(int(timeout))
        if efi_id:
            if not SAFE.match(efi_id):
                raise ValueError("Invalid EFI id")
            values["efiBootloaderId"] = efi_id
        if values:
            self.write("bootloader", values)

    def set_locale(self, timezone, geoip=False):
        region, _, zone = timezone.partition("/")
        values = {"region": region, "zone": zone or region}
        if not geoip:
            values["geoip"] = None
        self.write("locale", values)

    def set_removed_packages(self, packages):
        """Packages removed from the installed system (live tools, installer)."""
        data = self.read("packages")
        ops = [op for op in data.get("operations") or []
               if not (isinstance(op, dict) and set(op) <= {"remove", "try_remove"})]
        if packages:
            ops.insert(0, {"try_remove": _unique(packages)})
        values = {"operations": ops}
        if "backend" not in data:
            values["backend"] = "apt"
        self.write("packages", values)


def _groups(groups):
    out = []
    for g in groups:
        out.append(g if isinstance(g, str) else str(g.get("name", "")))
    return [g for g in out if g]


def _merge_groups(existing, names):
    """Keep the dict form (name/must_exist/system) of groups that stay."""
    keep = {(g if isinstance(g, str) else g.get("name")): g for g in existing}
    return [keep.get(n, n) for n in _unique(names) if n]


def _unique(items):
    out = []
    for i in items:
        if i not in out:
            out.append(i)
    return out


def qml_string(text):
    """A QML/JavaScript string literal (quotes, backslashes and newlines escaped)."""
    import json
    return json.dumps(str(text or ""), ensure_ascii=True)


def slide_qml(title, text, image, background, color):
    from eduka_customizer.core.welcome import to_markup
    body = to_markup(text).replace("\n", "<br>")
    parts = ["    Slide {",
             "        Rectangle {{ anchors.fill: parent; color: {} }}".format(qml_string(background)),
             "        Column {",
             "            anchors.centerIn: parent; width: parent.width * 0.86; spacing: 14"]
    if image:
        h = "0.88" if not (title or text) else "0.48"
        parts.append("            Image {{ source: {}; width: parent.width; height: presentation.height * {}; "
                     "fillMode: Image.PreserveAspectFit; smooth: true }}".format(qml_string(image), h))
    if title:
        parts.append("            Text {{ width: parent.width; text: {}; color: {}; font.pixelSize: 28; "
                     "font.bold: true; wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter }}"
                     .format(qml_string(title), qml_string(color)))
    if text:
        parts.append("            Text {{ width: parent.width; text: {}; color: {}; font.pixelSize: 17; "
                     "wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter; textFormat: Text.StyledText; "
                     "linkColor: {} }}".format(qml_string(body), qml_string(color), qml_string(color)))
    parts += ["        }", "    }"]
    return "\n".join(parts)

SHOW_QML = """/* Calamares slideshow generated by Eduka-Customizer */
import QtQuick 2.0;
import calamares.slideshow 1.0;

Presentation {{
    id: presentation

    Rectangle {{ anchors.fill: parent; color: "{background}"; z: -1 }}

    Timer {{
        interval: {ms}
        running: presentation.activatedInCalamares
        repeat: true
        onTriggered: presentation.goToNextSlide()
    }}

{slides}

    function onActivate() {{ presentation.currentSlide = 0; }}
    function onLeave() {{ }}
}}
"""
