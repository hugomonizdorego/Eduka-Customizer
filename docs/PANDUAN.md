# Panduan singkat Eduka-Customizer 0.11 Alpha

Eduka-Customizer adalah pembangun ISO khusus **Edukasaun OS**. ISO sumber
harus **Debian stable, testing, sid** atau **Edukasaun OS** (ISO Ubuntu dan
turunannya ditolak). Aplikasinya sendiri bisa dipasang di Debian, Edukasaun
OS, **Ubuntu dan turunannya**.

## Cara tercepat: Quick Wizard

Buka **Quick Wizard ✨** di sidebar, isi 8 langkah (Sumber → Identitas →
Basis Debian → Desktop → Tampilan → Aplikasi → Branding → Selesai), lalu
tekan **Finish**. Semua jawaban disimpan sebagai recipe
`recipe-wizard.json`, dan ISO langsung dibangun.

## Instalasi

```sh
sudo apt install debhelper python3-pytest dpkg-dev
dpkg-buildpackage -us -uc -b
sudo apt install ../eduka-customizer_0.11.0~alpha_all.deb
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
9. **Distro Branding** – distro sendiri, bukan sekadar Debian ganti nama:
   paket `<id>-branding` mengganti identitas base-files (os-release, issue),
   lsb-release, distro-info-data, desktop-base (wallpaper, login, GRUB),
   semua logo Debian, GRUB sistem terpasang dan installer Calamares, dengan
   `dpkg-divert` (tetap aman saat update Debian). Opsional: kunci GPG dan
   paket `<id>-archive-keyring` sendiri. File `debian/control`, `changelog`,
   `copyright`, `rules` bisa diedit langsung di GUI. Tidak butuh repositori.
10. **Package Workshop** – buka paket terpasang (base-files, desktop-base,
    ...), edit file langsung, build ulang, pasang dan *hold*; bisa
    dikembalikan ke versi Debian.
11. **Themes & Icons** – tema GTK, ikon, kursor, font, mode gelap, paket
    tema sekali klik, impor tema, ikon desktop.
12. **Desktop** – juga pilihan layar login (LightDM GTK, Slick, Arctica,
    KDE, SDDM + tema, GDM, LXDM, Ly, greetd), sesi **X11 atau Wayland**, dan
    **compositor** (picom: ringan/bayangan/kaca blur, bawaan desktop, labwc,
    KWin, Wayfire, Sway).
13. **Build & Test** – pilih kompresi (zstd disarankan), opsi pembersihan,
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
* **Log untuk developer** (setiap kali jalan): `/tmp/eduka-customizer/eduka-customizer.log`
  dan `/tmp/eduka-customizer/errors.log` (error + traceback). Menu
  **Settings → Create bug report** membuat arsip untuk dikirim ke developer.
* Screenshot semua halaman: `docs/screenshots/`.
