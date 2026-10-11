# Validasi implementasi

Dijalankan pada 5 Oktober 2026 di macOS, PHP 8.3, Python 3.10.6, PySide6 6.11 dan MySQL 9.6 lokal terisolasi. Tidak ada pengiriman ke API manual produksi atau perubahan database pengguna.

## Lulus

| Pemeriksaan | Hasil |
| --- | --- |
| Logika hasil, unggah, impor/ekspor pada SQLite | 24 pemeriksaan |
| Pemeriksaan yang sama pada MySQL lokal terisolasi | 24 pemeriksaan |
| Desktop: protokol, penyimpanan, jam, TCP, endpoint tetap dan tampilan multi-EPC | 11 tes |
| Integrasi HTTP: pemasangan, login/CSRF, unggah, hasil, ekspor, pembatalan, multi-EPC dan filter bukti | 5 tes |
| Multi-EPC: migrasi, impor, tabrakan tag, hasil, audit dan publikasi pada SQLite/MySQL | 15 pemeriksaan per database |
| Publikasi kategori, status, audit, label ekspor, pembaruan database pada SQLite dan MySQL | 17 pemeriksaan per database |
| Alur blok AIA 2.2 dengan SQLite nyata dan komponen simulasi | 7 tes |
| AIA 2.2: referensi komponen/prosedur dan regresi Screen1 | Lulus pemeriksaan XML dan simulasi handler |
| PHP syntax dan Python syntax | Lulus |
| Composer audit | Tidak ditemukan advisori saat diperiksa |

Pengujian TCP mengirim 300 frame untuk 30 EPC berbeda melalui socket lokal, termasuk frame terpotong dan tergabung. Semua 300 bukti tersimpan dan tetap tersedia setelah SQLite dibuka ulang. Ini menguji jalur software, bukan persentase tag yang berhasil dibaca antena.

Perhitungan database diuji dengan 501 bukti RFID, termasuk pembacaan rapat dan tag sebelum start. Hasil tetap cocok dengan lintasan yang diharapkan. Impor/ekspor memeriksa BIB dengan nol awal, formula Excel, dan PDF yang benar-benar dirender.

Antarmuka admin diperiksa melalui browser lokal: atur DNF, hitung ulang, tetapkan resmi kategori Men Elite sementara Women Open belum lengkap, lalu filter kategori dan buka formulir status. Screenshot ada di `screenshots/admin-results.png`. PDF contoh diperiksa secara visual. Jendela desktop berhasil dirender secara offscreen di macOS.

Simulasi AIA menjalankan graf blok yang benar-benar tersimpan dalam file keluaran terhadap SQLite, dengan hasil kolom angka berupa string dan hasil satu kolom berupa daftar datar. Alur yang diperiksa meliputi migrasi, BIB/nol awal, putaran invalid, pergantian penugasan dengan data ditolak, pembaruan token penugasan asal, kedua tombol titik 2 lintas kategori, serta koreksi yang menunggu pembatalan sebelum upload pengganti. Simulasi bukan kompilasi Kodular atau pengujian APK.

## Belum terverifikasi pada lingkungan target

- Reader Electron fisik, firmware dan antena pengguna; penempatan tag pergelangan kaki basah, interferensi, lebar garis dan 30 peserta bersamaan.
- Build/operasi EXE di Windows; skrip build dan workflow disediakan, tidak ada EXE yang diklaim sudah dibuat di macOS.
- APK Kodular versi 2.2 di ponsel. Pengguna melaporkan error Screen1 versi awal; sumber sudah diperbaiki, tetapi keberhasilan runtime baru belum dikonfirmasi.
- MariaDB 10.6 pada shared hosting pengguna serta pengaturan Apache/LiteSpeed/PHP dan batas sumber dayanya.
- Akurasi absolut jam server. Penyelarasan HTTP menyamakan acuan aplikasi terhadap server, bukan menjamin server mengikuti waktu resmi panitia secara presisi.

## Uji penerimaan sebelum lomba

Gunakan event latihan. Lalui lima tahap dengan beberapa BIB, uji manual+RFID, putaran, kategori beda gun time, kehilangan internet, restart desktop dan kirim ulang. Masukkan gun resmi setelah pencatatan dan cocokkan hasil dengan perhitungan tangan. Periksa semua reader satu per satu di tab Tes Reader. Konfirmasi kasus titik 2 dan jumlah putaran dengan panitia sebelum mengunci rute.

Untuk Kodular gunakan langkah rinci di [PEMBARUAN-2.2.md](PEMBARUAN-2.2.md). Status “hasil resmi” sebaiknya dipakai setelah pengiriman manual selesai dan temuan pemeriksaan terselesaikan.

Pembaruan 2.3 juga diuji dengan 301 bacaan RFID dari tag tambahan, tanpa pembacaan tag utama, termasuk dua reader di finish swim. Hasil rute tetap tunggal dan seluruh bukti mentah tersimpan. Antarmuka peserta multi-EPC diperiksa melalui browser lokal; screenshot `screenshots/participants-multi-epc.png`.
