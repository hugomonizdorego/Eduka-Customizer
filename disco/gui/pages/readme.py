"""Desktop document: a PDF about the distribution, with any title, on every user's desktop."""

import tempfile
from pathlib import Path

from disco.qt.widgets import QLineEdit, QMessageBox, QTextEdit

from disco.core import readmedoc
from disco.gui.widgets import Page, button, hbox, label


class ReadmePage(Page):
    title = "Desktop document"
    nav_title = "Desktop document"
    subtitle = ("A PDF that explains your operating system, with the title you like. It is put on the desktop of "
                "every user at the first login (the live user too) and in the menu. Your change waits in "
                "Review & Apply.")
    icon_names = ("x-office-document", "text-x-generic")
    CHANGES = ("Desktop document",)

    def build(self):
        c = self.card("Document")
        f = c.form()
        self.doc_title = QLineEdit()
        self.doc_title.setPlaceholderText("Welcome to My Linux")
        f.addRow("Title:", self.doc_title)
        self.file_label = label("", "muted")
        f.addRow("File:", self.file_label)
        self.doc_title.textChanged.connect(lambda t: self.file_label.setText(readmedoc.file_name(t or "README")))
        self.body = QTextEdit()
        self.body.setAcceptRichText(True)
        self.body.setMinimumHeight(320)
        c.add(label("The text (bold, lists and links are kept; paste from any editor). \"Write a first text\" "
                    "describes the system from the project.", "muted"))
        c.add(self.body)
        c.add(hbox(button("Write a first text", self.first_text, icon_names=("document-new",)),
                   button("Preview PDF", self.preview, icon_names=("document-print-preview",)), None,
                   button("Remove from the system", self.remove, "danger"),
                   button("Put it on the desktop", self.apply, "primary", ("user-desktop",))))

    def project_changed(self):
        """Another project: its own title and text (never the text of the project before)."""
        self.doc_title.clear()
        self.body.clear()

    def refresh(self):
        if not self.project:
            return
        st = self.project.state.get("readme") or {}
        if not self.doc_title.text():
            self.doc_title.setText(st.get("title") or "About {}".format(self.project.display_name()))
        if not self.body.toPlainText().strip():
            saved = Path(self.project.path) / "branding/readme.html"
            if saved.exists():
                self.body.setHtml(saved.read_text(errors="replace"))

    def first_text(self):
        if self.project:
            self.body.setHtml(readmedoc.default_html(self.project))

    def _make(self, out):
        title = self.doc_title.text().strip() or "README"
        html = self.body.toHtml() if self.body.toPlainText().strip() else readmedoc.default_html(self.project)
        keep = Path(self.project.path) / "branding/readme.html"
        keep.parent.mkdir(parents=True, exist_ok=True)
        keep.write_text(html)
        return title, readmedoc.make_pdf(title, html, out)

    def preview(self):
        if not self.project:
            return
        out = Path(tempfile.mkdtemp(prefix="disco-readme-")) / readmedoc.file_name(self.doc_title.text() or "README")
        try:
            self._make(out)
        except Exception as e:  # shown to the user
            QMessageBox.warning(self, "Desktop document", str(e))
            return
        from disco.gui.opener import open_url
        open_url(str(out))

    def apply(self):
        if not self.project:
            return
        pdf = Path(self.project.path) / "branding/readme" / readmedoc.file_name(self.doc_title.text() or "README")
        try:
            title, pdf = self._make(pdf)   # made now, in the window: Qt draws the PDF
        except Exception as e:  # shown to the user
            QMessageBox.warning(self, "Desktop document", str(e))
            return
        proj = self.project
        self.task("Desktop document: " + title, lambda t: readmedoc.install(proj, pdf, title))

    def remove(self):
        proj = self.project
        self.task("Desktop document removed", lambda t: readmedoc.remove(proj))
