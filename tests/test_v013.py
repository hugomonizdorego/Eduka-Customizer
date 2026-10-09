import os
import shutil
import subprocess

import pytest
from pathlib import Path

from eduka_customizer.core import users as usr
from eduka_customizer.core.config import DEFAULT_TIMEZONE

needs_openssl = pytest.mark.skipif(not shutil.which("openssl"), reason="openssl missing")


@pytest.fixture
def nochroot(monkeypatch):
    from eduka_customizer.core import chroot
    calls = []
    monkeypatch.setattr(chroot.Chroot, "run", lambda self, cmd, *a, **k: calls.append(cmd) or 0)
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    return calls


@pytest.fixture
def accounts(project):
    r = project.rootfs
    (r / "etc").mkdir(exist_ok=True)
    (r / "etc/passwd").write_text(
        "root:x:0:0:root:/root:/bin/bash\nnobody:x:65534:65534:nobody:/nonexistent:/usr/sbin/nologin\n"
        "teacher:x:1000:1000:Teacher Ana,,,:/home/teacher:/bin/bash\n"
        "guest:x:1001:1001:Guest:/home/guest:/bin/bash\nlocked:x:1002:1002::/home/locked:/bin/sh\n")
    (r / "etc/shadow").write_text("root:*:1::::::\nteacher:$6$abc$xyz:1::::::\nguest::1::::::\nlocked:!:1::::::\n")
    (r / "etc/group").write_text("sudo:x:27:teacher\naudio:x:29:teacher,guest\nvideo:x:44:\nusers:x:100:\n")
    return project


def test_default_timezone_is_dili(project):
    assert DEFAULT_TIMEZONE == "Asia/Dili"
    assert project.state["locale"]["timezone"] == "Asia/Dili"
    from eduka_customizer.core import language
    assert language.boot_params("en_US.UTF-8").endswith("timezone=Asia/Dili")


def test_usernames():
    for good in ("student", "eduka", "ana-maria", "_svc", "a1"):
        usr.check_username(good)
    for bad in ("", "Root", "root", "1abc", "ana maria", "a" * 33, "../x", "nobody", "lightdm"):
        with pytest.raises(ValueError):
            usr.check_username(bad)


@needs_openssl
def test_live_user_password_modes(project):
    u = usr.Users(project)
    assert u.live()["password"] == "default" and not u.live()["configured"]
    u.set_live("student", "Student", "custom", "sekola", autologin=False, groups=["audio", "video"])
    live = u.live()
    assert live == {"username": "student", "fullname": "Student", "hostname": "edukasaun", "password": "custom",
                    "autologin": False, "groups": ["audio", "video"], "configured": True}
    script = u._script().read_text()
    assert "usermod -p '$6$" in script and "sekola" not in script
    conf = (project.rootfs / usr.LIVE_CONF).read_text()
    assert 'LIVE_USERNAME="student"' in conf and 'LIVE_CONFIG_NOAUTOLOGIN="true"' in conf
    assert project.state["identity"]["live_user"] == "student"
    subprocess.run(["sh", "-n", str(u._script())], check=True)

    # Only a user name, no password at all
    u.set_live("murid", "Murid", "none")
    assert u.live()["password"] == "none" and 'passwd -d "$LIVE_USERNAME"' in u._script().read_text()
    subprocess.run(["sh", "-n", str(u._script())], check=True)
    # The Identity page renames the user but keeps the password choice
    from eduka_customizer.core.branding import Branding
    Branding(project).set_live_user("aluno", "Aluno", "escola")
    assert u.live()["username"] == "aluno" and u.live()["password"] == "none" and u.live()["hostname"] == "escola"

    u.set_live("murid", "Murid", "default")
    assert u.live()["password"] == "default" and not u._script().exists()
    u.set_live("murid", password_mode="custom", password_hash="$6$salt$hash")
    assert "usermod -p '$6$salt$hash'" in u._script().read_text()
    with pytest.raises(ValueError):
        u.set_live("murid", password_mode="custom")  # no password typed
    with pytest.raises(ValueError):
        u.set_live("murid", password_mode="custom", password_hash="plain")
    u.remove_live()
    assert not (project.rootfs / usr.LIVE_CONF).exists() and not u._script().exists()
    assert u.live()["username"] == "user" and u.live()["password"] == "default"


def test_accounts_listing(accounts):
    rows = {a["username"]: a for a in usr.Users(accounts).accounts()}
    assert set(rows) == {"teacher", "guest", "locked"}
    assert rows["teacher"]["password"] == "password set" and rows["teacher"]["fullname"] == "Teacher Ana"
    assert rows["teacher"]["groups"] == ["audio", "sudo"]
    assert rows["guest"]["password"] == "no password" and rows["locked"]["password"] == "locked"


@needs_openssl
def test_account_add_password_delete(accounts, nochroot):
    u = usr.Users(accounts)
    u.add_account("pupil", "Pupil One", password=None, admin=True, groups=["audio", "video", "missing"])
    assert nochroot[0][:5] == ["useradd", "--create-home", "--shell", "/bin/bash", "--comment"]
    assert nochroot[0][-3:] == ["--groups", "audio,sudo,video", "pupil"]
    assert nochroot[1] == ["passwd", "-d", "pupil"]
    with pytest.raises(ValueError, match="already exists"):
        u.add_account("teacher")
    u.set_password("teacher", "rahasia")
    assert nochroot[-1][:2] == ["usermod", "-p"] and nochroot[-1][2].startswith("$6$") and "rahasia" not in nochroot[-1]
    u.set_password("teacher", None)
    assert nochroot[-1] == ["passwd", "-d", "teacher"]
    with pytest.raises(ValueError):
        u.set_password("nobodyhere", "x")
    # userdel is mocked: the account is still there, so deleting must report it
    with pytest.raises(RuntimeError):
        u.delete_account("guest")
    assert nochroot[-1] == ["userdel", "--remove", "guest"]
    with pytest.raises(ValueError):
        u.delete_account("root")


def test_recipe_users_step(project, tmp_path):
    import json
    from eduka_customizer.core import recipe
    r = tmp_path / "r.json"
    r.write_text(json.dumps({"steps": [{"action": "users", "live": {"username": "kids", "password_mode": "none"}}]}))
    recipe.apply(project, r, build=False)
    assert usr.Users(project).live()["username"] == "kids"
    assert usr.Users(project).live()["password"] == "none"


def test_example_recipe_users_arguments_match():
    """Every key in the example's users step must be a real argument."""
    import inspect
    import json
    from pathlib import Path
    from eduka_customizer.core.recipe import _args
    ex = json.loads((Path(__file__).resolve().parents[1] / "examples/school-edition.json").read_text())
    for step in ex["steps"]:
        if step["action"] != "users":
            continue
        live = inspect.signature(usr.Users.set_live).parameters
        add = inspect.signature(usr.Users.add_account).parameters
        assert set(_args(step["live"])) <= set(live)
        for acc in step.get("accounts", []):
            assert set(_args(acc)) <= set(add)


# Fixes from the 0.13 code review ------------------------------------------------------

def _kernels(project, *versions):
    (project.rootfs / "boot").mkdir(exist_ok=True)
    for v in versions:
        (project.rootfs / "boot" / ("vmlinuz-" + v)).write_bytes(b"k")
        (project.rootfs / "boot" / ("initrd.img-" + v)).write_bytes(b"i")


def test_kernel_remove_refuses_paths(project, nochroot):
    from eduka_customizer.core.kernel import Kernels
    _kernels(project, "6.1.0-1-amd64", "6.12.0-1-amd64")
    (project.rootfs / "lib/modules/keep").mkdir(parents=True)
    for bad in ("..", ".", "nonexistent-1.0"):
        with pytest.raises(ValueError):
            Kernels(project).remove(bad)
    assert (project.rootfs / "lib/modules/keep").is_dir()


def test_cli_grub_booleans(project):
    import sys
    project.save()
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    subprocess.run([sys.executable, "-m", "eduka_customizer", "-p", str(project.path), "kernel", "grub",
                    "GRUB_DISABLE_OS_PROBER=false", "GRUB_TIMEOUT=3"], check=True, env=env, capture_output=True)
    text = (project.rootfs / "etc/default/grub.d/95-eduka-customizer.cfg").read_text()
    assert 'GRUB_DISABLE_OS_PROBER="false"' in text and 'GRUB_TIMEOUT="3"' in text


def test_build_options_follow_identity_after_a_build(project):
    from eduka_customizer.core.isobuild import BuildOptions
    project.state["build"] = BuildOptions.from_project(project).to_dict()  # as saved by a build
    project.state["build"]["compression"] = "xz"
    project.state["identity"].update({"name": "Renamed OS", "volume_label": "RENAMED"})
    project.state["boot"].update({"extra_params": "quiet", "timeout": 3})
    o = BuildOptions.from_project(project)
    assert (o.title, o.volume_label, o.boot_params, o.timeout, o.compression) == \
        ("Renamed OS", "RENAMED", "quiet", 3, "xz")


def test_update_params_removes_old_options(project):
    from eduka_customizer.core import bootloader
    (project.isodir / "boot/grub").mkdir(parents=True)
    cfg = project.isodir / "boot/grub/grub.cfg"
    cfg.write_text('menuentry "Live" {\n\tlinux\t/live/vmlinuz boot=live components\n}\n')
    bootloader.update_params(project, "quiet splash toram nomodeset")
    assert "toram" in cfg.read_text()
    bootloader.update_params(project, "quiet splash")
    text = cfg.read_text()
    assert "toram" not in text and "nomodeset" not in text and "quiet splash" in text and "boot=live" in text


def test_quick_build_refuses_changed_kernel(project):
    from eduka_customizer.core import isobuild
    _kernels(project, "6.1.0-1-amd64", "6.12.0-1-amd64")
    (project.isodir / "live").mkdir(parents=True)
    (project.isodir / "live/filesystem.squashfs").write_bytes(b"x")
    project.state["built_kernel"] = "6.1.0-1-amd64"
    with pytest.raises(RuntimeError, match="kernel changed"):
        isobuild.quick_build(project)
    project.state["built_kernel"] = "6.12.0-1-amd64"
    project.state["initramfs_dirty"] = True
    with pytest.raises(RuntimeError, match="initramfs"):
        isobuild.quick_build(project)


def test_plymouth_file_installs_its_own_theme(project, tmp_path, monkeypatch):
    from eduka_customizer.core.plymouth import Plymouth
    downloads = tmp_path / "Downloads"
    (downloads / "abc").mkdir(parents=True)
    (downloads / "abc/abc.plymouth").write_text("[Plymouth Theme]\nName=abc\nModuleName=script\n")
    (downloads / "foo.plymouth").write_text("[Plymouth Theme]\nName=foo\nModuleName=script\n")
    assert Plymouth(project).install(downloads / "foo.plymouth") == "foo"
    assert (project.rootfs / "usr/share/plymouth/themes/foo/foo.plymouth").exists()


def test_isolinux_in_boot_folder_is_not_checked_as_grub(project):
    from eduka_customizer.core import bootedit
    (project.isodir / "boot/isolinux").mkdir(parents=True)
    problems = bootedit.validate(project, "boot/isolinux/isolinux.cfg", "label live\n  menu label {Live\n")
    assert not any("GRUB" in p or "{" in p for p in problems)


def test_calamares_32_keys(project, monkeypatch):
    from eduka_customizer.core.calamares import Calamares
    (project.rootfs / "etc/calamares/modules").mkdir(parents=True)
    (project.rootfs / "etc/calamares/settings.conf").write_text("branding: debian\n")
    (project.rootfs / "etc/calamares/modules/users.conf").write_text("userShell: /bin/sh\n")
    (project.rootfs / "etc/calamares/modules/partition.conf").write_text("defaultFileSystemType: ext4\n")
    monkeypatch.setattr(Calamares, "version", lambda self: "3.2.61-1")
    c = Calamares(project)
    c.set_users(shell="/bin/bash")
    c.set_partition(efi_size="512MiB")
    assert c.read("users")["userShell"] == "/bin/bash" and "user" not in c.read("users")
    assert c.read("partition")["efiSystemPartitionSize"] == "512MiB" and "efi" not in c.read("partition")


def test_reuse_squashfs_is_not_remembered(project):
    from eduka_customizer.core.isobuild import BuildOptions
    project.state["build"] = {"reuse_squashfs": True, "compression": "xz"}
    o = BuildOptions.from_project(project)
    assert o.reuse_squashfs is False and o.compression == "xz"
