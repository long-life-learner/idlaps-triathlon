# Pemasangan tanpa terminal shared hosting

## Admin dan API

1. Unduh paket `dist/idlaps-shared-hosting.zip`. Paket sudah menyertakan `vendor/`, sehingga hosting tidak perlu menjalankan Composer.
2. Buat database MySQL/MariaDB melalui cPanel dan berikan akses kepada user database untuk database tersebut. Sebaiknya gunakan database khusus aplikasi ini.
3. Ekstrak paket melalui File Manager ke folder seperti `/home/AKUN/idlaps-triathlon`. Atur document root subdomain admin ke folder **`idlaps-triathlon/public`**.
4. Jika document root tidak bisa diubah, paket bisa diletakkan di `public_html/triathlon`, lalu alamat aplikasi adalah `https://domain/triathlon/public`. File `.htaccess` di akar menolak akses ke folder inti dan `public/.htaccess` mengizinkan halaman publik. Pastikan hosting menggunakan Apache/LiteSpeed dan menerapkan aturan tersebut.
5. Salin `config/example.php` menjadi `config/local.php`. Isi DSN, user, password, dan kode pemasangan acak minimal 24 karakter. Biarkan `allow_http_local` bernilai `false`.
6. Aktifkan HTTPS melalui cPanel. PHP minimal 8.2; aktifkan PDO MySQL, mbstring, zip, gd, xml/dom, fileinfo, iconv sesuai pemeriksaan dependensi.
7. Buka `https://ALAMAT-ADMIN/install.php`, masukkan kode pemasangan dan buat admin. Setelah admin pertama ada, halaman pemasangan menolak pemasangan ulang.
8. Masuk melalui `index.php`. Buat event, zona waktu, kategori dan jadwal. Impor peserta melalui template Excel.
9. Tambahkan desktop RFID dan Android manual di **Titik & perangkat**. Kode pemasangan berlaku 24 jam, sekali pakai. Kode baru memutus token lama; lakukan hanya ketika perangkat berhenti atau perlu dipasangkan ulang.
10. Tambahkan setiap reader pada desktop yang tepat. Gunakan IP statis unik di jaringan switch. Port dan pengaturan harus sesuai perangkat fisik.

Tidak ada daemon, WebSocket atau cron yang wajib berjalan di hosting. Desktop melakukan pengiriman berkala; Android memiliki tombol kirim. Perhitungan hasil dilakukan pada permintaan admin.

Paket tidak memuat konfigurasi database, kredensial demo, atau database lokal pengembangan. Setelah pemasangan, uji bahwa URL folder `config/`, `app/` dan `vendor/` tidak dapat dibaca langsung dari internet.

## Desktop Windows

Build dilakukan di Windows dengan Python 3.12 64-bit, menggunakan `desktop/build-windows.bat`. Hasilnya `desktop/dist/IDLAPS-Triathlon.exe`. Workflow `.github/workflows/windows.yml` juga menghasilkan artefak EXE jika dijalankan di GitHub Actions.

Operator akhir tidak perlu Python setelah EXE tersedia. Jalankan EXE, masukkan alamat admin (tanpa `/index.php`, tanpa slash akhir) dan kode desktop RFID. SQLite disimpan di `%LOCALAPPDATA%\IDLAPS-Triathlon\capture.sqlite3`.

Reader tersambung melalui LAN/switch. Internet dapat melalui jaringan yang sama atau koneksi lain, asalkan subnet LAN dan rute internet benar. Reader yang masih memiliki IP pabrik sama harus diberi IP unik satu per satu sebelum dipasang bersamaan. Penetapan alamat jaringan fisik tidak dilakukan otomatis oleh aplikasi.

Unduh ulang konfigurasi saat pencatatan berhenti. Aplikasi tidak menerapkan perubahan reader diam-diam di tengah sesi. Pada Windows aplikasi meminta sistem tetap aktif saat tes/pencatatan; penutupan tutup laptop dan kehilangan daya tetap harus dicegah secara operasional.

## Android Kodular

1. Impor `android/IDLAPSTriathlonTap.aia` sebagai proyek baru di Kodular.
2. Nama paket baru `com.idlaps.triathlontap` menjaga aplikasi lama tetap terpisah. Data lokal aplikasi lama tidak otomatis dimigrasikan; kirim/arsipkan terlebih dahulu melalui aplikasi lama.
3. Periksa Designer dan Blocks, lalu build APK dari Kodular. Generator dan pemeriksaan XML tidak menggantikan kompilasi Kodular atau pengujian Android.
4. Pasang APK pada Android yang mendukung versi Kodular saat build (proyek menetapkan minimum Android 6).
5. Masukkan alamat admin tanpa slash akhir dan kode untuk **Android manual**, bukan desktop.
6. Di titik 2 muncul tombol **Mulai Sepeda** dan **Mulai Lari**. Di titik 3/4 operator memasukkan nomor putaran jika rute memang memiliki beberapa putaran.
7. Uji pencatatan offline, kirim berulang, pembatalan dan penutupan aplikasi. Data yang belum terkirim tidak boleh hilang.

Ponsel dapat memakai kode baru setelah seluruh catatan dan pembatalan terkirim. Jika token dicabut saat masih ada antrean, pasangkan kembali ke ID perangkat yang sama dengan kode baru. Jangan hapus data aplikasi untuk menyelesaikan masalah kirim.

### Penyelarasan Android

Versi Kodular memakai beberapa sampel HTTP dan koreksi terhadap jam ponsel. Ini belum memakai extension penghitung monotonic Android. Jam ponsel yang berubah ketika offline dapat memengaruhi catatan; nilai waktu asli, koreksi, dan usia sinkronisasi ikut dikirim untuk pemeriksaan. Jangan mengganti jam/zona waktu ponsel saat lomba. Catatan tanpa penyelarasan baru ditandai belum terverifikasi/stale. Desktop menggunakan penghitung monotonic.

## Sistem manual lama

`insert.php` lama tidak diubah atau diganti oleh paket ini. Admin menyediakan **Arsip manual lama** untuk mengambil `result_logs` secara eksplisit. Jika tabel ada di database lain, isi blok `legacy` pada `config/local.php` dengan akses database yang dapat dibaca dari hosting tersebut.

Pilih event, tanggal sebenarnya, checkpoint, rentang ID, arti pecahan detik, jenis lintasan titik 2, dan putaran. Periksa pratinjau sebelum impor. ID impor stabil dalam event agar pengulangan tidak menggandakan catatan. Jam arsip ditandai belum terverifikasi; tinjau melalui koreksi admin sebelum hasil resmi. Tidak ada penebakan tanggal dari waktu upload. Jika baris lama pernah terpotong di `varchar(11)`, digit yang hilang tidak dapat direkonstruksi.

## Pembaruan dan cadangan

Cadangkan database melalui phpMyAdmin/cPanel sebelum pembaruan. Paket pertama memasang tabel baru; aplikasi tidak menghapus `result_logs`. Buat cadangan file SQLite desktop dan data Android sebelum mengganti perangkat. Ekspor JSONL desktop menyimpan bukti pembacaan tanpa token konfigurasi.
