import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("EDUKA_CUSTOMIZER_CONF", str(ROOT / "tests" / "_no_such.conf"))
os.environ.setdefault("EDUKA_CUSTOMIZER_DATA", str(ROOT / "data"))


def make_rootfs(base, os_release, debian_version, sources=None, legacy=None):
    root = Path(base)
    (root / "etc/apt/sources.list.d").mkdir(parents=True)
    (root / "usr/lib").mkdir(parents=True)
    (root / "usr/bin").mkdir(parents=True)
    (root / "var/lib/dpkg").mkdir(parents=True)
    (root / "usr/lib/os-release").write_text(os_release)
    (root / "etc/os-release").symlink_to("../usr/lib/os-release")
    (root / "etc/debian_version").write_text(debian_version + "\n")
    if sources:
        (root / "etc/apt/sources.list.d/debian.sources").write_text(sources)
    if legacy:
        (root / "etc/apt/sources.list").write_text(legacy)
    shutil.copy2(os.path.realpath("/bin/sh"), root / "usr/bin/dpkg")
    (root / "var/lib/dpkg/status").write_text(
        "Package: bash\nStatus: install ok installed\nVersion: 5.2\nInstalled-Size: 7000\n"
        "Description: GNU Bourne Again SHell\n\n"
        "Package: oldpkg\nStatus: deinstall ok config-files\nVersion: 1\n\n"
        "Package: live-boot\nStatus: install ok installed\nVersion: 1:20250225\n"
        "Description: Live System Boot Components\n")
    return root


DEBIAN_TRIXIE = ('PRETTY_NAME="Debian GNU/Linux 13 (trixie)"\nNAME="Debian GNU/Linux"\n'
                 'VERSION_ID="13"\nVERSION="13 (trixie)"\nVERSION_CODENAME=trixie\nID=debian\n')
TRIXIE_SOURCES = ("Types: deb\nURIs: http://deb.debian.org/debian\nSuites: trixie trixie-updates\n"
                  "Components: main\nSigned-By: /usr/share/keyrings/debian-archive-keyring.gpg\n")


@pytest.fixture
def trixie(tmp_path):
    return make_rootfs(tmp_path / "rootfs", DEBIAN_TRIXIE, "13.1", TRIXIE_SOURCES)


FILLED_IDENTITY = {"name": "Edukasaun OS", "id": "edukasaun", "version": "1.0", "codename": "Kameli",
                   "home_url": "https://edukasaun.org", "hostname": "edukasaun", "volume_label": "EDUKASAUN_OS"}


@pytest.fixture
def blank_project(tmp_path):
    from eduka_customizer.core.project import Project
    p = Project.create(tmp_path / "blank")
    make_rootfs_into(p.rootfs)
    return p


@pytest.fixture
def project(tmp_path):
    from eduka_customizer.core.project import Project
    p = Project.create(tmp_path / "proj")
    make_rootfs_into(p.rootfs)
    # New projects start without a name; most tests use a distribution that was named.
    p.state["identity"].update(FILLED_IDENTITY)
    return p


def make_rootfs_into(rootfs):
    tmp = Path(str(rootfs) + "-tmp")
    make_rootfs(tmp, DEBIAN_TRIXIE, "13.1", TRIXIE_SOURCES)
    shutil.rmtree(rootfs)
    tmp.rename(rootfs)
