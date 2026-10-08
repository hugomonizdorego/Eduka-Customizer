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


# ISO size targets ---------------------------------------------------------------------------------

def test_iso_size_plan():
    from eduka_customizer.core import isosize
    MB = isosize.MB
    est = {"system": 1000 * MB, "ratio": 0.3, "other": 60 * MB,
           "sizes": {(c, l): int(1000 * MB * 0.3 * f) + 60 * MB for c, l, f, _s in isosize.METHODS}}
    p = isosize.plan(est, "700")
    assert p["compression"] == "lz4" and p["reachable"]
    p = isosize.plan(est, "400")
    assert (p["compression"], p["level"]) == ("zstd", 15) and p["reachable"]
    p = isosize.plan(est, "300")
    assert p["compression"] == "xz" and not p["reachable"]
    assert "too small" in isosize.describe(p, [("docs", "Smaller ISO: remove documentation", 50 * MB)])
    assert isosize.plan(est, "smallest")["compression"] == "xz"
    assert isosize.plan(est, "none")["compression"] == "zstd"


def test_iso_size_estimate_and_savers(project, tmp_path):
    from eduka_customizer.core import cleanup, isosize
    r = project.rootfs
    doc = r / "usr/share/doc/foo"
    doc.mkdir(parents=True)
    (doc / "copyright").write_text("GPL")
    (doc / "README").write_text("x" * 100000)
    for lang in ("de", "pt", "en"):
        d = r / "usr/share/locale" / lang / "LC_MESSAGES"
        d.mkdir(parents=True)
        (d / "foo.mo").write_bytes(b"y" * 50000)
    (r / "usr/share/man/man1").mkdir(parents=True)
    (r / "usr/share/man/man1/foo.1").write_text("z" * 30000)
    project.state["locale"] = {"default": "pt_PT.UTF-8"}
    est = isosize.estimate(project)
    assert 0 < est["ratio"] < 1 and est["system"] > 0
    keys = {k for k, _t, _b in isosize.savers(project)}
    assert {"docs", "man_pages", "locales"} <= keys
    cleanup._remove_docs(r)
    assert (doc / "copyright").exists() and not (doc / "README").exists()
    cleanup._remove_locales(r, cleanup.kept_languages(project))
    assert (r / "usr/share/locale/pt").exists() and (r / "usr/share/locale/en").exists()
    assert not (r / "usr/share/locale/de").exists()
