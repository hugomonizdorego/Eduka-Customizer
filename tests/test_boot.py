from eduka_customizer.core import bootloader, iso

GRUB = '''set timeout=30
menuentry "Live system (amd64)" --hotkey=l {
    linux /live/vmlinuz-6.12.38+deb13-amd64 boot=live components quiet splash findiso=${iso_path}
    initrd /live/initrd.img-6.12.38+deb13-amd64
}
menuentry "Start installer" {
    linux /install/gtk/vmlinuz vga=788 --- quiet
    initrd /install/gtk/initrd.gz
}
submenu "Utilities" {
    menuentry "Memory test" { linux16 /live/memtest }
    menuentry "Installer with speech" { linux /install/vmlinuz speakup.synth=soft }
}
'''

ISOLINUX = '''timeout 50
label live-amd64
\tmenu label ^Debian GNU/Linux Live (amd64)
\tlinux /live/vmlinuz-6.12.38+deb13-amd64
\tappend initrd=/live/initrd.img-6.12.38+deb13-amd64 boot=live components quiet splash
label installer
\tmenu label ^Install
\tlinux /install/vmlinuz
\tappend initrd=/install/initrd.gz vga=788
'''


def tree(tmp_path):
    d = tmp_path / "iso"
    (d / "boot/grub").mkdir(parents=True)
    (d / "isolinux").mkdir()
    (d / "boot/grub/grub.cfg").write_text(GRUB)
    (d / "isolinux/live.cfg").write_text(ISOLINUX)
    return d


def test_kernel_paths_and_installer_removal(tmp_path):
    d = tree(tmp_path)
    bootloader.normalize_kernel_paths(d)
    assert bootloader.remove_installer_entries(d) == 2
    g = (d / "boot/grub/grub.cfg").read_text()
    assert "/live/vmlinuz boot=live" in g and "initrd /live/initrd.img\n" in g
    assert "/install/" not in g
    assert "Memory test" in g and 'submenu "Utilities"' in g
    i = (d / "isolinux/live.cfg").read_text()
    assert "/install/" not in i and "linux /live/vmlinuz\n" in i


def test_params_titles_timeout(tmp_path):
    d = tree(tmp_path)
    bootloader.append_params(d, "quiet splash locales=pt_PT.UTF-8")
    bootloader.append_params(d, "quiet splash locales=pt_PT.UTF-8")  # idempotent
    bootloader.set_titles(d, "Edukasaun OS")
    bootloader.set_timeout(d, 7)
    g = (d / "boot/grub/grub.cfg").read_text()
    assert g.count("locales=pt_PT.UTF-8") == 1
    assert "findiso=${iso_path}" in g
    assert '"Edukasaun OS Live (amd64)"' in g
    assert "set timeout=7" in g
    i = (d / "isolinux/live.cfg").read_text()
    assert "timeout 70" in i and "Edukasaun OS Live (amd64)" in i
    assert "append initrd=/live/initrd.img-6.12.38+deb13-amd64 boot=live components quiet splash locales=pt_PT.UTF-8" in i
    bootloader.remove_params(d, "locales=pt_PT.UTF-8")
    assert "locales=" not in (d / "boot/grub/grub.cfg").read_text()


def test_strip_output_args():
    args = ["-V", "d-live 13", "--modification-date=2025", "-isohybrid-mbr", "x", "-o", "old.iso", "-J"]
    assert iso.strip_output_args(args) == ["-isohybrid-mbr", "x", "-J"]


def test_detach_boot_intervals(tmp_path):
    src = tmp_path / "src.iso"
    data = bytes(range(256)) * 400  # 102400 bytes
    src.write_bytes(data)
    args = ["-isohybrid-mbr", "--interval:local_fs:0d-15d:zero_mbrpt,zero_gpt:{}".format(src),
            "-append_partition", "2", "0xef", "--interval:local_fs:100d-109d::{}".format(src), "-J"]
    out = iso.detach_boot_args(args, src, tmp_path / "boot")
    assert out[0] == "-isohybrid-mbr" and out[-1] == "-J"
    first = out[1]
    assert first.startswith("--interval:local_fs:0-8191:zero_mbrpt,zero_gpt:")
    img1 = first.rsplit(":", 1)[1]
    assert open(img1, "rb").read() == data[:8192]
    img2 = out[5].rsplit(":", 1)[1]
    assert out[5].startswith("--interval:local_fs:0-5119::")
    assert open(img2, "rb").read() == data[100 * 512:110 * 512]


def test_generated_grub_cfg_format():
    text = bootloader.GRUB_CFG.format(title="Edukasaun OS", params="quiet splash", timeout=5)
    assert "menuentry \"Edukasaun OS Live\" --id live {" in text
    assert text.count("{") == text.count("}")


def test_embedded_grub_keeps_memdisk_prefix():
    # Regression: setting $prefix to the ISO made the standalone EFI GRUB
    # look for modules that only exist in its memdisk (found with QEMU/OVMF).
    assert "set prefix" not in bootloader.GRUB_EMBED
    assert "configfile ($root)/boot/grub/grub.cfg" in bootloader.GRUB_EMBED
