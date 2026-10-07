"""Identity page: OS name, version, live user, language, time zone."""

from eduka_customizer.qt.widgets import QCheckBox, QLineEdit

from eduka_customizer.gui.widgets import Page, button, hbox


class IdentityPage(Page):
    title = "Identity"
    nav_title = "Identity"
    subtitle = "How the system names itself: os-release, computer name, boot menu and installer."
    icon_names = ("preferences-desktop-personal", "user-info")

    FIELDS = [("name", "System name"), ("version", "Version"), ("codename", "Codename"),
              ("id", "OS ID"), ("home_url", "Home page"), ("support_url", "Support URL"),
              ("bug_url", "Bug report URL"), ("hostname", "Host name"),
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

        c = self.card("More", "The live user and passwords, and the default language, have their own pages.")
        c.add(hbox(button("Users and passwords...", lambda: self.main.go("UsersPage")),
                   button("Language...", lambda: self.main.go("LanguagePage")), None))

    def refresh(self):
        if not self.project:
            return
        ident = self.project.state.get("identity", {})
        for key, e in self.edits.items():
            e.setText(str(ident.get(key, "")))

    def apply_identity(self):
        from eduka_customizer.core.branding import Branding
        ident = dict(self.project.state.get("identity", {}))
        ident.update({k: e.text().strip() for k, e in self.edits.items()})
        proj, protect, cal = self.project, self.protect.isChecked(), self.calamares.isChecked()

        def work(t):
            b = Branding(proj)
            b.apply_identity(ident, protect=protect)
            if cal and b.calamares_branding(ident["name"], ident["version"], ident.get("home_url", "")):
                t.set_stage("Calamares branding updated")
        self.task("Apply identity", work)
