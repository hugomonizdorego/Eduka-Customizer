# Panduan singkat Eduka-Customizer 0.15 Alpha

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
sudo apt install ./release/eduka-customizer_0.15.0~alpha_all.deb
```

Atau build sendiri:

```sh
sudo apt install debhelper python3-pytest dpkg-dev
dpkg-buildpackage -us -uc -b
sudo apt install ../eduka-customizer_0.15.0~alpha_all.deb
eduka-customizer doctor        # cek alat yang dibutuhkan
```

## Baru di 0.15

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

## Alur kerja di GUI (12 langkah)

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
8. **Kernel & Boot** – tab *Kernel* dan *Boot Menu* (edit grub.cfg/isolinux).
9. **Look & Feel** – tab *Themes & Icons*, *Wallpaper & Login*, *Plymouth*.
10. **Installer** – Calamares.
11. **Advanced** – tab *Terminal & Live* (desktop image di jendela, terminal
    root, Synaptic) dan *Package Workshop*.
12. **Check & Build** – periksa, build ISO, uji di QEMU (BIOS/UEFI/Secure Boot).

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
