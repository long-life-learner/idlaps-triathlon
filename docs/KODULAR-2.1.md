> Catatan historis versi 2.1. Untuk pembaruan saat ini gunakan [PEMBARUAN-2.2.md](PEMBARUAN-2.2.md).

# Pembaruan Kodular 2.1

## Perbaikan Screen1

Pesan `bad arguments to select list item … ["0"], [1]` cocok dengan jalur pengecekan antrean yang mengasumsikan hasil hitungan SQLite berbentuk daftar bertingkat. Versi 2.1 tidak mengindeks hasil hitungan tersebut: query mengambil ID catatan tertunda dan handler memakai parameter `numberOfRecords` dari `AfterQuery`.

Antrean diperiksa lagi saat kembali dari Screen2. Tombol pemasangan dan lanjut baru aktif setelah penyimpanan siap. Query pembatalan di Screen2 kini mengambil dua kolom supaya menggunakan bentuk baris yang sama dengan query riwayat/pengiriman.

Referensi kontrak event: [SQLite Kodular](https://docs.kodular.io/components/storage/sqlite/). Pemeriksaan regresi menjalankan handler XML yang dihasilkan dengan antrean kosong, satu baris, hasil datar, dan hasil bertingkat. Pemeriksaan ini tidak menjalankan runtime Android.

## Tampilan

- Latar abu hijau, panel putih, margin kiri/kanan dan jarak antarbagian.
- Judul event dan penugasan langsung terlihat.
- BIB besar, tombol pencatatan setinggi 64 dp.
- Di titik 2, Mulai Sepeda berwarna hijau dan Mulai Lari biru; keduanya tetap memiliki label eksplisit.
- Penyimpanan/kirim berada di bagian sendiri. Pembatalan dibedakan dari tombol pencatatan.
- Putaran dan labelnya hanya terlihat pada titik 3/4.
- Semua memakai komponen native Kodular, tanpa WebViewer atau extension tambahan.

## Memasang pembaruan

Impor `dist/IDLAPSTriathlonTap-2.1.aia` dan build APK di akun Kodular yang menggunakan keystore sebelumnya. Nama paket tetap `com.idlaps.triathlontap`, version code menjadi 3. Pasang APK sebagai pembaruan aplikasi triathlon yang telah dicoba; jangan uninstall/hapus data bila masih ada antrean.

Aplikasi manual lama dengan paket `com.idlaps.tap` tetap terpisah.

## Uji di ponsel

1. Buka Screen1 dengan penyimpanan kosong; tidak boleh ada error daftar.
2. Pasangkan perangkat manual lalu simpan BIB yang terdaftar saat offline.
3. Kembali ke Screen1; jumlah antrean harus bertambah. Buka lagi Screen2 dan periksa riwayat.
4. Kirim data, kirim lagi, lalu periksa admin: satu catatan tetap satu catatan.
5. Batalkan catatan sebelum/sesudah dikirim, lalu kirim pembatalan. Catatan asli tetap ada dalam riwayat.
6. Coba penugasan titik 2: satu BIB dicatat sebagai Mulai Sepeda dan kemudian Mulai Lari.
7. Periksa ukuran teks, posisi keyboard, dan tombol pada ponsel operator sebenarnya. Rendering HTML/Designer tidak membuktikan tata letak APK.
