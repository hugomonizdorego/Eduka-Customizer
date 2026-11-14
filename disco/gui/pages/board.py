"""Raspberry Pi: the SD-card image of boards (config.txt, kernel options, size)."""

from pathlib import Path

from disco.qt.widgets import QCheckBox, QLineEdit, QMessageBox, QPlainTextEdit, QSpinBox

from disco.core import imgbuild, platforms
from disco.gui.widgets import Page, button, combo, hbox, label


class BoardPage(Page):
    title = "Raspberry Pi"
    nav_title = "Raspberry Pi"
    subtitle = ("SD-card images for the Raspberry Pi, laid out like Debian's own images: a FAT boot partition "
                "(RASPIFIRM: firmware, kernel, config.txt, cmdline.txt, written by Debian's raspi-firmware) and an "
                "ext4 system partition (RASPIROOT) that grows to the whole card at the first start.")
    icon_names = ("media-flash", "drive-removable-media", "computer")
    needs_rootfs = False

    def build(self):
        self.note = label("", "muted")
        self.add(self.note)
        c = self.card("config.txt and kernel options",
                      "Your lines are kept in /etc/default/raspi-firmware-custom and "
                      "/etc/default/raspi-extra-cmdline, so they survive kernel updates.")
        self.config_txt = QPlainTextEdit()
        self.config_txt.setPlaceholderText("for example:\ndtparam=audio=on\ndtoverlay=vc4-kms-v3d\n"
                                           "hdmi_force_hotplug=1\ngpu_mem=128")
        self.config_txt.setMaximumHeight(130)
        f = c.form()
        f.addRow("config.txt lines:", self.config_txt)
        self.cmdline = QLineEdit()
        self.cmdline.setPlaceholderText("extra kernel options, e.g. quiet splash cma=128M")
        f.addRow("Kernel options:", self.cmdline)

        c = self.card("Image")
        f = c.form()
        self.size = QSpinBox()
        self.size.setRange(0, 262144)
        self.size.setSingleStep(512)
        self.size.setSuffix(" MiB")
        self.size.setSpecialValueText("as small as possible (grows on the card)")
        f.addRow("Image size:", self.size)
        self.boot_mb = QSpinBox()
        self.boot_mb.setRange(128, 2048)
        self.boot_mb.setSingleStep(64)
        self.boot_mb.setSuffix(" MiB")
        f.addRow("Boot partition:", self.boot_mb)
        self.compress = combo([("xz", "xz (.img.xz, about 4 times smaller)"), ("none", "none (.img)")])
        f.addRow("Compression:", self.compress)
        self.sysconf = QCheckBox("sysconf.txt on the boot partition (host name and SSH key, editable on any computer "
                                 "before the first start)")
        f.addRow("", self.sysconf)
        self.img_name = QLineEdit()
        self.img_name.setPlaceholderText("default: like the ISO name, ending in .img")
        f.addRow("File name:", self.img_name)
        c.add(hbox(None, button("Save", self.save), button("Test in QEMU", self.test),
                   button("Build SD-card image", self.build_image, "primary", ("media-flash",))))

        c = self.card("Write the card")
        self.flash = label("", wrap=True)
        c.add(self.flash)
        c.add(label("<b>WARNING: dd overwrites the whole device you name in of=.</b> Find the card with "
                    "<code>lsblk</code> (unplug and plug it to see which name appears) and never use the disk "
                    "of this computer. Raspberry Pi Imager (\"Use custom\") and GNOME Disks (\"Restore Disk "
                    "Image\") write the same file with a safer device chooser.", wrap=True))

    _loaded = None

    def project_changed(self):
        self._loaded = None

    def _board(self):
        return self.project and platforms.of_project(self.project).output == "img"

    def refresh(self):
        if not self.project:
            self.note.setText("Start a project first (step 1).")
            return
        plat = platforms.of_project(self.project)
        if plat.output != "img":
            self.note.setText("This project builds an ISO for {}. For a Raspberry Pi, start a new project with "
                              "Start → Other ways to start → New system (no ISO) and choose a Raspberry Pi."
                              .format(plat.name))
        else:
            account = ""
            if self.project.has_rootfs():
                from disco.core.users import Users
                live = Users(self.project).live()
                if live["password"] in ("default", "none"):
                    account = ("<br><b>Account on the card:</b> {} with {}. Over SSH it logs in with a key only. "
                               "Set a password of your own on System → Users.".format(
                                   live["username"], "the password 'live'" if live["password"] == "default"
                                   else "no password"))
            self.note.setText("<b>{}</b> — {}{}{}".format(plat.name, plat.description, " " + plat.note if plat.note
                                                           else "", account))
        if self._loaded != str(self.project.path):     # once per project: never undo what is being typed
            self._loaded = str(self.project.path)
            o = imgbuild.ImageOptions.from_project(self.project)
            self.config_txt.setPlainText(o.config_txt)
            self.cmdline.setText(o.cmdline)
            self.size.setValue(int(o.size_mb or 0))
            self.boot_mb.setValue(int(o.boot_mb))
            self.compress.setCurrentIndex(max(0, self.compress.findData(o.compress)))
            self.sysconf.setChecked(bool(o.sysconf))
            self.img_name.setText(o.name)
        last = self.project.state.get("last_image")
        if last and Path(last).exists():
            self.flash.setText("<b>{}</b><br><code>{}</code>".format(last, imgbuild.flash_command(last)))
        else:
            self.flash.setText("Build the image first.")

    def _options(self):
        o = imgbuild.ImageOptions(size_mb=self.size.value(), boot_mb=self.boot_mb.value(),
                                  compress=self.compress.currentData(),
                                  config_txt=imgbuild.check_lines(self.config_txt.toPlainText(), "config.txt"),
                                  cmdline=" ".join(imgbuild.check_lines(self.cmdline.text(), "cmdline.txt").split()),
                                  sysconf=self.sysconf.isChecked(), name=self.img_name.text().strip())
        if o.name and ("/" in o.name or o.name.startswith(".")):
            raise ValueError("The file name must not contain '/'")
        return o

    def save(self, quiet=False):
        if not self.project:
            return None
        try:
            o = self._options()
        except ValueError as e:
            QMessageBox.warning(self, "Raspberry Pi", str(e))
            return None
        self.project.state["board"] = o.to_dict()
        self.project.save()
        if not quiet:
            self.main.stage_label.setText("Raspberry Pi settings saved: they are used by the next image")
        return o

    def build_image(self):
        if not self._board():
            QMessageBox.information(self, "Raspberry Pi", "This project is not for a Raspberry Pi. Start a new "
                                    "project with Start → Other ways to start → New system (no ISO).")
            return
        o = self.save(quiet=True)
        if o is None:
            return
        proj = self.project

        def done(out):
            self.refresh()
            QMessageBox.information(self, "SD-card image", "Ready:\n{}\n\nWrite it with:\n{}\n\nWARNING: dd "
                                    "overwrites the whole device: check the name with lsblk first.".format(
                                        out, imgbuild.flash_command(out)))
        self.task("Build SD-card image", lambda t: imgbuild.build(proj, o, t.set_progress, t.set_stage), done,
                  queue=False)

    def test(self):
        if not self.project:
            return
        from disco.core import qemu
        try:
            qemu.start(self.project, self.project.state.get("last_image"))
        except Exception as e:  # shown to the user
            QMessageBox.warning(self, "QEMU", str(e))
            return
        self.main.stage_label.setText("QEMU started with the image's own kernel (ARM is emulated: be patient)")
