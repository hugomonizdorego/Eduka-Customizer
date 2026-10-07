"""Identity page: OS name, version, live user, language, time zone."""

from PyQt6.QtWidgets import QCheckBox, QLineEdit, QListWidget, QAbstractItemView

from eduka_customizer.gui.widgets import Page, button, combo, hbox, label


class IdentityPage(Page):
    title = "Identity & Language"
    nav_title = "Identity & Language"
    subtitle = ("How the system names itself (os-release, boot menu, installer), the live user, "
                "and the default language, time zone and keyboard.")
    icon_names = ("preferences-desktop-personal", "user-info")

    FIELDS = [("name", "System name"), ("version", "Version"), ("codename", "Codename"),
              ("id", "OS ID"), ("home_url", "Home page"), ("support_url", "Support URL"),
              ("bug_url", "Bug report URL"), ("hostname", "Host name"),
              ("live_user", "Live user name"), ("live_fullname", "Live user full name"),
              ("volume_label", "ISO volume label")]

    def build(self):
        c = self.card("System identity",
                      "Written to /usr/lib/os-release (ID_LIKE=debian), /etc/issue and "
                      "/etc/lsb-release. VERSION_CODENAME stays the Debian codename so APT tools "
                      "keep working; your codename is stored as EDUKASAUN_CODENAME.")
        f = c.form()
        self.edits = {}
        for key, text in self.FIELDS:
            e = QLineEdit()
            self.edits[key] = e
            f.addRow(text + ":", e)
        self.protect = QCheckBox("Protect branding from base-files upgrades (dpkg-divert)")
        self.protect.setChecked(True)
        f.addRow("", self.protect)
        self.calamares = QCheckBox("Update the Calamares installer branding too")
        self.calamares.setChecked(True)
        f.addRow("", self.calamares)
        c.add(hbox(None, button("Apply identity", self.apply_identity, "primary")))

        c = self.card("Language, time zone and keyboard",
                      "Used for the installed system and the live session (live-config).")
        f = c.form()
        self.locale = combo([], editable=True)
        f.addRow("Default language:", self.locale)
        self.extra = QListWidget()
        self.extra.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        self.extra.setMaximumHeight(150)
        f.addRow("Extra languages:", self.extra)
        self.tz = combo([], editable=True)
        f.addRow("Time zone:", self.tz)
        self.kb = QLineEdit()
        self.kb.setPlaceholderText("us, pt, fr ... (comma separated)")
        f.addRow("Keyboard layout:", self.kb)
        c.add(label("Tip for Timor-Leste: pt_PT.UTF-8 and en_US.UTF-8 with time zone Asia/Dili.",
                    "muted"))
        c.add(hbox(None, button("Apply language settings", self.apply_locale, "primary")))

    def refresh(self):
        if not self.project:
            return
        ident = self.project.state.get("identity", {})
        for key, e in self.edits.items():
            e.setText(str(ident.get(key, "")))
        from eduka_customizer.core.branding import Branding
        b = Branding(self.project)
        loc = self.project.state.get("locale", {})
        locales = b.supported_locales()
        self.locale.clear()
        self.locale.addItems(locales)
        self.locale.setCurrentText(loc.get("default", "en_US.UTF-8"))
        self.extra.clear()
        self.extra.addItems(locales)
        for i in range(self.extra.count()):
            it = self.extra.item(i)
            it.setSelected(it.text() in loc.get("extra", []))
        self.tz.clear()
        self.tz.addItems(b.timezones())
        self.tz.setCurrentText(loc.get("timezone", "Asia/Dili"))
        self.kb.setText(loc.get("keyboard", "us"))

    def apply_identity(self):
        from eduka_customizer.core.branding import Branding
        ident = {k: e.text().strip() for k, e in self.edits.items()}
        proj, protect, cal = self.project, self.protect.isChecked(), self.calamares.isChecked()

        def work(t):
            b = Branding(proj)
            b.apply_identity(ident, protect=protect)
            if cal and b.calamares_branding(ident["name"], ident["version"], ident.get("home_url", "")):
                t.set_stage("Calamares branding updated")
        self.task("Apply identity", work)

    def apply_locale(self):
        from eduka_customizer.core.branding import Branding
        proj = self.project
        default = self.locale.currentText().strip()
        extra = [i.text() for i in self.extra.selectedItems()]
        tz, kb = self.tz.currentText().strip(), self.kb.text().strip() or "us"
        self.task("Apply language settings",
                  lambda t: Branding(proj).apply_locale(default, extra, tz, kb))
