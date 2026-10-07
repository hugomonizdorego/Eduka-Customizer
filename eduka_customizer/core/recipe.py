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
                                       step.get("timezone", "UTC"), step.get("keyboard", "us"))
    elif action == "plymouth":
        b = Branding(project)
        theme = step.get("theme")
        if step.get("import"):
            theme = b.import_plymouth(_path(base, step["import"]))
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
        project.state["boot"].update({k: v for k, v in step.items() if k != "action"})
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
             {"action": "locale", **st["locale"]}]
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
