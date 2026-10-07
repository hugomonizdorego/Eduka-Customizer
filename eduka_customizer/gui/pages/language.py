"""Language page: default language, keyboard, time zone, language packs and the
language entries of the ISO boot menu."""

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import QCheckBox, QLineEdit, QListWidget, QListWidgetItem

from eduka_customizer.core import language
from eduka_customizer.core.config import DEFAULT_TIMEZONE
from eduka_customizer.gui.widgets import Page, button, combo, hbox, label


def language_combo(current="en_US.UTF-8"):
    """Editable combo of the language catalog; data is the locale."""
    c = combo([(l["locale"], "{} — {} ({})".format(l["native"], l["name"], l["locale"]))
               for l in language.catalog()], current, editable=True)
    return c


def combo_locale(c):
    data = c.currentData()
    text = c.currentText().strip()
    if data and c.itemText(c.currentIndex()) == text:
        return data
    return text.split()[-1].strip("()") if text else "en_US.UTF-8"


class LanguagePage(Page):
    title = "Language"
    nav_title = "Language"
    subtitle = ("The default language of the live system, the installer and the installed system: "
                "locale, keyboard, time zone, translations and spell checking, and a language choice "
                "in the boot menu of the ISO.")
    icon_names = ("preferences-desktop-locale", "config-language", "preferences-desktop-keyboard")

    def build(self):
        c = self.card("Default language")
        f = c.form()
        self.default = language_combo()
        self.default.currentIndexChanged.connect(self._suggest)
        f.addRow("Language:", self.default)
        self.tz = combo([], editable=True)
        f.addRow("Time zone:", self.tz)
        self.kb = QLineEdit()
        self.kb.setPlaceholderText("us, pt, br ... several: us,ru (Alt+Shift switches)")
        f.addRow("Keyboard layout:", self.kb)
        self.variant = QLineEdit()
        self.variant.setPlaceholderText("optional, e.g. intl, dvorak, nodeadkeys")
        f.addRow("Keyboard variant:", self.variant)
        c.add(label("Tetun has no system locale yet: for Timor-Leste choose Português (pt_PT.UTF-8) or "
                    "English and add the other one below.", "muted"))

        a, b = self.row(self.card("More languages", "Generated too, and offered at login and in the "
                                                    "installer. Tick the languages for the boot menu as well."),
                        self.card("What to do"))
        self.extra = QListWidget()
        self.extra.setMinimumHeight(240)
        a.add(self.extra)
        self.packs = QCheckBox("Install translations and spell checking for installed programs\n"
                               "(LibreOffice, Firefox, Thunderbird, hunspell, CJK fonts and input)")
        self.packs.setChecked(True)
        self.bootmenu = QCheckBox("Add a 'Language' submenu to the ISO boot menu (GRUB and ISOLINUX)")
        self.bootmenu.setChecked(True)
        self.calamares = QCheckBox("Use as the default of the Calamares installer (language and time zone)")
        self.calamares.setChecked(True)
        for w in (self.packs, self.bootmenu, self.calamares):
            b.add(w)
        self.status = label("", "muted")
        b.add(self.status)
        b.add(hbox(None, button("Apply language", self.apply, "primary")))

    def _suggest(self):
        # Only the keyboard follows the language; the time zone stays (Asia/Dili by default).
        lang = language.info(combo_locale(self.default))
        if lang.get("keyboard"):
            self.kb.setText(lang["keyboard"])

    def refresh(self):
        if not self.project:
            return
        from eduka_customizer.core.branding import Branding
        st = language.Language(self.project).current()
        self.default.blockSignals(True)
        idx = self.default.findData(st.get("default", "en_US.UTF-8"))
        if idx >= 0:
            self.default.setCurrentIndex(idx)
        else:
            self.default.setEditText(st.get("default", "en_US.UTF-8"))
        self.default.blockSignals(False)
        self.tz.clear()
        self.tz.addItems(Branding(self.project).timezones())
        self.tz.setCurrentText(st.get("timezone") or DEFAULT_TIMEZONE)
        self.kb.setText(st.get("keyboard", "us"))
        self.variant.setText(st.get("variant", ""))
        extra, boot = set(st.get("extra", [])), set(st.get("boot_menu", []))
        self.extra.clear()
        for lang in language.catalog():
            it = QListWidgetItem("{} — {}".format(lang["native"], lang["locale"]))
            it.setData(Qt.ItemDataRole.UserRole, lang["locale"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(Qt.CheckState.Checked if lang["locale"] in extra | boot else Qt.CheckState.Unchecked)
            self.extra.addItem(it)
        if "packs" in st:
            self.packs.setChecked(st["packs"])
        if "calamares" in st:
            self.calamares.setChecked(st["calamares"])
        if "boot_menu" in st:
            self.bootmenu.setChecked(bool(st["boot_menu"]))
        done = st.get("installed_packs")
        self.status.setText("Language packs installed last time: {}".format(" ".join(done)) if done else "")

    def selected_extra(self):
        out = []
        for i in range(self.extra.count()):
            it = self.extra.item(i)
            if it.checkState() == Qt.CheckState.Checked:
                out.append(it.data(Qt.ItemDataRole.UserRole))
        return out

    def apply(self):
        default = combo_locale(self.default)
        extra = [l for l in self.selected_extra() if l != default]
        boot = ([default] + extra) if self.bootmenu.isChecked() and extra else []
        proj = self.project
        tz, kb, variant = self.tz.currentText().strip(), self.kb.text().strip(), self.variant.text().strip()
        packs, cal = self.packs.isChecked(), self.calamares.isChecked()
        self.task("Apply language " + default,
                  lambda t: language.Language(proj).apply(default, extra, tz, kb, variant, packs, boot, cal),
                  lambda _r: self.refresh())
