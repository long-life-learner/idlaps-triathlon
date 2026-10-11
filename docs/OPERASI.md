# Panduan hari lomba

## Admin

1. Buat event dan pilih zona waktunya. Buat kategori; jadwal digunakan sementara sebagai gun time.
2. Atur jumlah putaran hanya setelah rute diketahui. Implementasi awal mendukung putaran sepeda melalui titik 3 dan putaran lari melalui titik 4. Titik 2 tidak dipakai sebagai checkpoint putaran tambahan.
3. Impor peserta menggunakan template `.xlsx`. BIB 1–3 digit dan unik per event; `007` berbeda dari `7`; Satu BIB boleh memiliki beberapa EPC (pisahkan dengan koma atau baris baru); EPC yang sama tidak boleh dipakai dua peserta dalam event yang sama. Peserta tanpa EPC tetap dapat dicatat manual, tetapi belum siap untuk RFID.
4. Buat penugasan perangkat dan reader. Beberapa reader di satu garis menggunakan checkpoint yang sama. Titik 2 wajib multi detect.
5. Minta operator tes. Periksa jam server terhadap acuan resmi panitia. Tanggal/waktu resmi panitia harus memakai zona waktu event yang sama.
6. Saat panitia memberikan gun time, isi **Gun time resmi** pada kategori yang tepat. Koreksi ini tidak mengubah catatan asli.
7. Tekan **Hitung Hasil**. Daftar peserta bermasalah menjelaskan catatan yang kurang. Pilih **Periksa catatan** untuk koreksi waktu, atau **Atur status peserta** untuk DNS (tidak start), DNF (tidak selesai), DSQ (diskualifikasi). Alasan DSQ wajib diisi; status bisa dikembalikan ke Aktif, dengan riwayat perubahan.
8. Pastikan operator mengirim seluruh catatan kategori yang akan disahkan, termasuk antrean dari penugasan sebelumnya. Konfirmasi ini dilakukan pada kartu kategori di **Hasil lomba**.
9. Hitung ulang. Pilih kategori, isi gun time resmi, selesaikan pemeriksaan, centang dua konfirmasi, lalu **Tetapkan resmi · nama kategori**. Kategori lain yang belum berlomba tidak menghalangi.
10. Ekspor Excel/PDF. Label resmi/sementara mengikuti masing-masing kategori. Data baru atau koreksi hanya membatalkan status resmi kategori terkait. Pilih kategori yang masih valid untuk ekspor jika kategori lain belum dihitung ulang.

## Operator desktop

- Sambungkan reader, switch, laptop dan daya. Jalankan aplikasi, unduh konfigurasi.
- Buka **Tes Reader**, tekan **Mulai Tes Semua Reader**, lalu lewatkan tag pada masing-masing reader. Periksa tag, sinyal dan jumlah bacaan. Sinyal bukan pengukur jarak yang pasti.
- Tekan **Selesai Tes**, lalu **Mulai Pencatatan**. Tes dan lomba tidak berjalan bersamaan.
- Biarkan aplikasi terbuka. Antrean internet terputus tersimpan di SQLite; jangan menutup laptop atau mematikan reader.
- Jika koneksi reader putus, aplikasi mencoba kembali. Peserta yang lewat ketika reader mati/koneksi terputus belum tentu dapat dipulihkan; gunakan catatan manual untuk periode itu.
- Setelah selesai, pastikan antrean nol. Jika ada penolakan, periksa pesan dengan admin; jangan menghapus database. Setelah masalah diperbaiki, pilih kirim ulang.

## Operator Android

- Masukkan kode pemasangan; alamat server sudah tetap. Buka penugasan tersimpan dan periksa jam sebelum mulai.
- Ketik BIB 1–3 digit; keyboard angka disediakan. Cocokkan nama dan kategori yang muncul. Semua kategori dalam event bisa dicatat; tidak perlu ganti kode hanya karena berganti kategori.
- Tekan tombol lintasan. Di titik 2 pilih **Mulai Sepeda** atau **Mulai Lari** setiap kali mencatat. Di titik 3/4 isi nomor putaran 1–100 sesuai rute.
- BIB belum terdaftar boleh **Simpan untuk diperiksa** agar waktu tidak terlewat. Catatan tetap lokal ketika server menolaknya. Minta admin mendaftarkan BIB atau perbaiki salah ketik.
- Buka **Catatan perlu diperiksa**, pilih catatan, lalu perbaiki BIB atau batalkan. Perbaikan BIB tersedia sebelum konfirmasi penerimaan server; sesudah itu gunakan koreksi admin. Waktu dan penugasan asal tidak berubah. Catatan asli tetap tersimpan sebagai riwayat.
- Tekan **Kirim Data · semua penugasan** saat internet tersedia. Batch maksimal 100 berjalan berurutan otomatis. Catatan ditolak tidak menghalangi batch lain; periksa pesan lalu kirim lagi setelah diperbaiki. Pengiriman ulang memakai ID sama sehingga tidak menggandakan data.
- **Ganti titik / event** tetap tersedia walaupun ada antrean. Masukkan kode penugasan baru; catatan lama tetap dikirim dengan akses penugasan lama. Akses lama yang dicabut memerlukan kode baru untuk ID perangkat asal dari admin.
- Jangan mengubah jam ponsel, menghapus aplikasi, atau membersihkan penyimpanan selama event.

## Aturan pemilihan hasil

1. Keputusan admin dengan alasan, jika ada.
2. Satu catatan manual valid untuk tahap/putaran tersebut.
3. RFID yang dapat ditempatkan secara konsisten pada rute.

Manual ganda tidak otomatis dipilih yang tercepat. Selisih manual/RFID yang jauh ditandai, bukan dirata-ratakan. Catatan sebelum jadwal tetap disimpan dan dapat dipakai ketika gun time dikoreksi; data tes tidak pernah masuk hasil.

Pengelompokan lintasan menyatukan seluruh EPC peserta pada reader sebelum menggunakan interval minimum dan syarat tag tidak terbaca selama `quiet_ms`. Bukti raw tetap ada. Kandidat dari reader berbeda pada satu checkpoint dalam 2 detik digabung; dukungan manual/RFID dianggap berdekatan sampai 3 detik. Nilai awal ini dicatat dalam rancangan v0.1 dan harus diuji terhadap lebar area baca serta kecepatan peserta; bukan klaim akurasi.

Jam desktop terus berjalan saat internet terputus. Status berubah menjadi holdover setelah 2 menit dan stale setelah 1 jam. Perbedaan besar saat sinkronisasi ditandai `jump`. Estimasi ketidakpastian bukan jaminan akurasi perangkat. Tidak ada jaminan 0,1 detik tanpa pembuktian lapangan.
