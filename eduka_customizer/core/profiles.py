"""What the distribution is for (Education, Server, Professional, Home, Other) and
the recommendations that follow from it. Every recommendation is a recipe step,
so it can be shown, unticked, applied or saved like any other recipe."""

import json

from eduka_customizer.core.config import data_file


def catalog():
    with open(data_file("profiles.json"), encoding="utf-8") as fh:
        return json.load(fh)["profiles"]


def get(profile_id):
    for p in catalog():
        if p["id"] == profile_id:
            return p
    raise KeyError("Unknown purpose: {}".format(profile_id))


def recommendations(profile_id):
    """[(key, label, step)] for a purpose, in the order of the work."""
    from eduka_customizer.core import desktop as dsk
    p = get(profile_id)
    out = []
    if p.get("desktop"):
        de = dsk.desktop(p["desktop"])
        dm = dsk.display_manager(p["dm"]) if p.get("dm") else None
        out.append(("desktop", "Desktop: {}{}".format(de["name"], " with the login screen " + dm["name"] if dm else ""),
                    {"action": "desktop", "id": de["id"], "dm": p.get("dm")}))
        if p.get("session_type"):
            out.append(("session", "Session: {}".format("Wayland" if p["session_type"] == "wayland" else "X11"),
                        {"action": "session-type", "desktop": de["id"], "type": p["session_type"]}))
        if p.get("compositor"):
            _choices, best = dsk.compositors_for(de["id"], p.get("session_type", "x11"))
            names = {c["id"]: c["name"] for c in dsk.catalog()["compositors"]}
            out.append(("compositor", "Compositor: {}".format(names.get(best, best)),
                        {"action": "compositor", "id": best, "preset": p.get("picom_preset", "shadows")}))
        packs = [x[0] for x in (p.get("icons"), p.get("gtk")) if x]
        if packs:
            out.append(("look", "Look: {} icons, {} theme{}".format(p["icons"][1], p["gtk"][1],
                                                                   ", dark" if p.get("dark") else ""),
                        {"action": "themes", "packs": packs, "icons": p["icons"][1], "gtk": p["gtk"][1],
                         "dark": bool(p.get("dark"))}))
    if p.get("packages"):
        out.append(("apps", "Applications: " + ", ".join(p["packages"]),
                    {"action": "apt-install", "packages": list(p["packages"])}))
    if p.get("flatpaks"):
        out.append(("flatpak", "Flatpak apps at first boot: " + ", ".join(p["flatpaks"]),
                    {"action": "flatpak", "apps": list(p["flatpaks"]), "firstboot": True}))
    if p.get("firmware"):
        out.append(("firmware", "Firmware for Wi-Fi, graphics and sound",
                    {"action": "kernel", "firmware": True}))
    if p.get("calamares"):
        out.append(("installer", "Calamares installer", {"action": "calamares", "install": True}))
    if p.get("plymouth") == "generate":
        out.append(("plymouth", "Boot splash: Plymouth with the spinner theme",
                    {"action": "plymouth", "theme": "spinner", "packages": ["plymouth", "plymouth-themes"]}))
    return out


def apply(project, profile_id, keys=None, progress=None):
    """Run the chosen recommendations (all when keys is None)."""
    from eduka_customizer.core.recipe import run_step
    chosen = [r for r in recommendations(profile_id) if keys is None or r[0] in keys]
    project.state["purpose"] = profile_id
    project.save()
    for n, (key, label, step) in enumerate(chosen, 1):
        if progress:
            progress("{}/{}: {}".format(n, len(chosen), label.split(":")[0]))
        run_step(project, step, project.path, build=False)
    project.record("purpose", "{} ({})".format(profile_id, ", ".join(k for k, _l, _s in chosen)))
    return [k for k, _l, _s in chosen]
