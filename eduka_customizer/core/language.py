"""Default language of the image: locale, keyboard, time zone, language packs,
language entries in the ISO boot menu and the Calamares installer defaults."""

import json
import re

from eduka_customizer.core import bootloader
from eduka_customizer.core.apt import Packages
from eduka_customizer.core.config import DEFAULT_TIMEZONE, data_file
from eduka_customizer.core.log import log

# Translations are only added for applications that are already installed;
# otherwise installing e.g. libreoffice-l10n-pt would pull in LibreOffice.
APP_PACKS = [
    ("libreoffice-core", "libreoffice", ["libreoffice-l10n-{}", "libreoffice-help-{}"]),
    ("firefox-esr", "mozilla", ["firefox-esr-l10n-{}"]),
    ("firefox", "mozilla", ["firefox-l10n-{}"]),
    ("thunderbird", "mozilla", ["thunderbird-l10n-{}"]),
]


def catalog():
    with open(data_file("languages.json"), encoding="utf-8") as fh:
        return json.load(fh)["languages"]


def info(locale):
    for lang in catalog():
        if lang["locale"] == locale:
            return lang
    code = locale.split(".")[0]
    return {"locale": locale, "name": code, "native": code, "keyboard": "us", "timezone": DEFAULT_TIMEZONE,
            "libreoffice": "", "mozilla": "", "hunspell": "", "extra": []}


def boot_params(locale, keyboard=None, timezone=None):
    """live-config boot options that start the live system in *locale*.

    The language changes, the place does not: the time zone is Dili unless given.
    """
    lang = info(locale)
    params = ["locales=" + locale, "keyboard-layouts=" + (keyboard or lang["keyboard"])]
    tz = timezone or DEFAULT_TIMEZONE
    if tz:
        params.append("timezone=" + tz)
    return " ".join(params)


def pack_candidates(locales, installed):
    """Language packages worth installing for *locales* given installed packages."""
    names = []
    for locale in locales:
        lang = info(locale)
        if lang.get("hunspell"):
            names += ["hunspell-" + lang["hunspell"], "hyphen-" + lang["hunspell"]]
        for app, key, patterns in APP_PACKS:
            if app in installed and lang.get(key):
                names += [p.format(lang[key]) for p in patterns]
        names += lang.get("extra", [])
    seen = []
    for n in names:
        if n not in seen:
            seen.append(n)
    return seen


class Language:
    def __init__(self, project):
        self.project = project

    def current(self):
        st = dict(self.project.state.get("locale", {}))
        st.update(self.project.state.get("language", {}))
        return st

    def apply(self, default, extra=(), timezone=None, keyboard=None, variant="", packs=True,
              boot_menu=(), calamares=True):
        """Make *default* the language of the live and installed system."""
        from eduka_customizer.core.branding import Branding
        lang = info(default)
        # Choosing a language does not move the school: keep the project's time zone (Dili).
        timezone = timezone or self.current().get("timezone") or DEFAULT_TIMEZONE
        keyboard = keyboard or lang["keyboard"] or "us"
        if variant and not re.match(r"^[a-z0-9_,-]*$", variant):
            raise ValueError("Invalid keyboard variant: {}".format(variant))
        extra = [l for l in extra if l and l != default]
        boot_menu = [l for l in boot_menu if l]
        Branding(self.project).apply_locale(default, extra, timezone, keyboard, variant)
        installed_packs = []
        if packs:
            installed_packs = self.install_packs([default] + extra)
        if calamares:
            from eduka_customizer.core.calamares import Calamares
            cal = Calamares(self.project)
            if cal.installed():
                cal.set_locale(timezone)
                log.info("Calamares will suggest %s and the time zone %s", default, timezone)
        self.project.state["language"] = {"default": default, "extra": extra, "timezone": timezone,
                                          "keyboard": keyboard, "variant": variant, "packs": bool(packs),
                                          "boot_menu": boot_menu, "calamares": bool(calamares),
                                          "installed_packs": installed_packs}
        self.project.save()
        if self.project.has_isotree():
            self.apply_boot_menu()
        self.project.record("language", default)
        return installed_packs

    def install_packs(self, locales):
        pkgs = Packages(self.project)
        installed = {p[0] for p in pkgs.installed()}
        wanted = [n for n in pack_candidates(locales, installed) if n not in installed]
        if not wanted:
            return []
        with pkgs.chroot:
            pkgs.update()
            found = pkgs.available(wanted)
        todo = [n for n in wanted if n in found]
        missing = [n for n in wanted if n not in found]
        if missing:
            log.info("Not available for this Debian release (skipped): %s", " ".join(missing))
        if todo:
            pkgs.install(todo, update=False)
        return todo

    def boot_entries(self, title=None):
        st = self.project.state.get("language", {})
        title = title or self.project.state.get("build", {}).get("title") or \
            self.project.state.get("identity", {}).get("name", "Edukasaun OS")
        entries = []
        for locale in st.get("boot_menu", []):
            lang = info(locale)
            kb = st.get("keyboard") if locale == st.get("default") else lang["keyboard"]
            # The language changes, the place does not: keep the chosen time zone.
            tz = st.get("timezone") or DEFAULT_TIMEZONE
            entries.append(("{} ({})".format(title, lang["native"]), boot_params(locale, kb, tz)))
        return entries

    def apply_boot_menu(self, title=None):
        """Add (or remove) the language entries of the ISO boot menu."""
        changed = bootloader.set_language_entries(self.project.isodir, self.boot_entries(title))
        if changed:
            log.info("Boot menu language entries updated")
        return changed
