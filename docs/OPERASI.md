# Panduan hari lomba

## Admin

1. Buat event dan pilih zona waktunya. Buat kategori; jadwal digunakan sementara sebagai gun time.
2. Atur jumlah putaran hanya setelah rute diketahui. Implementasi awal mendukung putaran sepeda melalui titik 3 dan putaran lari melalui titik 4. Titik 2 tidak dipakai sebagai checkpoint putaran tambahan.
3. Impor peserta menggunakan template `.xlsx`. BIB unik per event; EPC yang sama tidak boleh dipakai dua peserta dalam event yang sama. Peserta tanpa EPC tetap dapat dicatat manual, tetapi belum siap untuk RFID.
4. Buat penugasan perangkat dan reader. Beberapa reader di satu garis menggunakan checkpoint yang sama. Titik 2 wajib multi detect.
5. Minta operator tes. Periksa jam server terhadap acuan resmi panitia. Tanggal/waktu resmi panitia harus memakai zona waktu event yang sama.
6. Saat panitia memberikan gun time, isi **Gun time resmi** pada kategori yang tepat. Koreksi ini tidak mengubah catatan asli.
7. Tekan **Hitung Hasil**. Periksa masalah, tetapkan koreksi dengan alasan, atau status DNS/DNF/DSQ sesuai keputusan panitia.
8. Pastikan semua Android selesai mengirim dan konfirmasikan di **Titik & perangkat**. Antrean yang dilaporkan adalah status terakhir; konfirmasi operator tetap diperlukan.
9. Hitung ulang. Tetapkan resmi setelah semua pemeriksaan selesai dan penggunaan RFID untuk catatan manual yang hilang disetujui.
10. Ekspor Excel/PDF. Data baru atau perubahan aturan menandai snapshot hasil sudah usang; hitung ulang sebelum ekspor.

## Operator desktop

- Sambungkan reader, switch, laptop dan daya. Jalankan aplikasi, unduh konfigurasi.
- Buka **Tes Reader**, tekan **Mulai Tes Semua Reader**, lalu lewatkan tag pada masing-masing reader. Periksa tag, sinyal dan jumlah bacaan. Sinyal bukan pengukur jarak yang pasti.
- Tekan **Selesai Tes**, lalu **Mulai Pencatatan**. Tes dan lomba tidak berjalan bersamaan.
- Biarkan aplikasi terbuka. Antrean internet terputus tersimpan di SQLite; jangan menutup laptop atau mematikan reader.
- Jika koneksi reader putus, aplikasi mencoba kembali. Peserta yang lewat ketika reader mati/koneksi terputus belum tentu dapat dipulihkan; gunakan catatan manual untuk periode itu.
- Setelah selesai, pastikan antrean nol. Jika ada penolakan, periksa pesan dengan admin; jangan menghapus database. Setelah masalah diperbaiki, pilih kirim ulang.

## Operator Android

- Buka penugasan yang sudah tersimpan dan periksa jam sebelum mulai.
- Ketik BIB dan tekan tombol sesuai lintasan. Di titik 2 pilih **Mulai Sepeda** atau **Mulai Lari** setiap kali mencatat.
- Jika salah tekan, **Batalkan catatan terakhir**. Pembatalan disimpan lokal dan harus ikut dikirim.
- Tekan **Kirim Data** saat internet tersedia. Satu kiriman maksimal 100 catatan; ulangi sampai antrean habis. Pengiriman ulang tidak menggandakan catatan.
- Untuk putaran, isi nomor putaran yang benar. Sistem tidak menebak putaran manual dari urutan upload.
- Jangan mengubah jam ponsel, menghapus aplikasi, atau membersihkan penyimpanan selama event.

## Aturan pemilihan hasil

1. Keputusan admin dengan alasan, jika ada.
2. Satu catatan manual valid untuk tahap/putaran tersebut.
3. RFID yang dapat ditempatkan secara konsisten pada rute.

Manual ganda tidak otomatis dipilih yang tercepat. Selisih manual/RFID yang jauh ditandai, bukan dirata-ratakan. Catatan sebelum jadwal tetap disimpan dan dapat dipakai ketika gun time dikoreksi; data tes tidak pernah masuk hasil.

Pengelompokan lintasan menggunakan interval minimum dan syarat tag tidak terbaca selama `quiet_ms`. Bukti raw tetap ada. Kandidat dari reader berbeda pada satu checkpoint dalam 2 detik digabung; dukungan manual/RFID dianggap berdekatan sampai 3 detik. Nilai awal ini dicatat dalam rancangan v0.1 dan harus diuji terhadap lebar area baca serta kecepatan peserta; bukan klaim akurasi.

Jam desktop terus berjalan saat internet terputus. Status berubah menjadi holdover setelah 2 menit dan stale setelah 1 jam. Perbedaan besar saat sinkronisasi ditandai `jump`. Estimasi ketidakpastian bukan jaminan akurasi perangkat. Tidak ada jaminan 0,1 detik tanpa pembuktian lapangan.
