"""Rename configuration files that older versions (made only for Edukasaun OS)
wrote into the image, so a project keeps one file per setting."""

from eduka_customizer.core.log import log

RENAMES = [
    ("etc/live/config.conf.d/50-edukasaun.conf", "etc/live/config.conf.d/50-eduka-customizer.conf"),
    ("etc/live/config.conf.d/40-edukasaun-locale.conf", "etc/live/config.conf.d/40-eduka-customizer-locale.conf"),
    ("etc/lightdm/lightdm.conf.d/50-edukasaun.conf", "etc/lightdm/lightdm.conf.d/50-eduka-customizer.conf"),
    ("etc/lightdm/lightdm-gtk-greeter.conf.d/50-edukasaun.conf",
     "etc/lightdm/lightdm-gtk-greeter.conf.d/50-eduka-customizer.conf"),
    ("etc/sddm.conf.d/50-edukasaun.conf", "etc/sddm.conf.d/50-eduka-customizer.conf"),
    ("etc/sddm.conf.d/10-edukasaun-theme.conf", "etc/sddm.conf.d/10-eduka-customizer-theme.conf"),
    ("etc/sddm.conf.d/20-edukasaun-display.conf", "etc/sddm.conf.d/20-eduka-customizer-display.conf"),
    ("usr/share/glib-2.0/schemas/90_edukasaun-wallpaper.gschema.override",
     "usr/share/glib-2.0/schemas/90_eduka-customizer-wallpaper.gschema.override"),
    ("usr/share/glib-2.0/schemas/91_edukasaun-gdm.gschema.override",
     "usr/share/glib-2.0/schemas/91_eduka-customizer-gdm.gschema.override"),
]


def migrate(rootfs):
    moved = 0
    for old, new in RENAMES:
        src, dst = rootfs / old, rootfs / new
        if src.is_file() and not src.is_symlink():
            if dst.exists():
                src.unlink()  # the newer file wins
            else:
                src.rename(dst)
            moved += 1
    if moved:
        log.info("Renamed %d configuration file(s) written by an older version", moved)
    return moved
