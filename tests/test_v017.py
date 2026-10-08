"""0.17: automatic fixes, review & apply, ISO size targets, about, new name."""

import pytest

from eduka_customizer.core import calamares_check as cc
from eduka_customizer.core import fixes, preflight
from tests.test_v016 import cal, nochroot  # noqa: F401 (fixtures)


def test_grub_from_the_iso_pool_is_not_a_problem(cal):
    r = cal.rootfs
    (r / "usr/sbin/grub-install").unlink()
    fails = [x for x in cc.check(cal) if x[0] == "fail"]
    assert any("grub needs /usr/sbin/grub-install" in x[2] for x in fails)
    pool = cal.isodir / "pool/main/g/grub2"
    pool.mkdir(parents=True)
    (pool / "grub-efi-amd64_2.12-9_amd64.deb").write_bytes(b"")
    res = cc.check(cal)
    assert not [x for x in res if x[0] == "fail"]
    assert any("installed during the installation" in x[2] for x in res)
    (pool / "grub-efi-amd64_2.12-9_amd64.deb").unlink()
    (r / "usr/sbin/bootloader-config").write_text("")
    assert not [x for x in cc.check(cal) if x[0] == "fail"]


def test_fix_rules():
    label, _f = fixes.find("/etc/calamares/modules/bootloader.conf: grub needs /usr/sbin/grub-install in the image")
    assert "grub-efi-amd64-bin" in label
    assert fixes.find("xfs needs mkfs.xfs (xfsprogs) in the image")[0] == "Install xfsprogs"
    assert "try_remove" in fixes.find("'remove: foo' is not installed: apt would fail")[0]
    assert fixes.find("/home has teacher: everything there ends up in the ISO.") is None


def test_auto_fix_calamares(cal, nochroot):  # noqa: F811
    r = cal.rootfs
    etc = r / "etc/calamares"
    (etc / "modules/packages.conf").write_text("---\nbackend: apt\noperations:\n  - remove:\n      - not-there\n"
                                               "      - live-boot\n")
    (etc / "modules/displaymanager.conf").write_text("---\ndisplaymanagers:\n  - gdm\n")
    (etc / "modules/unpackfs.conf").write_text("---\nunpack:\n    - source: \"/cdrom/casper/filesystem.squashfs\"\n")
    desc = etc / "branding/debian/branding.desc"
    desc.write_text(desc.read_text().replace("componentName: debian", "componentName: other"))
    (etc / "settings.conf").write_text((etc / "settings.conf").read_text().replace("  - umount", "  - umount\n  - ghost"))
    results = preflight.run(cal)
    assert [x for x in results if x.level == "fail" and x.fix]
    done, failed = preflight.auto_fix(cal, results)
    assert not failed, failed
    assert not [x for x in cc.check(cal) if x[0] == "fail"], cc.check(cal)
    from eduka_customizer.core.calamares import Calamares
    c = Calamares(cal)
    ops = c.read("packages")["operations"]
    assert {"remove": ["live-boot"], "try_remove": ["not-there"]} in ops
    assert c.read("displaymanager")["displaymanagers"] == ["lightdm"]
    assert "ghost" not in str(c.read("settings")["sequence"])


GUI_REVIEW = """
import sys
from eduka_customizer.qt.widgets import QApplication
app = QApplication([])
from eduka_customizer.core.project import Project
from eduka_customizer.gui.main_window import MainWindow
w = MainWindow()
assert w.open_project(sys.argv[1])
w.project.mark_all_steps(); w.update_state()
page = next(p for p in w.pages if p.__class__.__name__ == "SoundsPage")
ran = []
page.task("Apply system sounds", lambda t: ran.append(1))
page.task("List something", lambda t: ran.append(2))
assert len(w.pending) == 1 and w.pending[0]["section"] == "System Sounds", w.pending
assert w.pending_btn.text().startswith("Review & Apply: 1 change")
w.go("ReviewPage")
review = w.stack.currentWidget().current()
assert review.items.count() == 1 and not review.apply_btn.isEnabled()
review.tick_all()
assert review.apply_btn.isEnabled()
review.items.setCurrentRow(0); review.remove()
assert w.pending == []
import time
t0 = time.time()
while w.task and time.time() - t0 < 20:
    app.processEvents(); time.sleep(0.02)
print("ok", ran)
"""


def test_review_and_apply_collects_changes(tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path
    from eduka_customizer.core.project import Project
    from tests.conftest import make_rootfs_into
    p = Project.create(tmp_path / "gui")
    make_rootfs_into(p.rootfs)
    p.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", GUI_REVIEW, str(p.path)], capture_output=True, text=True, env=env,
                         timeout=120)
    assert res.returncode == 0, res.stderr[-3000:]
    assert res.stdout.strip().startswith("ok")
