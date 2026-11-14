"""D!sco 0.11.1: the fixes of the code reviews (safety of the image, of this computer and of what you typed)."""

import json
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def nochroot(monkeypatch):
    from disco.core import chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(list(cmd)) or 0)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    return calls


# This computer: links in folders of the user and of the image are never followed out ------------------
def test_give_to_user_does_not_follow_links(project, tmp_path, monkeypatch):
    from disco.core import permissions
    if os.geteuid() != 0:
        pytest.skip("needs root")
    try:
        nobody = pwd.getpwnam("nobody")
    except KeyError:
        pytest.skip("no user 'nobody'")
    monkeypatch.setenv("PKEXEC_UID", str(nobody.pw_uid))
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret"
    secret.write_text("of this computer")
    d = Path(project.path) / "overlay"
    d.mkdir(exist_ok=True)
    (d / "folder-link").symlink_to(outside)
    (d / "file-link").symlink_to(secret)
    (d / "mine.txt").write_text("mine")
    permissions.give_to_user(d)
    assert secret.stat().st_uid == 0 and outside.stat().st_uid == 0
    assert os.lstat(d / "folder-link").st_uid == nobody.pw_uid
    assert (d / "mine.txt").stat().st_uid == nobody.pw_uid


def test_overlay_readme_link_is_replaced(project, tmp_path, monkeypatch):
    from disco.core import pipeline, platforms
    monkeypatch.setattr(platforms, "host_requirements", lambda p, m="": [])
    target = tmp_path / "host-file"
    target.write_text("keep me")
    readme = Path(project.path) / "overlay" / "README.txt"
    readme.parent.mkdir(exist_ok=True)
    readme.symlink_to(target)
    project.state["builder"] = {"platform": "pc64", "desktop": "xfce"}
    pipeline.Pipeline(project).prepare()
    assert target.read_text() == "keep me"
    assert not readme.is_symlink() and "copied into the system" in readme.read_text()


def test_browser_policies_stay_in_the_image(project, tmp_path):
    from disco.core import browserpolicy as bp
    host = tmp_path / "host-chromium"
    host.mkdir()
    (project.rootfs / "etc/chromium").symlink_to(host)          # absolute link: it means the image's /tmp/...
    bp.apply(project, "https://example.org", False, "Debian | https://www.debian.org")
    assert list(host.iterdir()) == []
    r = project.rootfs
    rec = json.loads(bp._target(r, bp.CHROMIUM_RECOMMENDED).read_text())
    man = json.loads(bp._target(r, bp.CHROMIUM_PATH).read_text())
    # Not locked: users may change the home page, so it is only recommended.
    assert rec["HomepageLocation"] == "https://example.org" and "HomepageLocation" not in man
    assert man["MetricsReportingEnabled"] is False and "ManagedBookmarks" in man
    bp.apply(project, "https://example.org", True, "")
    assert not bp._target(r, bp.CHROMIUM_RECOMMENDED).exists()
    assert json.loads(bp._target(r, bp.CHROMIUM_PATH).read_text())["HomepageLocation"] == "https://example.org"
    bp.remove(project)
    assert not bp._target(r, bp.CHROMIUM_PATH).exists()


# /etc/skel: settings yes, secrets no ------------------------------------------------------------------
def test_skel_import_leaves_secrets_here(project, tmp_path):
    from disco.core import sysfiles
    src = tmp_path / "chromium"
    (src / "Default").mkdir(parents=True)
    prefs = src / "Default/Preferences"
    prefs.write_text("{}")
    prefs.chmod(0o600)
    (src / "Default/Bookmarks").write_text("{}")
    (src / "Default/Bookmarks").chmod(0o644)
    for name in ("Cookies", "Login Data", "Web Data", "History", "Current Session", "COOKIES-journal"):
        (src / "Default" / name).write_text("secret")
    (src / "Local State").write_text("{}")
    dest = sysfiles.import_config(project, src, ".config")
    names = {p.name for p in dest.rglob("*")}
    assert {"Preferences", "Bookmarks"} <= names
    assert not names & {"Cookies", "Login Data", "Web Data", "History", "Current Session", "COOKIES-journal",
                        "Local State"}
    assert (dest / "Default/Preferences").stat().st_mode & 0o777 == 0o600     # private stays private
    assert (dest / "Default/Bookmarks").stat().st_mode & 0o777 == 0o644
    ssh = tmp_path / ".ssh"
    ssh.mkdir()
    with pytest.raises(ValueError, match="keys or passwords"):
        sysfiles.import_config(project, ssh)
    # A link in /etc/skel stays inside the image.
    host = tmp_path / "host-local"
    host.mkdir()
    (project.rootfs / "etc/skel/.local").symlink_to(host)
    sysfiles.import_config(project, src, ".local")
    assert list(host.iterdir()) == []


# Scripts and files that are sourced: one line per value -------------------------------------------------
def test_os_release_refuses_line_breaks():
    from disco.core.distro import format_os_release, parse_os_release
    with pytest.raises(ValueError):
        format_os_release({"NAME": "My Linux\nevil=1"})
    with pytest.raises(ValueError):
        format_os_release({"BAD KEY": "x"})
    text = format_os_release({"NAME": 'My "Linux" $HOME `x`'})
    assert parse_os_release(text)["NAME"] == 'My "Linux" $HOME `x`'


def test_preset_values_are_checked():
    from disco.core import presets
    ok = presets.normalize({"name": "Test", "builder": {"distro_name": "Hugo's Linux",
                                                        "mirror": "http://deb.debian.org/debian"}})
    assert ok["builder"]["distro_name"] == "Hugo's Linux"
    for bad in ({"distro_name": "x\nrm -rf /"}, {"mirror": "http://x/debian main\ndeb http://evil/ x"},
                {"mirror": "http://x/$(id)"}, {"dm": "lightdm; reboot"}, {"desktop": "../x"},
                {"profile": "a b"}, {"variant": "buildd"}):
        with pytest.raises(ValueError):
            presets.normalize({"name": "Test", "builder": bad})


def test_livebuild_identity_is_quoted(project):
    from disco.core import livebuild
    project.state["identity"].update({"hostname": "pc; rm -rf /", "id": "bad id!", "name": "My 'Linux'"})
    host = livebuild.hostname(project)
    assert re.fullmatch(r"[a-z0-9-]+", host)
    hook = livebuild._identity_hook(project)
    assert "rm -rf" not in hook
    assert "echo {} > /etc/hostname".format(host) in hook
    with pytest.raises(ValueError, match="OpenRC|openrc"):
        livebuild._initsystem("openrc")


def test_livebuild_keeps_the_status_of_lb(tmp_path):
    from disco.core import livebuild
    bindir = tmp_path / "bin"
    bindir.mkdir()
    (bindir / "lb").write_text("#!/bin/sh\necho building\n[ \"$FAIL\" = 1 ] && exit 7\nexit 0\n")
    (bindir / "lb").chmod(0o755)
    script = tmp_path / "build"
    script.write_text(livebuild.AUTO_BUILD)
    env = dict(os.environ, PATH="{}:{}".format(bindir, os.environ.get("PATH", "")))
    failed = subprocess.run(["sh", str(script)], cwd=tmp_path, env=dict(env, FAIL="1"), capture_output=True)
    assert failed.returncode == 7 and "building" in (tmp_path / "build.log").read_text()
    good = subprocess.run(["sh", str(script)], cwd=tmp_path, env=dict(env, FAIL="0"), capture_output=True)
    assert good.returncode == 0 and not (tmp_path / ".lb-failed").exists()


def test_pipeline_refuses_openrc_with_livebuild(project, monkeypatch):
    from disco.core import pipeline, platforms
    monkeypatch.setattr(platforms, "host_requirements", lambda p, m="": [])
    project.state["builder"] = {"platform": "pc64", "method": "live-build", "init": "openrc"}
    text = " ".join(t for ok, t in pipeline.Pipeline(project).check() if not ok)
    assert "OpenRC" in text


# Package lists ----------------------------------------------------------------------------------------
def test_lists_are_checked_before_they_replace(project):
    from disco.core.pkglists import Lists
    lists = Lists(project)
    lists.load({"10-base.list": {"title": "Base", "packages": ["vim", "-nano"]}})
    for bad in ({"10-x.list": {"packages": ["ok", "bad name"]}}, {"bad.list": {}}, {"20-x.list": "text"},
                {"30-x.list": {"packages": "vim"}}, ["x"]):
        with pytest.raises(ValueError):
            lists.load(bad)
        assert [l.name for l in lists.all()] == ["10-base.list"]
    lists.load({"10-base.list": {"title": "Base\nevil-package", "packages": ["vim"]}})
    assert lists.get("10-base.list").read() == (["vim"], [])


def test_lists_with_architectures(project, monkeypatch, nochroot):
    from disco.core import apt
    from disco.core.pkglists import Lists
    calls = {}
    monkeypatch.setattr(apt.Packages, "installed", lambda self: [("nano", "1", "1", "")])
    monkeypatch.setattr(apt.Packages, "recover", lambda self: None)
    monkeypatch.setattr(apt.Packages, "update", lambda self: None)
    monkeypatch.setattr(apt.Packages, "available", lambda self, names: {"libc6", "firefox-esr"} & set(names))
    monkeypatch.setattr(apt.Packages, "install", lambda self, pk, **k: calls.setdefault("install", list(pk)))
    monkeypatch.setattr(apt.Packages, "remove", lambda self, pk, **k: calls.setdefault("remove", list(pk)))
    lists = Lists(project)
    lists.load({"10-x.list": {"packages": ["libc6:i386", "firefox-esr", "nosuchpackage", "-nano:amd64"]}})
    todo, skipped = lists.install()
    assert calls["install"] == ["libc6:i386", "firefox-esr"] and skipped == ["nosuchpackage"]
    assert calls["remove"] == ["nano:amd64"]


# SD-card images -------------------------------------------------------------------------------------------
def test_sd_image_account_not_open_over_ssh(project):
    from disco.core import imgbuild
    b = imgbuild.ImageBuilder(project)
    guard = project.rootfs / imgbuild.SSH_GUARD
    b._guard_ssh("live", "default")
    text = guard.read_text()
    assert "Match User live" in text and "PasswordAuthentication no" in text
    b._guard_ssh("live", "custom")                 # a password of your own: password logins are fine
    assert not guard.exists()


def test_uncompressed_never_leaves_half_an_image(tmp_path):
    from disco.core import imgbuild
    if not shutil.which("xz"):
        pytest.skip("xz is missing")
    raw = tmp_path / "t.img"
    raw.write_bytes(os.urandom(50000))
    subprocess.run(["xz", "-k", str(raw)], check=True)
    cache = tmp_path / "cache"
    out = imgbuild.uncompressed(tmp_path / "t.img.xz", cache)
    assert out.read_bytes() == raw.read_bytes()
    (tmp_path / "bad.img.xz").write_bytes(b"not xz")
    with pytest.raises(subprocess.CalledProcessError):
        imgbuild.uncompressed(tmp_path / "bad.img.xz", cache)
    assert sorted(p.name for p in cache.iterdir()) == ["t.img"]


# The README on the desktop is readable --------------------------------------------------------------------
def test_readme_pdf_text_has_a_readable_size(tmp_path):
    from disco.core import imaging, readmedoc
    if imaging._qt() is None or not shutil.which("pdftotext"):
        pytest.skip("needs Qt and pdftotext")
    out = readmedoc.make_pdf("Test", "<p>Hello world of the README.</p>", tmp_path / "t.pdf")
    box = subprocess.run(["pdftotext", "-bbox", str(out), "-"], capture_output=True, text=True).stdout
    m = re.search(r'yMin="([\d.]+)" xMax="[\d.]+" yMax="([\d.]+)">Hello', box)
    assert m and 9 < float(m.group(2)) - float(m.group(1)) < 20      # about 11 pt, not 4 pt


# Calamares: the installer choice is honored ---------------------------------------------------------------
def test_calamares_remove(project, monkeypatch):
    from disco.core import apt, calamares
    removed = []
    monkeypatch.setattr(apt.Packages, "is_installed", lambda self, n: n in ("calamares", "calamares-settings-debian"))
    monkeypatch.setattr(apt.Packages, "remove", lambda self, names, **k: removed.extend(names))
    assert calamares.Calamares(project).remove() == ["calamares-settings-debian", "calamares"]
    assert removed == ["calamares-settings-debian", "calamares"]


# What you typed survives when a page is shown again -------------------------------------------------------
KEEP_TYPED = """
import sys
from disco.qt.widgets import QApplication
app = QApplication([])
from disco.qt.widgets import QMessageBox
shown = []
for kind in ("information", "warning", "critical", "question"):     # a dialog would wait for a click
    setattr(QMessageBox, kind, staticmethod(lambda *a, k=kind, **kw: shown.append((k, a[2] if len(a) > 2 else ""))
                                           or QMessageBox.StandardButton.Yes))
from disco.gui.main_window import MainWindow
w = MainWindow()
assert w.open_project(sys.argv[1])
w.project.mark_all_steps()
w.update_state()
page = lambda name: next(p for p in w.pages if p.__class__.__name__ == name)

sf = page("SystemFilesPage")
w.go("SystemFilesPage")
typed = 'NAME="Typed Linux"\\nID=typed\\nPRETTY_NAME="Typed Linux 1.0"'
sf.editor.selectAll()
sf.editor.insertPlainText(typed)                # like typing: the document is modified
sf.refresh()
assert sf.editor.toPlainText() == typed
sf.save()                                       # waits in Review & Apply
assert not shown, shown
sf.files.setCurrentRow(1)
sf.files.setCurrentRow(0)
assert sf.editor.toPlainText().startswith(typed) and "waits" in sf.desc.text(), sf.desc.text()

b = page("BoardPage")
w.go("BoardPage")
b.cmdline.setText("quiet cma=128M")
b.refresh()
assert b.cmdline.text() == "quiet cma=128M"

f = page("FilesPage")
w.go("FilesPage")
f.editor.editor.setPlainText("typed in the editor")
f.refresh()
assert f.editor.editor.toPlainText() == "typed in the editor"
print("ok")
"""


def test_pages_keep_what_was_typed(project):
    import sys
    project.save()
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    res = subprocess.run([sys.executable, "-c", KEEP_TYPED, str(project.path)], capture_output=True, text=True,
                         env=env, timeout=90)
    assert res.returncode == 0, res.stdout + res.stderr[-3000:]
    assert "ok" in res.stdout
