# Panduan singkat Eduka-Customizer 0.16 Alpha

Eduka-Customizer adalah pembangun ISO untuk **semua distribusi berbasis
Debian**: Debian stable, testing, sid dan turunan Debian seperti **LMDE**
(ISO Ubuntu dan turunannya ditolak). Tidak ada lagi pengaturan bawaan untuk
Edukasaun OS — nama, ID, host name dan homepage kosong sampai Anda mengisinya
(selama kosong, nama dari `os-release` image yang dipakai). **Eduka-Desktop**
tetap tersedia sebagai salah satu desktop. Aplikasinya sendiri bisa dipasang
di Debian, turunan Debian, **Ubuntu dan turunannya**.

## Cara tercepat: Quick Wizard

Buka **Quick Wizard** di sidebar, isi 8 langkah (Sumber → Identitas →
Basis Debian → Desktop → Tampilan → Aplikasi → Branding → Selesai), lalu
tekan **Finish**. Pilih juga *distro untuk apa*, **edisi ISO** dan **edisi
desktop**. Semua jawaban disimpan sebagai recipe `recipe-wizard.json`, ISO
langsung dibangun, dan semua langkah di sidebar terbuka untuk penyesuaian.

## Instalasi

Paket siap pakai untuk dicoba (Debian 13, Ubuntu 24.04 dan turunannya):

```sh
sudo apt install ./release/eduka-customizer_0.16.0~alpha_all.deb
```

Atau build sendiri:

```sh
sudo apt install debhelper python3-pytest dpkg-dev
dpkg-buildpackage -us -uc -b
sudo apt install ../eduka-customizer_0.16.0~alpha_all.deb
eduka-customizer doctor        # cek alat yang dibutuhkan
```

## Baru di 0.16

* **System Sounds** (langkah 10) — suara untuk boot, startup (login), logout, shutdown,
  error, peringatan, informasi, notifikasi, e-mail, perangkat USB, kabel daya, baterai
  lemah, dll. Jatuhkan folder: file bernama `boot.ogg`, `login.wav`, `shutdown.ogg`,
  `error.oga`, `notification.ogg` otomatis dicocokkan. Menjadi tema suara default semua
  desktop; suara boot/shutdown lewat layanan systemd, suara login lewat autostart.
* **Welcome Screen** (langkah 11) — 4 halaman yang Anda desain: judul, teks (**tebal**,
  *miring*, [tautan](https://...)), logo, gambar, warna, dan tombol (buka situs, jalankan
  program, mulai installer, tutup). Muncul setelah login sampai pengguna menghapus centang
  *Show this at startup* (atau hanya live / hanya terpasang / hanya dari menu).
* **Identity & Branding** dimuat langsung dari ISO yang diekstrak (nama, ID, versi,
  codename, URL, hostname, label, logo, wallpaper, latar login & GRUB, warna installer).
* **Edisi** dengan istilah resmi tiap desktop: GNOME Core, KDE Plasma dengan KDE Gear,
  Xfce dengan Goodies, MATE extras, ... plus deskripsi paket Debian dari image.
* **Flatpak** untuk semua jenis distro: seluruh katalog Flathub per kategori (Office,
  Audio & Video, Grafis, Internet, Pendidikan, Sains, Game, Developer, Sistem, Utilitas).
* **Replace apps** — *berlaku untuk semuanya* (semua pengguna, semua desktop).
* **Kernel** — terminal untuk memasukkan repositori pihak ke-3 lalu `apt update`; kernelnya
  muncul di daftar. Jika kernel dipasang, repositori ikut tetap di sistem; jika tidak,
  repositori hanya sementara dan dihapus (paling lambat saat build).
* **Look & Feel** — hanya ikon, tema GTK/Qt, tema jendela dan kursor yang cocok dengan
  desktop/WM yang dipilih.
* **Calamares** — slide berisi teks agar orang bisa membaca saat instalasi; ID Calamares
  mengikuti ISO; pemeriksaan installer yang teliti (branding, modul, unpackfs, bootloader,
  display manager, paket, file system, grup, perintah).
* **GRUB Design** (tab di Kernel & Boot) — tema GRUB pihak ke-3 (dicek; ditolak bila tidak
  kompatibel), desain menu GRUB (judul, urutan, default, timeout, warna), dan bootloader
  sistem terpasang: GRUB, GRUB + Secure Boot, systemd-boot, rEFInd. LILO, BURG, EFISTUB dan
  Syslinux dijelaskan alasannya tidak dipakai.
* Tampilan lebih modern: sidebar gradien, tab pil, *Step N of 14* dengan bar kemajuan.


* **Untuk semua distro berbasis Debian** — default Edukasaun OS dihapus.
  Project lama tetap jalan; file `*-edukasaun*` di image diganti nama otomatis.
* **Build langkah demi langkah** — 12 langkah bernomor. Langkah berikutnya baru
  aktif setelah langkah sebelumnya selesai: tekan **Done — next step** di bawah
  halaman (✔ = selesai). Langkah 1 selesai saat project sudah punya sistem.
  Mode ahli: **Settings → Free navigation** membuka semua menu kapan saja.
* **Menu yang mirip digabung** (tab): *Identity & Branding*; *Software*
  (Packages, Flatpak, Replace apps); *Kernel & Boot*; *Look & Feel* (Themes &
  Icons, Wallpaper & Login, Plymouth); *Advanced* (Terminal & Live, Package
  Workshop).
* **Edisi desktop / WM**: **Mini** (desktop + terminal + file manager, tanpa
  paket rekomendasi), **Compact** (alat inti, jaringan, pengaturan), **Full**
  (desktop lengkap seperti di Debian), **Full with apps** (Full + aplikasi yang
  direkomendasikan: browser, office, mail, media, grafis).
* **Daftar DE, WM dan compositor hanya yang ada di Debian**: GNOME, KDE Plasma,
  Xfce, Cinnamon, MATE, LXQt, LXDE, Budgie, GNOME Flashback, Enlightenment,
  Eduka-Desktop; WM Openbox, i3, Fluxbox, IceWM, awesome, JWM, herbstluftwm,
  bspwm, dwm, spectrwm, Sway, labwc, Wayfire, Hyprland (Debian 13 ke atas).
* **Edisi ISO** di jendela *distro untuk apa?*: **Minimal**, **Full**, **Full
  with recommended apps**.
* **Replace apps** — ganti program bawaan desktop (browser, e-mail, pengolah
  kata, spreadsheet, editor teks, file manager, terminal, penampil gambar,
  pemutar video dan musik, PDF, arsip, kalkulator) dengan program lain. Program
  baru dipasang dan dijadikan default (`/etc/xdg/mimeapps.list` dan
  `update-alternatives`); yang lama bisa dihapus. Desktop tidak ikut terhapus.
* **Check & Build** — pemeriksaan sebelum build: distro, alat build, database
  paket (paket setengah terpasang, `apt-get check`), kernel dan initrd,
  live-boot, sesi desktop dan layar login, installer, identitas, file boot yang
  diedit, mount/`policy-rc.d` tersisa, data pribadi, ruang disk dan perkiraan
  ukuran ISO. Masalah serius menghentikan build; klik dua kali baris untuk
  membuka halaman perbaikannya.

## Alur kerja di GUI (14 langkah)

1. **Start** – buat project (folder kerja), lalu pilih sumber: ISO Debian live
   (disarankan *standard*) atau ISO turunan Debian, *Download Debian* (dicek
   SHA256), *New Debian base* (mmdebstrap), atau *This computer* (snapshot).
   Lalu jawab **distro untuk apa?** (Pendidikan, Server, Profesional, Rumah,
   Lainnya) dan pilih **edisi ISO** — atau tutup untuk membangun sendiri.
2. **Repositories** – stable / testing / sid, repositori sendiri + kuncinya.
3. **Identity & Branding** – tab *Identity* (nama OS, ID, versi, codename,
   URL, nama komputer, label ISO) dan tab *Distro Branding* (paket
   `<id>-branding`, logo, GRUB, Calamares, keyring).
4. **Users** – user live dengan password, tanpa password, atau default Debian;
   akun di dalam image; ubah/hapus password; hapus akun.
5. **Language** – bahasa default, keyboard, zona waktu (default Asia/Dili),
   terjemahan, submenu *Language* di menu boot.
6. **Desktop** – pilih desktop atau WM dan **edisinya** (Mini, Compact, Full,
   Full with apps), layar login, X11/Wayland, compositor, Eduka-Desktop.
7. **Software** – tab *Packages* (semua paket Debian, centang/hapus centang,
   hapus aplikasi bawaan ISO), *Flatpak apps*, *Replace apps*.
8. **Kernel & Boot** – tab *Kernel* (dengan terminal repositori), *Boot Menu* (edit
   grub.cfg/isolinux) dan *GRUB Design* (tema, menu, bootloader).
9. **Look & Feel** – tab *Themes & Icons*, *Wallpaper & Login*, *Plymouth*.
10. **System Sounds** – suara sistem.
11. **Welcome Screen** – layar sambutan 4 halaman.
12. **Installer** – Calamares (slide, pemeriksaan).
13. **Advanced** – tab *Terminal & Live* (desktop image di jendela, terminal
    root, Synaptic) dan *Package Workshop*.
14. **Check & Build** – periksa, build ISO, uji di QEMU (BIOS/UEFI/Secure Boot).

## Baris perintah

```sh
sudo eduka-customizer new ~/mylinux --iso debian-live-13.1.0-amd64-standard.iso
sudo eduka-customizer -p ~/mylinux brand identity name="My Linux" id=mylinux version=1.0
sudo eduka-customizer -p ~/mylinux purpose apply home --edition full_apps
sudo eduka-customizer -p ~/mylinux desktop install xfce --edition compact --dm lightdm
sudo eduka-customizer -p ~/mylinux desktop install eduka            # Eduka-Desktop
sudo eduka-customizer -p ~/mylinux apps replace browser chromium --remove-old
sudo eduka-customizer -p ~/mylinux flatpak install org.kde.gcompris --firstboot
sudo eduka-customizer -p ~/mylinux shell          # terminal di dalam image
sudo eduka-customizer -p ~/mylinux sounds add ~/suara/ && sudo eduka-customizer -p ~/mylinux sounds apply
sudo eduka-customizer -p ~/mylinux welcome apply
sudo eduka-customizer -p ~/mylinux grub-theme add ~/Unduhan/tema-grub.tar.xz --installed
sudo eduka-customizer -p ~/mylinux boot-loader use systemd-boot
sudo eduka-customizer -p ~/mylinux calamares check
sudo eduka-customizer -p ~/mylinux check --deep   # periksa sebelum build
sudo eduka-customizer -p ~/mylinux build
eduka-customizer -p ~/mylinux test --firmware uefi
```

Build yang bisa diulang (reproducible) memakai *recipe* JSON:
`sudo eduka-customizer -p ~/mylinux recipe apply examples/my-distro.json`
(contoh edisi sekolah dengan Eduka-Desktop: `examples/edukasaun-school.json`).

## Tips

* Jika aplikasi crash dan masih ada mount: `sudo eduka-customizer -p PROJECT clean --unmount-only`.
* Saat Debian rilis versi baru, ubah codename di halaman **Settings**.
* Log lengkap: `PROJECT/logs/eduka-customizer.log`.
* **Log untuk developer** (setiap kali jalan): `/tmp/eduka-customizer/eduka-customizer.log`
  dan `/tmp/eduka-customizer/errors.log` (error + traceback). Menu
  **Settings → Create bug report** membuat arsip untuk dikirim ke developer.
* Screenshot semua halaman: `docs/screenshots/`.
