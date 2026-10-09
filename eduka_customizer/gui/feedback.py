"""The 'Send feedback' dialog: a bug, an error, an idea or a question for the
developers, with files (screenshots, logs, ...) attached."""

import os
import tempfile
import time

from eduka_customizer.qt.core import Qt
from eduka_customizer.qt.widgets import (QCheckBox, QDialog, QFormLayout, QLineEdit, QListWidget,
                                          QMessageBox, QPlainTextEdit, QVBoxLayout)

from eduka_customizer import APP_NAME
from eduka_customizer.core import feedback
from eduka_customizer.gui.widgets import DropZone, button, combo, hbox, label


class FeedbackDialog(QDialog):
    def __init__(self, main, kind="bug", subject="", message=""):
        super().__init__(main)
        self.main = main
        self.setWindowTitle("Send feedback — {}".format(APP_NAME))
        self.resize(720, 680)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        title = label("Tell the developers", "cardTitle")
        lay.addWidget(title)
        lay.addWidget(label("Report a bug or an error, suggest something, or ask a question. Add screenshots or "
                            "other files if they help. The report is sent to the developers of {}.".format(APP_NAME),
                            "muted"))
        form = QFormLayout()
        self.kind = combo(feedback.KINDS, kind)
        form.addRow("What is it?", self.kind)
        self.subject = QLineEdit(subject)
        self.subject.setPlaceholderText("In a few words, e.g. 'The build stops at the squashfs step'")
        form.addRow("Title:", self.subject)
        self.message = QPlainTextEdit(message)
        self.message.setPlaceholderText("What did you do? What happened? What did you expect?\n"
                                        "For an idea: what would make DistroForge better for you?")
        self.message.setMinimumHeight(170)
        form.addRow("Message:", self.message)
        self.contact = QLineEdit()
        self.contact.setPlaceholderText("Optional: your e-mail address, if you would like an answer")
        form.addRow("Your e-mail:", self.contact)
        lay.addLayout(form)

        drop = DropZone("Drop screenshots, logs or other files here (8 MB together at most)", folders=False)
        drop.dropped.connect(self.add_files)
        lay.addWidget(drop)
        self.files = QListWidget()
        self.files.setMaximumHeight(110)
        lay.addWidget(self.files)
        lay.addWidget(hbox(button("Add a screenshot of the main window", self.screenshot), None,
                           button("Remove the selected file", self.remove_file, "danger")))
        self.logs = QCheckBox("Add the logs of {} and the settings of the open project (recommended for bugs "
                              "and errors)".format(APP_NAME))
        self.logs.setChecked(kind in ("bug", "error"))
        lay.addWidget(self.logs)
        lay.addWidget(label("Nothing else is collected. The report travels encrypted (HTTPS); without internet it "
                            "is kept and sent the next time {} starts.".format(APP_NAME), "muted"))
        self.send_btn = button("Send", self.send, "primary")
        lay.addWidget(hbox(None, button("Cancel", self.reject), self.send_btn))
        self.kind.currentIndexChanged.connect(
            lambda _i: self.logs.setChecked(self.kind.currentData() in ("bug", "error")))

    # Files -------------------------------------------------------------------------------
    def _paths(self):
        return [self.files.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.files.count())]

    def add_files(self, paths):
        from eduka_customizer.qt.widgets import QListWidgetItem
        for p in paths:
            if os.path.isfile(p) and p not in self._paths():
                it = QListWidgetItem("{}  ({:.0f} KB)".format(os.path.basename(p), os.path.getsize(p) / 1024))
                it.setData(Qt.ItemDataRole.UserRole, p)
                self.files.addItem(it)

    def screenshot(self):
        path = os.path.join(tempfile.gettempdir(), time.strftime("distroforge-screenshot-%H%M%S.png"))
        self.main.grab().save(path)
        self.add_files([path])

    def remove_file(self):
        for it in self.files.selectedItems():
            self.files.takeItem(self.files.row(it))

    # Send --------------------------------------------------------------------------------
    def send(self):
        try:
            report = feedback.make_report(self.kind.currentData(), self.subject.text(), self.message.toPlainText(),
                                          self.contact.text(), self._paths(), self.logs.isChecked(),
                                          self.main.project)
        except (ValueError, OSError) as e:
            QMessageBox.warning(self, "Send feedback", str(e))
            return
        self.send_btn.setEnabled(False)
        self.send_btn.setText("Sending...")

        def done(ok):
            if ok:
                QMessageBox.information(self.main, "Send feedback", "Thank you! Your report was sent to the "
                                                                    "developers.")
            else:
                QMessageBox.information(self.main, "Send feedback",
                                        "The report could not be sent now (no internet?). It is kept and sent the "
                                        "next time {} starts:\n{}".format(APP_NAME, report))
        self.accept()
        self.main.run_task("Send feedback", lambda t: feedback.send(report), done)
