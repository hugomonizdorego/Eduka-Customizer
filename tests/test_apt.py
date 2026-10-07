import pytest

from eduka_customizer.core import apt


def test_deb822_roundtrip():
    text = "Types: deb\nURIs: http://x/debian\nSuites: trixie\nComponents: main\n\nTypes: deb\nURIs: y\nSuites: sid\n"
    st = apt.parse_deb822(text)
    assert len(st) == 2 and st[1]["Suites"] == "sid"
    assert apt.parse_deb822(apt.format_deb822(st)) == st


def test_oneline_conversion():
    st = apt.oneline_to_deb822("deb [signed-by=/k.gpg arch=amd64] http://deb.debian.org/debian trixie main contrib\n# x\n")
    assert st == [{"Types": "deb", "URIs": "http://deb.debian.org/debian", "Suites": "trixie",
                   "Components": "main contrib", "Signed-By": "/k.gpg", "Architectures": "amd64"}]


def test_debian_sources_suites():
    st = apt.debian_sources("stable", backports=True)
    assert st[0]["Suites"] == "trixie trixie-updates trixie-backports"
    assert st[1]["Suites"] == "trixie-security"
    sid = apt.debian_sources("sid")
    assert len(sid) == 1 and sid[0]["Suites"] == "sid"
    t = apt.debian_sources("testing", use_codename=False)
    assert t[0]["Suites"].startswith("testing") and t[1]["Suites"] == "testing-security"
    with pytest.raises(ValueError):
        apt.debian_sources("jammy")


def test_sources_set_debian_moves_legacy(trixie):
    (trixie / "etc/apt/sources.list").write_text("deb http://deb.debian.org/debian trixie main\n")
    src = apt.Sources(trixie)
    src.set_debian("sid")
    assert (trixie / "etc/apt/sources.list.eduka-old").exists()
    assert "Suites: sid" in src.read("debian.sources")


def test_sources_reject_bad_names(trixie):
    src = apt.Sources(trixie)
    for bad in ("../x.list", "a b.sources", "x.txt"):
        with pytest.raises(ValueError):
            src.write(bad, "")
    with pytest.raises(ValueError):
        src.write("bad.sources", "URIs: http://x\n")


def test_package_name_validation():
    apt._check_names(["libreoffice", "gcompris-qt", "linux-image-amd64", "vlc:amd64", "foo=1.2-3", "bar/trixie-backports"])
    with pytest.raises(ValueError):
        apt._check_names(["; rm -rf /"])
    with pytest.raises(ValueError):
        apt._check_names(["-oAPT::x"])


def test_installed_reads_status(project):
    rows = apt.Packages(project).installed()
    names = [r[0] for r in rows]
    assert names == ["bash", "live-boot"]


def test_read_package_list(tmp_path):
    f = tmp_path / "list.txt"
    f.write_text("# comment\nvlc gimp\n-nano\n  \n")
    assert apt.read_package_list(f) == (["vlc", "gimp"], ["nano"])
