# Pembaruan 2.2

## File yang digunakan

- `dist/idlaps-shared-hosting.zip`: web admin, API dan dependensi PHP.
- `dist/IDLAPSTriathlonTap-2.2.aia`: sumber Kodular, version code 4, untuk dibuild menjadi APK.

## Memperbarui hosting yang sudah berjalan

1. Cadangkan database melalui phpMyAdmin/cPanel dan salin `config/local.php`.
2. Ekstrak paket baru ke folder aplikasi yang sama melalui File Manager. Timpa kode aplikasi dan dependensinya, tetapi pertahankan `config/local.php` serta isi `storage/` milik instalasi. Paket tidak menyertakan kredensial/database demo.
3. Pastikan `triathlon.idlaps.com` mengarah ke folder `public/`, dengan HTTPS aktif. Android selalu memakai `https://triathlon.idlaps.com/api.php`.
4. Buka admin. Pembaruan menambah tabel versi/publikasi kategori otomatis; tidak perlu terminal, import SQL manual, atau menjalankan `install.php` ulang. User database perlu izin membuat tabel.
5. Tekan **Hitung Hasil**. Hasil lama perlu dihitung ulang dan disahkan per kategori; penanda resmi global versi lama tidak otomatis menjadi resmi di versi ini.
6. Fitur **Arsip manual lama** tidak lagi tersedia. Jika menimpa folder lama, hapus file kode `app/legacy.php` yang mungkin tertinggal. Tabel `result_logs` dan endpoint manual lama tidak dihapus atau dipakai untuk impor.

Hasil resmi ditetapkan pada kartu kategori di halaman **Hasil lomba**. Gun time resmi harus diisi; seluruh peserta harus selesai diperiksa atau memiliki status DNS/DNF/DSQ yang tepat. Pastikan seluruh catatan manual kategori itu sudah dikirim, lalu centang konfirmasi dan tetapkan resmi. Upload kategori lain tidak membatalkan hasil resmi kategori ini.

Untuk status peserta, klik **Atur status peserta** pada daftar masalah atau **Atur status · BIB** di tabel. Pilih status, isi alasan (wajib untuk DSQ), simpan, lalu hitung ulang. Pilihan Aktif mengembalikan perhitungan berdasarkan catatan. Riwayat perubahan mencatat status sebelum/sesudah dan alasan.

## Memperbarui Android

1. Impor AIA 2.2 ke Kodular dan build APK. Proyek ini belum dikompilasi/dijalankan pada ponsel dalam pengujian pengembangan.
2. Gunakan paket `com.idlaps.triathlontap` dan keystore yang sama dengan APK triathlon sebelumnya. Pasang sebagai pembaruan; **jangan uninstall atau bersihkan data aplikasi**. Jika Android meminta uninstall karena tanda tangan berbeda, kembali ke keystore lama.
3. Saat pertama dibuka, catatan versi triathlon 2.1 disalin ke antrean per penugasan. Tabel dan isi bukti lama dipertahankan. Migrasi ini bukan impor data aplikasi IDLapsTap asli yang berbeda paket.
4. Operator cukup memasukkan kode pemasangan. Alamat server tidak perlu diisi.
5. Periksa penugasan dan nama peserta, lalu lakukan uji offline/kirim ulang di event latihan.

## BIB dan pergantian penugasan

BIB berisi 1–3 digit. Input kosong, huruf, tanda minus, desimal, dan lebih dari tiga digit ditolak tanpa dipotong diam-diam. Nol awal dipertahankan: `007` dan `7` adalah BIB berbeda. Impor peserta Excel harus memakai format teks untuk BIB dengan nol awal. Bila instalasi lama memiliki BIB nonangka/lebih dari tiga digit, selesaikan pemetaan peserta sebelum memakai pencatatan baru; pembaruan tidak mengubah peserta lama secara otomatis.

Satu penugasan menerima semua kategori dalam event. Nama/kategori ditampilkan berdasarkan BIB dari konfigurasi yang telah diunduh. Gunakan **Periksa jam & konfigurasi** setelah admin mengubah peserta.

**Ganti titik / event** tidak menunggu antrean kosong. Setiap catatan menyimpan identitas penugasan asal. **Kirim Data · semua penugasan** mengirim batch secara berurutan menggunakan akses asalnya, termasuk data penugasan sebelumnya. Jika akses asal dicabut, admin membuat ulang kode untuk **ID perangkat asal yang sama**; pemasangan ulang memperbarui akses antrean itu. Membuat perangkat baru tidak membuka akses catatan perangkat lama.

BIB belum terdaftar boleh **Simpan untuk diperiksa**, dengan waktu saat tombol ditekan. Server belum menerima catatan itu sampai BIB terdaftar. Dari **Catatan perlu diperiksa**, operator dapat membetulkan BIB catatan yang belum dikonfirmasi server atau membatalkannya. Koreksi membuat catatan pengganti dengan waktu yang sama, menyimpan bukti asli, lalu mengirim pembatalan asli sebelum pengganti. Catatan terkirim dikoreksi melalui admin. Halaman pemeriksaan menampilkan maksimal 300 catatan, mendahulukan yang belum terkirim; semua bukti tetap tersimpan di database lokal.

## Uji singkat sebelum dipakai

- Buka aplikasi kosong dan aplikasi hasil update dengan antrean lama; Screen1 harus terbuka tanpa error daftar.
- Coba `007`, `7`, BIB tiga digit, dan tempel `1234`/huruf; cocokkan nama/kategori dan pastikan input tidak valid tidak tercatat.
- Catat BIB salah saat offline, ganti penugasan, catat BIB valid, lalu kirim. Data valid penugasan baru harus terkirim meskipun catatan lama ditolak.
- Perbaiki BIB lama; periksa bahwa waktu tetap sama, penugasan tidak berpindah, dan tidak ada hasil ganda. Coba juga pembatalan serta tutup/buka aplikasi.
- Uji titik 2: tombol mulai sepeda dan mulai lari menghasilkan tahap berbeda untuk BIB yang sama.
- Di admin, tetapkan DNS/DNF/DSQ lalu kembalikan Aktif dan periksa audit. Sahkan kategori A, unggah data kategori B, dan pastikan A tetap resmi pada layar serta ekspor.

Paket belum diunggah ke hosting produksi. Validasi rinci dan batas pengujian ada di `docs/VALIDASI.md` pada sumber proyek.
