# Panduan singkat Eduka-Customizer 0.10 Alpha

Eduka-Customizer adalah pembangun ISO khusus **Edukasaun OS**. Hanya
**Debian stable, testing, sid** dan **Edukasaun OS** yang didukung;
Ubuntu dan semua turunannya ditolak.

## Instalasi

```sh
sudo apt install debhelper python3-pytest dpkg-dev
dpkg-buildpackage -us -uc -b
sudo apt install ../eduka-customizer_0.10.0~alpha_all.deb
eduka-customizer doctor        # cek alat yang dibutuhkan
```

## Alur kerja di GUI

1. **Start / Project** – buat project (folder kerja), lalu pilih sumber:
   ISO Debian live / Edukasaun OS, *Download Debian* (otomatis dicek
   SHA256), *New Debian base* (mmdebstrap), atau *This computer*
   (snapshot sistem yang sedang berjalan, gaya remastersys).
2. **Identity & Language** – nama OS, versi, codename, hostname, user live,
   bahasa (mis. `pt_PT.UTF-8`), zona waktu `Asia/Dili`, keyboard.
3. **Repositories** – pilih stable / testing / sid, tambah repositori
   sendiri (misalnya repo Edukasaun) beserta kuncinya, edit file sources.
4. **Packages** – cari, pasang, hapus paket; upgrade semua; pasang `.deb`.
5. **Flatpak apps** – aktifkan Flathub, pilih aplikasi sekolah (GCompris,
   GeoGebra, Stellarium, ...), pasang ke ISO atau saat boot pertama.
6. **Desktop** – pilih Eduka-Desktop (default), LXQt, Xfce, KDE, GNOME,
   MATE, Cinnamon, LXDE, Budgie atau window manager (Openbox, i3, Sway, ...).
   Eduka-Desktop diambil dari GitHub, di-build jadi `.deb`, lalu dipasang.
   Pengaturan default panel/menu bisa diubah untuk semua user baru.
7. **Appearance** – tema Plymouth (pilih, impor, atau buat dari logo),
   wallpaper, layar login, judul & latar menu boot ISO.
8. **Terminal & Live** – jalankan desktop image di jendela (*live edit*):
   semua perubahan langsung tersimpan ke image (default ke `/etc/skel`).
   Buka terminal root di dalam image, jalankan perintah atau skrip hook,
   edit file boot (`grub.cfg`, isolinux).
9. **Build & Test** – pilih kompresi (zstd disarankan), opsi pembersihan,
   lalu *Build ISO image*. Uji di QEMU dengan BIOS, UEFI atau Secure Boot.

## Baris perintah

```sh
sudo eduka-customizer new ~/eduka --iso debian-live-13.1.0-amd64-lxqt.iso
sudo eduka-customizer -p ~/eduka desktop install eduka --dm lightdm
sudo eduka-customizer -p ~/eduka apt install libreoffice vlc
sudo eduka-customizer -p ~/eduka flatpak install org.kde.gcompris --firstboot
sudo eduka-customizer -p ~/eduka shell          # terminal di dalam image
sudo eduka-customizer -p ~/eduka live           # edit live di jendela
sudo eduka-customizer -p ~/eduka build
eduka-customizer -p ~/eduka test --firmware uefi
```

Build yang bisa diulang (reproducible) memakai *recipe* JSON:
`sudo eduka-customizer -p ~/eduka recipe apply examples/edukasaun-school.json`.

## Tips

* Jika aplikasi crash dan masih ada mount: `sudo eduka-customizer -p PROJECT clean --unmount-only`.
* Saat Debian rilis versi baru, ubah codename di halaman **Settings**.
* Log lengkap: `PROJECT/logs/eduka-customizer.log`.
