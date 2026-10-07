# Roadmap & rekomendasi

Status: **0.11 Alpha** (Oktober 2026). Daftar ini adalah usulan langkah
berikutnya untuk pengembang Edukasaun OS, diurutkan menurut manfaatnya.

## Selesai di 0.11 Alpha
Quick Wizard, Distro Branding Studio (paket branding + keyring), Package
Workshop, Themes & Icons, pilihan layar login, X11/Wayland, compositor, log
developer di `/tmp`, dukungan instalasi di Ubuntu, screenshot.

## Menuju 0.12 Alpha

1. **Uji penuh dengan ISO Debian 13 live asli** (LXQt dan standard) di
   perangkat keras nyata, BIOS dan UEFI, termasuk Secure Boot. Unit test dan
   uji boot QEMU sudah ada, tetapi ISO 3 GB nyata belum diuji di lingkungan
   pengembangan ini.
2. **Uji Secure Boot pada hardware nyata** dengan GRUB bernama distro
   (EFI/<id> + salinan EFI/debian) dan Calamares.
3. **Repositori APT Edukasaun** (misalnya `repo.edukasaun.org`) yang berisi
   paket `edukasaun-desktop-menu`, tema Plymouth, wallpaper dan
   `edukasaun-keyring`, sehingga update Eduka-Desktop bisa lewat `apt`.
   Eduka-Customizer sudah mendukung penambahan repositori dengan kunci.
4. **Folder `debian/` di Eduka-Desktop** (paket sumber yang benar, dengan
   `dpkg-buildpackage`). Eduka-Customizer sudah mendeteksinya otomatis.
5. **Terjemahan GUI** (Tetun, Português, Bahasa Indonesia, English) memakai
   Qt Linguist (`pylupdate6`/`lrelease`).

## Menuju 0.12 – 0.20

* **Overlay / snapshot rootfs** (overlayfs atau btrfs) sehingga setiap
  perubahan bisa di-*undo*, dan beberapa varian (sekolah, guru, lab) dibuat
  dari satu basis tanpa menyalin seluruh rootfs.
* **Build tanpa root** dengan `unshare`/user namespaces (mmdebstrap
  mendukungnya), lebih aman untuk CI.
* **Terminal tertanam** di GUI (QTermWidget untuk Qt6 bila tersedia di
  Debian) selain terminal eksternal.
* **Repositori APT lokal** yang ditandatangani dengan kunci dari Distro
  Branding (reprepro/aptly), sehingga paket branding bisa di-update online.
* **Pratinjau Plymouth** (`plymouthd --debug` di Xephyr) dan pratinjau menu
  GRUB di dalam aplikasi.
* **Daftar perangkat lunak per profil** (Sekolah Dasar, SMP, SMA, Guru) di
  `desktops.json`/recipe.
* **Profil hardware lama**: kernel `686-pae`, opsi zram, tanpa efek
  grafis – cocok dengan mode *low resource* Eduka-Desktop.
* **Pembaruan ISO inkremental** (hanya membangun ulang squashfs ketika
  rootfs berubah, berdasarkan checksum).
* **Pipeline CI** yang membangun ISO Edukasaun dari recipe pada setiap tag
  dan mengunggahnya sebagai rilis.

## Catatan teknis yang perlu dipantau

* Codename Debian berubah setiap rilis (sekarang: stable `trixie`, testing
  `forky`). Ubah di Settings atau `/etc/eduka-customizer/eduka-customizer.conf`.
* Debian tidak membuat ISO live untuk sid: mulai dari testing lalu ganti
  sumber ke sid, atau bootstrap basis sid.
* Jika Debian berhenti memakai ISOLINUX untuk BIOS, mode *replay* tetap
  bekerja karena menyalin konfigurasi boot dari ISO sumber.
