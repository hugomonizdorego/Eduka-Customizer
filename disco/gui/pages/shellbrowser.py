"""Terminal & Browser: the message after login, the bash prompt and the browsers' defaults."""

from disco.qt.widgets import QCheckBox, QLineEdit, QMessageBox, QPlainTextEdit

from disco.core import browserpolicy, shellbrand
from disco.gui.widgets import Page, button, combo, hbox, label


class ShellBrowserPage(Page):
    title = "Terminal & Browser"
    nav_title = "Terminal & Browser"
    subtitle = ("The message after login (MOTD), the bash prompt of every user, and the home page, bookmarks and "
                "privacy of Firefox ESR and Chromium (as enterprise policies). Your changes wait in Review & Apply.")
    icon_names = ("utilities-terminal", "web-browser")
    CHANGES = ("Message after login", "Bash prompt", "Browser")

    def build(self):
        m = self.card("Message after login (MOTD)", "Shown on text consoles and over SSH after logging in.")
        self.motd = QPlainTextEdit()
        self.motd.setMaximumHeight(110)
        self.motd.setPlaceholderText("Welcome! Documentation: https://example.org")
        m.add(self.motd)
        self.dynamic = QCheckBox("Dynamic: also show the system name, the computer and how long it is up "
                                 "(/etc/update-motd.d)")
        m.add(hbox(self.dynamic, None, button("Template", self.motd_template), button("Use it", self.set_motd,
                                                                                    "primary")))

        p = self.card("Bash prompt (PS1)", "For every user (/etc/bash.bashrc) and new users (/etc/skel/.bashrc).")
        self.prompt = combo([(k, v[0]) for k, v in shellbrand.PROMPTS.items()] + [("custom", "My own")])
        self.prompt.currentIndexChanged.connect(self._prompt_changed)
        self.custom = QLineEdit()
        self.custom.setPlaceholderText(r"\u@\h:\w\$ ")
        self.example = label("", "muted")
        p.add(hbox(self.prompt, self.custom))
        p.add(self.example)
        p.add(hbox(None, button("Back to Debian's prompt", self.remove_prompt), button("Use it", self.set_prompt,
                                                                                     "primary")))

        b = self.card("Web browsers", "Firefox ESR: /etc/firefox-esr/policies/policies.json (and the other places "
                                      "Firefox reads). Chromium: /etc/chromium/policies/managed/.")
        f = b.form()
        self.home = QLineEdit()
        self.home.setPlaceholderText("https://www.example.org")
        f.addRow("Home page:", self.home)
        self.locked = QCheckBox("Locked (users cannot change it)")
        f.addRow("", self.locked)
        self.bookmarks = QPlainTextEdit()
        self.bookmarks.setMaximumHeight(110)
        self.bookmarks.setPlaceholderText("One per line: Title | https://address\nDebian | https://www.debian.org")
        f.addRow("Bookmarks:", self.bookmarks)
        self.search = combo([(s, s or "Firefox's default") for s in browserpolicy.SEARCH])
        f.addRow("Search (Firefox):", self.search)
        self.telemetry = QCheckBox("Allow telemetry and studies (off by default)")
        f.addRow("", self.telemetry)
        self.ff = QCheckBox("Firefox ESR")
        self.ff.setChecked(True)
        self.ch = QCheckBox("Chromium")
        self.ch.setChecked(True)
        f.addRow("For:", hbox(self.ff, self.ch, None))
        b.add(hbox(None, button("Remove the policies", self.remove_browser, "danger"),
                   button("Use it", self.set_browser, "primary")))
        self._prompt_changed()

    def refresh(self):
        if not self.project:
            return
        st = self.project.state.get("shell", {})
        if st.get("motd") and not self.motd.toPlainText():
            self.motd.setPlainText(st["motd"])
            self.dynamic.setChecked(bool(st.get("motd_dynamic")))
        if st.get("prompt"):
            self.prompt.setCurrentIndex(max(0, self.prompt.findData(st["prompt"])))
            self.custom.setText(st.get("prompt_custom", ""))
        br = self.project.state.get("browser") or {}
        if br and not self.home.text():
            self.home.setText(br.get("homepage", ""))
            self.locked.setChecked(bool(br.get("locked")))
            self.bookmarks.setPlainText(br.get("bookmarks", ""))
            self.search.setCurrentIndex(max(0, self.search.findData(br.get("search", ""))))
            self.telemetry.setChecked(bool(br.get("telemetry")))
            self.ff.setChecked(br.get("firefox", True))
            self.ch.setChecked(br.get("chromium", True))

    # MOTD ------------------------------------------------------------------------------------------------
    def motd_template(self):
        if self.project:
            from disco.core import sysfiles
            self.motd.setPlainText(sysfiles.template(self.project, "etc/motd").strip("\n"))

    def set_motd(self):
        text, dyn = self.motd.toPlainText(), self.dynamic.isChecked()
        proj = self.project
        self.task("Message after login", lambda t: shellbrand.set_motd(proj, text, dyn))

    # Prompt -------------------------------------------------------------------------------------------------
    def _prompt_changed(self):
        key = self.prompt.currentData()
        self.custom.setEnabled(key == "custom")
        try:
            ps1 = shellbrand.prompt_text(key, self.project, self.custom.text())
        except ValueError:
            ps1 = ""
        self.example.setText("PS1='{}'".format(ps1.replace("<", "&lt;")))

    def set_prompt(self):
        key, custom = self.prompt.currentData(), self.custom.text()
        try:
            shellbrand.prompt_text(key, self.project, custom)
        except ValueError as e:
            QMessageBox.warning(self, "Bash prompt", str(e))
            return
        proj = self.project
        self.task("Bash prompt: " + key, lambda t: shellbrand.set_prompt(proj, key, custom))

    def remove_prompt(self):
        proj = self.project
        self.task("Bash prompt: Debian's own", lambda t: shellbrand.remove_prompt(proj))

    # Browser ---------------------------------------------------------------------------------------------------
    def set_browser(self):
        home, locked, marks = self.home.text().strip(), self.locked.isChecked(), self.bookmarks.toPlainText()
        tele, search, ff, ch = self.telemetry.isChecked(), self.search.currentData(), self.ff.isChecked(), \
            self.ch.isChecked()
        try:
            browserpolicy.parse_bookmarks(marks)
            browserpolicy.firefox_policies(home, locked, (), tele, search)
        except ValueError as e:
            QMessageBox.warning(self, "Web browsers", str(e))
            return
        proj = self.project
        self.task("Browser policies", lambda t: browserpolicy.apply(proj, home, locked, marks, tele, search, ff, ch))

    def remove_browser(self):
        proj = self.project
        self.task("Browser policies removed", lambda t: browserpolicy.remove(proj))
