import pytest

from conftest import DEBIAN_TRIXIE, make_rootfs
from eduka_customizer.core import distro


def test_parse_os_release_quotes_and_escapes():
    data = distro.parse_os_release('NAME="Edukasaun \\"OS\\""\nID=edukasaun\n# c\nX=\'a b\'\n')
    assert data == {"NAME": 'Edukasaun "OS"', "ID": "edukasaun", "X": "a b"}


def test_format_roundtrip():
    src = {"NAME": 'Eduka "OS" $x', "ID": "edukasaun", "VERSION": "1.0 (Kameli)"}
    assert distro.parse_os_release(distro.format_os_release(src)) == src


def test_debian_stable_detected(trixie):
    info = distro.detect(trixie)
    assert info.id == "debian"
    assert info.suite == "stable"
    assert info.debian_codename == "trixie"
    assert info.arch in ("amd64", "arm64")
    distro.validate(info, trixie)


def test_testing_and_sid(tmp_path):
    osr = DEBIAN_TRIXIE.replace("trixie", "forky").replace('VERSION_ID="13"\n', "")
    t = make_rootfs(tmp_path / "t", osr, "forky/sid", legacy="deb http://deb.debian.org/debian testing main\n")
    assert distro.detect(t).suite == "testing"
    s = make_rootfs(tmp_path / "s", osr, "forky/sid", legacy="deb [arch=amd64] http://deb.debian.org/debian sid main\n")
    info = distro.detect(s)
    assert info.suite == "sid"
    distro.validate(info, s)


def test_ubuntu_rejected(tmp_path):
    osr = 'NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 24.04 LTS"\n'
    r = make_rootfs(tmp_path / "u", osr, "trixie/sid")
    with pytest.raises(distro.UnsupportedDistro, match="Ubuntu"):
        distro.validate(distro.detect(r), r)


def test_mint_rejected(tmp_path):
    osr = 'NAME="Linux Mint"\nID=linuxmint\nID_LIKE="ubuntu debian"\nPRETTY_NAME="Linux Mint 22"\n'
    r = make_rootfs(tmp_path / "m", osr, "trixie/sid")
    with pytest.raises(distro.UnsupportedDistro):
        distro.validate(distro.detect(r), r)


def test_other_debian_derivative_rejected(tmp_path):
    osr = 'NAME="Kali"\nID=kali\nID_LIKE=debian\nPRETTY_NAME="Kali Linux"\n'
    r = make_rootfs(tmp_path / "k", osr, "kali-rolling")
    with pytest.raises(distro.UnsupportedDistro):
        distro.validate(distro.detect(r), r)


def test_oldstable_rejected_by_default(tmp_path):
    osr = DEBIAN_TRIXIE.replace("trixie", "bookworm").replace("13", "12")
    r = make_rootfs(tmp_path / "o", osr, "12.11",
                    legacy="deb http://deb.debian.org/debian bookworm main\n")
    info = distro.detect(r)
    assert info.suite == "oldstable"
    with pytest.raises(distro.UnsupportedDistro, match="oldstable"):
        distro.validate(info, r)


def test_edukasaun_accepted(tmp_path):
    osr = ('NAME="Edukasaun OS"\nID=edukasaun\nID_LIKE=debian\nVERSION_CODENAME=trixie\n'
           'PRETTY_NAME="Edukasaun OS 1.0 (Kameli)"\n')
    r = make_rootfs(tmp_path / "e", osr, "13.2")
    info = distro.detect(r)
    assert info.is_edukasaun and info.suite == "stable"
    distro.validate(info, r)
    assert "Edukasaun OS" in info.summary()


def test_resolve_in_root_absolute_symlink(tmp_path):
    root = tmp_path / "r"
    (root / "usr/lib").mkdir(parents=True)
    (root / "etc").mkdir()
    (root / "usr/lib/os-release").write_text("ID=debian\n")
    (root / "etc/os-release").symlink_to("/usr/lib/os-release")
    assert distro.resolve_in_root(root, "etc/os-release") == root / "usr/lib/os-release"
