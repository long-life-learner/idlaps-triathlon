# Memperbarui dari GitHub

Repository: `long-life-learner/idlaps-triathlon`, branch `main`.

## Hosting yang sudah terhubung

1. Cadangkan database melalui phpMyAdmin/cPanel sebelum pembaruan skema.
2. Gunakan fitur pull/update repository pada panel hosting untuk mengambil branch `main`. Jika panel memisahkan langkah pull dan deploy, jalankan keduanya sesuai pengaturan hosting Anda. Aplikasi yang dilayani harus menggunakan folder `web/public` dari kode terbaru.
3. Pertahankan `web/config/local.php`, data di `web/storage/`, dan `web/vendor/` yang sudah terpasang. File lokal tersebut diabaikan Git. Pembaruan ini tidak mengubah `composer.json` atau `composer.lock`, sehingga dependensi hosting yang sebelumnya lengkap dapat tetap digunakan.
4. Buka admin. Tabel pendukung hasil per kategori dan multi-EPC dibuat otomatis; user database perlu izin membuat tabel/index. Jangan menjalankan `install.php` ulang.
5. Periksa **Peserta → Ubah**: kolom EPC dapat menerima beberapa tag. Tekan **Hitung Hasil** dan periksa hasil sebelum menetapkan resmi kembali per kategori. Penanda resmi global versi awal tidak otomatis menjadi resmi pada versi ini.

Untuk instalasi pertama, dependensi `web/vendor/` tetap perlu disediakan sesuai [panduan pemasangan](PEMASANGAN.md). Git pull saja tidak mengunduh dependensi Composer.

## Desktop dan Android

Pull di hosting memperbarui website/API. Aplikasi yang terpasang di laptop/HP perlu diperbarui tersendiri:

- Desktop: push memicu workflow **Windows desktop** di GitHub Actions. Setelah berhasil, unduh artifact `IDLAPS-Triathlon-Windows`, ekstrak, lalu gunakan EXE terbaru. Alternatif: build dengan `desktop/build-windows.bat` di Windows. Alamat server desktop tetap `https://triathlon.idlaps.com`; unduh ulang konfigurasi setelah memperbarui daftar EPC.
- Android: sumber terbaru ada di `android/IDLAPSTriathlonTap.aia` (versi 2.2). Build melalui Kodular memakai keystore yang sama dan pasang sebagai pembaruan tanpa uninstall. Dukungan multi-EPC 2.3 sendiri tidak membutuhkan perubahan pada APK manual 2.2.

Paket ZIP di `dist/` merupakan keluaran lokal opsional dan tidak masuk Git. Untuk perubahan berikutnya, kode diuji dan di-commit/push dari proyek ini, kemudian diambil hosting melalui GitHub.

Detail perubahan: [versi 2.2](PEMBARUAN-2.2.md) dan [versi 2.3](PEMBARUAN-2.3.md).
