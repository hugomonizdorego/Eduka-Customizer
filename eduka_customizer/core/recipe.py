"""Recipes: replayable JSON descriptions of a customization.

A recipe makes an Edukasaun OS build reproducible (and usable in CI):

    {
      "name": "Edukasaun OS 1.0 school edition",
      "steps": [
        {"action": "sources", "suite": "stable", "backports": true},
        {"action": "apt-install", "packages": ["gcompris-qt", "libreoffice"]},
        {"action": "desktop", "id": "eduka"},
        {"action": "flatpak", "apps": ["org.geogebra.GeoGebra"], "firstboot": true},
        {"action": "build"}
      ]
    }
"""

import json
from pathlib import Path

from eduka_customizer.core import hooks
from eduka_customizer.core.apt import Packages, Sources
from eduka_customizer.core.branding import Branding
from eduka_customizer.core.desktop import DesktopManager
from eduka_customizer.core.eduka_desktop import EdukaDesktop
from eduka_customizer.core.flatpak import Flatpak
from eduka_customizer.core.config import DEFAULT_TIMEZONE
from eduka_customizer.core.log import log


def _path(base, value):
    p = Path(value)
    return p if p.is_absolute() else (base / p)


def apply(project, recipe_file, build=True):
    recipe_file = Path(recipe_file)
    data = json.loads(recipe_file.read_text())
    base = recipe_file.resolve().parent
    steps = data.get("steps", [])
    log.info("Applying recipe %s (%d steps)", data.get("name", recipe_file.name), len(steps))
    result = None
    for n, step in enumerate(steps, 1):
        action = step.get("action", "")
        log.info("[%d/%d] %s", n, len(steps), action)
        result = run_step(project, step, base, build) or result
    return result


def run_step(project, step, base, build=True):
    action = step.get("action")
    if action == "sources":
        Sources(project.rootfs).set_debian(step.get("suite", project.distro.suite or "stable"),
                                           backports=step.get("backports", False),
                                           deb_src=step.get("deb_src", False))
        Packages(project).update()
    elif action == "repo":
        Sources(project.rootfs).add_repository(step["name"], step["uri"], step.get("suites", ""),
                                               step.get("components", "main"),
                                               key=str(_path(base, step["key"])) if step.get("key") and
                                               not step["key"].startswith("http") else step.get("key"))
    elif action == "apt-install":
        Packages(project).install(step.get("packages", []), no_recommends=step.get("no_recommends", False))
    elif action == "apt-remove":
        Packages(project).remove(step.get("packages", []))
    elif action == "apt-upgrade":
        Packages(project).upgrade()
    elif action == "deb":
        Packages(project).install_debs([_path(base, f) for f in step.get("files", [])])
    elif action == "flatpak":
        fp = Flatpak(project)
        if step.get("firstboot"):
            fp.set_firstboot(step.get("apps", []))
        else:
            fp.install(step.get("apps", []))
    elif action == "desktop":
        DesktopManager(project).install(step["id"], dm_id=step.get("dm"),
                                        remove_others=step.get("remove_others", False))
    elif action == "branding":
        from eduka_customizer.core.distrobrand import BrandingSpec, DistroBranding
        spec = BrandingSpec.from_project(project)
        for k, v in step.items():
            if k in ("logo", "wallpaper", "login_background", "grub_background") and v:
                v = str(_path(base, v))
            if hasattr(spec, k):
                setattr(spec, k, v)
        DistroBranding(project).apply(spec, with_keyring=step.get("keyring", False),
                                      email=step.get("email", ""))
    elif action == "themes":
        from eduka_customizer.core.themes import Themes
        th = Themes(project)
        if step.get("packs"):
            th.install_packs(step["packs"])
        th.apply(step.get("gtk", ""), step.get("icons", ""), step.get("cursor", ""),
                 step.get("font", ""), step.get("dark", False), step.get("lxqt_theme", ""))
        if "desktop_icons" in step:
            th.desktop_icons(**step["desktop_icons"])
    elif action == "session-type":
        DesktopManager(project).set_session_type(step["desktop"], step["type"])
    elif action == "compositor":
        DesktopManager(project).set_compositor(step["id"], step.get("preset", "shadows"))
    elif action == "sddm-theme":
        DesktopManager(project).set_sddm_theme(step["theme"])
    elif action == "session":
        DesktopManager(project).set_default_session(step["id"])
    elif action == "display-manager":
        DesktopManager(project).set_display_manager(step["id"])
    elif action == "eduka-desktop":
        ed = EdukaDesktop(project)
        if step.get("deb"):
            ed.install(_path(base, step["deb"]))
        elif step.get("install", True):
            ed.fetch_build_install(step.get("repo"), step.get("ref"))
        if any(k in step for k in ("panel", "menu", "desktop")):
            ed.write_defaults(step.get("panel"), step.get("menu"), step.get("desktop"))
    elif action == "identity":
        ident = dict(project.state["identity"])
        ident.update({k: v for k, v in step.items() if k != "action"})
        Branding(project).apply_identity(ident)
    elif action == "locale":
        Branding(project).apply_locale(step.get("default", "en_US.UTF-8"), step.get("extra", []),
                                       step.get("timezone", DEFAULT_TIMEZONE), step.get("keyboard", "us"))
    elif action == "language":
        from eduka_customizer.core.language import Language
        Language(project).apply(step.get("default", "en_US.UTF-8"), step.get("extra", []), step.get("timezone"),
                                step.get("keyboard"), step.get("variant", ""), step.get("packs", True),
                                step.get("boot_menu", []), step.get("calamares", True))
    elif action == "calamares":
        from eduka_customizer.core.calamares import Calamares
        cal = Calamares(project)
        if step.get("install") and not cal.installed():
            cal.install()
        if "branding" in step:
            b = dict(step["branding"])
            images = {k: str(_path(base, v)) for k, v in (b.get("images") or {}).items() if v}
            slides = [str(_path(base, f)) for f in b["slides"]] if "slides" in b else None
            cal.set_branding(strings=b.get("strings"), colors=b.get("colors"), images=images or None,
                             slides=slides, slide_seconds=b.get("slide_seconds", 8))
            if b.get("launcher"):
                cal.set_launcher_name(b["launcher"])
        if "users" in step:
            cal.set_users(**step["users"])
        if "partition" in step:
            cal.set_partition(**step["partition"])
        if "requirements" in step:
            cal.set_requirements(**step["requirements"])
        if "finished" in step:
            cal.set_finished(step["finished"])
        if "remove_packages" in step:
            cal.set_removed_packages(step["remove_packages"])
        if "live_password" in step:
            cal.set_live_password(step["live_password"])
    elif action == "users":
        from eduka_customizer.core.users import Users
        u = Users(project)
        if step.get("live") == "remove":
            u.remove_live()
        elif step.get("live"):
            u.set_live(**_args(step["live"]))
        for name in step.get("delete", []):
            u.delete_account(name)
        for acc in step.get("accounts", []):
            u.add_account(**_args(acc))
        for name, pw in (step.get("passwords") or {}).items():
            u.set_password(name, pw or None)
    elif action == "kernel":
        from eduka_customizer.core.kernel import Kernels
        k = Kernels(project)
        if step.get("third_party"):
            k.install_third_party(step["third_party"], step.get("headers", True))
        if step.get("install"):
            k.install(step["install"], headers=step.get("headers", False),
                      target_release=step.get("target_release"))
        if step.get("debs"):
            k.install_debs([_path(base, f) for f in step["debs"]])
        for v in step.get("remove", []):
            k.remove(v)
        if step.get("iso"):
            k.use_for_iso(step["iso"])
        if step.get("grub"):
            k.set_grub_defaults(step["grub"])
        if step.get("firmware"):
            k.install_firmware()
    elif action == "boot-file":
        from eduka_customizer.core import bootedit
        text = _path(base, step["from"]).read_text() if step.get("from") else step["text"]
        bootedit.save(project, step["file"], text, keep=step.get("keep", True))
    elif action == "plymouth":
        b = Branding(project)
        theme = step.get("theme")
        if step.get("packages"):
            from eduka_customizer.core.plymouth import Plymouth
            Plymouth(project).install_packages(step["packages"])
        if step.get("import"):
            from eduka_customizer.core.plymouth import Plymouth
            with b.chroot:
                b.ensure_plymouth()
            theme = Plymouth(project).install(_path(base, step["import"]))
        elif step.get("logo"):
            theme = b.generate_plymouth(step.get("name", "edukasaun"), _path(base, step["logo"]),
                                        step.get("background", "#0b3d2e"), step.get("color", "#00a879"))
        if theme:
            b.set_plymouth(theme)
    elif action == "wallpaper":
        Branding(project).set_wallpaper(_path(base, step["image"]))
    elif action == "login":
        Branding(project).set_login_screen(
            background=_path(base, step["background"]) if step.get("background") else None,
            gtk_theme=step.get("gtk_theme", ""), icon_theme=step.get("icon_theme", ""),
            sddm_theme=step.get("sddm_theme", ""))
    elif action == "hook":
        hooks.run_hook(project, _path(base, step["script"]), step.get("args", []))
    elif action == "command":
        hooks.run_command(project, step["run"])
    elif action == "boot":
        values = {k: v for k, v in step.items() if k != "action"}
        if values.get("splash"):
            values["splash"] = str(_path(base, values["splash"]))
        project.state["boot"].update(values)
        build = project.state.setdefault("build", {})
        for src, dst in (("extra_params", "boot_params"), ("timeout", "timeout"), ("title", "title")):
            if src in values:
                build[dst] = values[src]
        project.save()
    elif action == "build":
        if not build:
            return None
        from eduka_customizer.core.isobuild import BuildOptions, build as do_build
        opts = BuildOptions.from_project(project)
        for k, v in step.get("options", {}).items():
            if hasattr(opts, k):
                setattr(opts, k, v)
        return do_build(project, opts)
    else:
        raise ValueError("Unknown recipe action: {}".format(action))
    return None


def export(project):
    """Create a recipe from the current project settings and history."""
    st = project.state
    steps = [{"action": "identity", **{k: v for k, v in st["identity"].items()}},
             {"action": "users", "live": _live_step(project)},
             {"action": "language", **_language_step(st)}]
    installs, removes = [], []
    for h in st.get("history", []):
        if h["action"] == "apt-install":
            installs += [p for p in h["detail"].split() if p not in installs]
        elif h["action"] == "apt-remove":
            removes += [p for p in h["detail"].split() if p not in removes]
    if removes:
        steps.append({"action": "apt-remove", "packages": removes})
    if installs:
        steps.append({"action": "apt-install", "packages": [p for p in installs if p not in removes]})
    session = st.get("desktop", {}).get("session")
    if session:
        steps.append({"action": "session", "id": session})
    if st.get("flatpak", {}).get("firstboot"):
        steps.append({"action": "flatpak", "apps": st["flatpak"]["firstboot"], "firstboot": True})
    steps.append({"action": "boot", **st.get("boot", {})})
    steps.append({"action": "build", "options": st.get("build", {})})
    return {"name": st.get("name", "Edukasaun OS"), "base": st.get("source", {}).get("label", ""),
            "steps": steps}


def _language_step(st):
    lang = dict(st.get("locale", {}))
    for k, v in st.get("language", {}).items():
        if k != "installed_packs":
            lang[k] = v
    return lang


def _live_step(project):
    """The live user without its password (a recipe should not carry secrets)."""
    from eduka_customizer.core.users import Users
    live = Users(project).live()
    return {"username": live["username"], "fullname": live["fullname"], "autologin": live["autologin"],
            "groups": live["groups"], "keep_password": True}


def _args(values):
    """Keyword arguments from a recipe object; "comment" keys are notes for people."""
    return {k: v for k, v in values.items() if k != "comment"}
