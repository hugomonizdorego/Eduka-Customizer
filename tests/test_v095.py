"""0.9.5 Beta: host names, Devuan, init systems, desktop recommendations, resources, styles."""

import pytest

from eduka_customizer.core import distro, initsystem
from tests.conftest import make_rootfs
from tests.test_v016 import cal, nochroot  # noqa: F401 (fixtures)

DEVUAN = ('PRETTY_NAME="Devuan GNU/Linux 6 (excalibur)"\nNAME="Devuan GNU/Linux"\nVERSION_ID="6"\n'
          'VERSION="6 (excalibur)"\nVERSION_CODENAME=excalibur\nID=devuan\nID_LIKE=debian\n')
DEVUAN_SOURCES = ("Types: deb\nURIs: http://deb.devuan.org/merged\nSuites: excalibur excalibur-updates "
                  "excalibur-security\nComponents: main\n")


def test_hostnames():
    from eduka_customizer.core.branding import Branding, split_hostname
    assert split_hostname("localhost.localdomain", "mylinux") == ("mylinux", "")
    assert split_hostname("localhost", "mylinux") == ("mylinux", "")
    assert split_hostname("PC1.Example.org") == ("pc1", "pc1.example.org")
    assert split_hostname("", "mylinux") == ("mylinux", "")
    for bad in ("my_pc", "-pc", "pc..x", "a" * 64):
        with pytest.raises(ValueError):
            split_hostname(bad)
    assert Branding.check_identity({"name": "My Linux", "hostname": "localhost.localdomain"}) == "my-linux"
    with pytest.raises(ValueError):
        Branding.check_identity({"name": "My Linux", "hostname": "bad host"})
    with pytest.raises(ValueError):
        Branding.check_identity({"name": ""})


def test_identity_with_localdomain_applies(project, nochroot):  # noqa: F811
    from eduka_customizer.core.branding import Branding
    ident = dict(project.state["identity"], hostname="localhost.localdomain")
    Branding(project).apply_identity(ident)
    r = project.rootfs
    assert (r / "etc/hostname").read_text() == "edukasaun\n"
    assert "127.0.1.1\tedukasaun" in (r / "etc/hosts").read_text()
    Branding(project).apply_identity(dict(ident, hostname="lab1.school.example"))
    assert (r / "etc/hostname").read_text() == "lab1\n"
    assert "127.0.1.1\tlab1.school.example lab1" in (r / "etc/hosts").read_text()


def test_devuan_is_detected(tmp_path):
    r = make_rootfs(tmp_path / "devuan", DEVUAN, "13.1", None)
    (r / "etc/apt/sources.list.d/devuan.sources").write_text(DEVUAN_SOURCES)
    (r / "etc/devuan_version").write_text("excalibur\n")
    info = distro.detect(r)
    assert info.is_devuan and info.devuan_codename == "excalibur"
    assert info.debian_codename == "trixie" and info.suite == "stable"
    assert distro.validate(info, r)
    assert "Devuan excalibur" in info.summary()
    # A Devuan derivative without numbers in debian_version and only /etc/devuan_version.
    r2 = make_rootfs(tmp_path / "refracta", 'PRETTY_NAME="Refracta 12"\nNAME=Refracta\nID=refracta\n'
                     'ID_LIKE="devuan debian"\n', "daedalus/ceres", None)
    (r2 / "etc/devuan_version").write_text("daedalus\n")
    info2 = distro.detect(r2)
    assert info2.is_devuan and info2.debian_codename == "bookworm"


def test_devuan_sources(tmp_path):
    from eduka_customizer.core.apt import Sources, parse_deb822
    r = make_rootfs(tmp_path / "devuan", DEVUAN, "13.1", None)
    (r / "etc/apt/sources.list.d/old.sources").write_text(DEVUAN_SOURCES)
    (r / "etc/devuan_version").write_text("excalibur\n")
    src = Sources(r)
    assert src.is_devuan()
    src.set_debian("stable")
    st = parse_deb822((r / "etc/apt/sources.list.d/devuan.sources").read_text())[0]
    assert st["URIs"] == "http://deb.devuan.org/merged"
    assert st["Suites"] == "excalibur excalibur-updates excalibur-security"
    assert "devuan-archive-keyring" in st["Signed-By"]
    assert (r / "etc/apt/sources.list.d/old.sources.eduka-old").exists()
    assert not (r / "etc/apt/sources.list.d/debian.sources").exists()


def _status(r, *pkgs):
    text = (r / "var/lib/dpkg/status").read_text()
    for p in pkgs:
        text += "\nPackage: {}\nStatus: install ok installed\nVersion: 1\n".format(p)
    (r / "var/lib/dpkg/status").write_text(text)


def test_init_detection_and_blockers(project):
    r = project.rootfs
    assert initsystem.current(r) == "systemd"
    _status(r, "systemd-sysv")
    assert initsystem.current(r) == "systemd"
    assert initsystem.live_packages(r) == ["live-boot", "live-config", "live-config-systemd"]
    opts = {o[0]: o for o in initsystem.options(project)}
    assert opts["systemd"][5] and opts["sysvinit"][3] and not opts["s6"][3] and not opts["shepherd"][3]
    _status(r, "gnome-shell")
    opts = {o[0]: o for o in initsystem.options(project)}
    assert not opts["openrc"][3] and "GNOME" in opts["openrc"][4]
    with pytest.raises(ValueError):
        initsystem.use(project, "openrc")
    with pytest.raises(ValueError):
        initsystem.use(project, "s6")


def test_switch_to_sysvinit(cal, monkeypatch):  # noqa: F811
    from eduka_customizer.core import apt, chroot, yamlconf
    r = cal.rootfs
    _status(r, "systemd-sysv", "live-config", "live-config-systemd", "xserver-xorg-core")
    calls = []

    def run(self, cmd, *a, **k):
        calls.append(list(cmd))
        if cmd[:2] == ["apt-get", "-y"] and "install" in cmd:
            text = (r / "var/lib/dpkg/status").read_text()
            for p in [c[:-1] for c in cmd if c.endswith("-")]:
                text = text.replace("Package: {}\nStatus: install ok installed".format(p),
                                    "Package: {}\nStatus: deinstall ok config-files".format(p))
            (r / "var/lib/dpkg/status").write_text(text)
            _status(r, *[c for c in cmd[cmd.index("install") + 1:] if not c.startswith("-") and not c.endswith("-")])
        return 0
    monkeypatch.setattr(chroot.Chroot, "run", run)
    monkeypatch.setattr(chroot.Chroot, "output", lambda self, *a, **k: "")
    monkeypatch.setattr(chroot.Chroot, "__enter__", lambda self: self)
    monkeypatch.setattr(chroot.Chroot, "__exit__", lambda self, *a: False)
    monkeypatch.setattr(apt.Packages, "available", lambda self, names: set(names))
    monkeypatch.setattr(apt.Packages, "update", lambda self, *a, **k: None)
    (r / "etc/systemd/system/multi-user.target.wants").mkdir(parents=True)
    unit = r / "etc/systemd/system/eduka-system-sounds.service"
    unit.write_text("[Unit]\nDescription=System sounds\n[Service]\nExecStart=/usr/lib/x/play boot\n"
                    "ExecStop=/usr/lib/x/play down\n")
    (r / "etc/systemd/system/multi-user.target.wants/eduka-system-sounds.service").symlink_to(
        "/etc/systemd/system/eduka-system-sounds.service")
    settings = (r / "etc/calamares/settings.conf").read_text().replace("  - displaymanager\n",
                                                                        "  - displaymanager\n  - services-systemd\n")
    (r / "etc/calamares/settings.conf").write_text(settings)
    (r / "etc/calamares/modules/machineid.conf").write_text("---\nsystemd: true\ndbus: true\n")
    initsystem.use(cal, "sysvinit")
    apt_call = next(c for c in calls if "--allow-remove-essential" in c)
    assert "sysvinit-core" in apt_call and "systemd-sysv-" in apt_call and "live-config-sysvinit" in apt_call
    assert "live-config-systemd-" in apt_call and "elogind" in apt_call and "libpam-elogind" in apt_call
    assert initsystem.current(r) == "sysvinit"
    script = (r / "etc/init.d/eduka-system-sounds").read_text()
    assert "start) /usr/lib/x/play boot ;;" in script and "Default-Start:     2 3 4 5" in script
    assert ["update-rc.d", "eduka-system-sounds", "defaults"] in calls
    data = yamlconf.load((r / "etc/calamares/settings.conf").read_text())
    exec_ = [m for st in data["sequence"] if "exec" in st for m in st["exec"]]
    assert "services-systemd" not in exec_ and "displaymanager" in exec_
    assert yamlconf.load((r / "etc/calamares/modules/machineid.conf").read_text())["systemd"] is False
    assert initsystem.live_packages(r)[-1] == "live-config-sysvinit"
    # OpenRC brings Calamares' services-openrc module.
    initsystem.use(cal, "openrc")
    data = yamlconf.load((r / "etc/calamares/settings.conf").read_text())
    exec_ = [m for st in data["sequence"] if "exec" in st for m in st["exec"]]
    assert exec_[exec_.index("displaymanager") + 1] == "services-openrc"
    assert (r / "etc/calamares/modules/services-openrc.conf").exists()
    assert initsystem.current(r) == "openrc"
