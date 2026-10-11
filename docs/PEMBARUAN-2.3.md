# Pembaruan web dan desktop 2.3

## Multi-EPC

Satu BIB dapat memiliki beberapa EPC. Buka **Peserta → Ubah**, lalu tulis satu EPC per baris atau pisahkan dengan koma. Contoh: `E200001122334455, E200001122334466`. EPC hanya boleh terhubung ke satu peserta dalam event yang sama. Peserta manual tetap boleh tanpa tag.

Dalam Excel, format kolom tidak berubah: BIB, Nama, Kategori, EPC, Tim. Masukkan semua EPC peserta dalam satu sel EPC, dipisahkan koma; satu baris tetap satu peserta. Impor memeriksa tabrakan dengan seluruh tag peserta lain, termasuk tag tambahan.

Perhitungan menggabungkan tag berdasarkan peserta sebelum menyaring lewat berulang. Dua EPC milik BIB yang sama pada reader yang sama tidak membuat dua lintasan. Bacaan tag tambahan tetap bisa melengkapi seluruh rute walaupun tag pertama tidak terbaca. Bukti mentah setiap tag tetap tersimpan. Perubahan daftar tag dicatat di audit dan membatalkan hasil resmi kategori peserta itu sampai dihitung/diperiksa ulang.

Daftar EPC lama dimigrasikan otomatis ke tabel tambahan `participant_tags`. Kolom EPC pertama dipertahankan untuk kompatibilitas. API konfigurasi menambahkan array `epcs`; desktop baru mengenali semuanya. Setelah perubahan tag, hentikan pencatatan dan **Unduh konfigurasi** di desktop, lalu jalankan tes reader.

## Desktop dengan alamat tetap

Alamat desktop sudah ditetapkan `https://triathlon.idlaps.com`. Kolom alamat dihapus; operator hanya memasukkan kode pemasangan. Pemasangan, unduh konfigurasi, penyelarasan jam, unggah, dan heartbeat memakai alamat tersebut. Kode harus berasal dari admin di alamat itu. Database SQLite lokal tidak dihapus oleh pembaruan.

Paket `dist/idlaps-desktop-windows-source.zip` berisi sumber dan `build-windows.bat`. Build EXE tetap dilakukan di Windows. Pengujian di macOS tidak menggantikan pengujian Windows atau reader fisik. Kodular tetap versi 2.2; tidak ada perubahan APK yang diperlukan untuk dukungan multi-EPC di hasil.

## Memperbarui hosting

Jika hosting sudah tersambung ke GitHub, gunakan [panduan pull dari GitHub](PEMBARUAN-GITHUB.md). Langkah ZIP di bawah adalah alternatif pemasangan manual.

1. Cadangkan database dan `config/local.php`.
2. Timpa kode/dependensi dari `dist/idlaps-shared-hosting.zip`, dengan tetap mempertahankan `config/local.php` dan data `storage/` instalasi.
3. Buka admin; tabel pemetaan tag dan migrasi tag lama dibuat otomatis. Tidak perlu terminal atau menjalankan installer ulang. Akses database harus dapat membuat tabel/index.
4. Uji satu peserta dengan dua tag. Pastikan keduanya menampilkan BIB yang sama di desktop dan hasil tidak berganda. Gunakan event latihan.

Pembaruan sebelumnya dijelaskan di [PEMBARUAN-2.2.md](PEMBARUAN-2.2.md). Paket belum diunggah ke hosting produksi.

## Arti pengaturan reader

| Pengaturan | Fungsi |
| --- | --- |
| Titik tugas | Penugasan perangkat. Menentukan tombol tahap pada Android; pada desktop hanya konteks penugasan, posisi bacaan mengikuti masing-masing reader. |
| Garis pencatatan | Checkpoint fisik reader: 1 finish swim, 2 mulai sepeda/lari, 3 lintasan/finish sepeda, 4 lintasan/finish lari. |
| Single detect | Bacaan pertama setelah gun time per peserta/reader menjadi kandidat lewat. Bacaan mentah berikutnya tetap disimpan. |
| Multi detect | Mengizinkan kandidat lewat berikutnya setelah kedua syarat jeda terpenuhi. Digunakan pada titik 2 dan rute beberapa putaran. |
| Jeda minimum | Durasi minimum sejak lewat terakhir yang diterima. |
| Waktu tidak terbaca | Durasi sejak bacaan terakhir dari semua tag peserta pada reader itu. Menghindari hitungan berulang saat peserta masih berada di area antena. |
| Inventory 50 ms | Pengaturan siklus pemindaian reader, 0,05 detik. Bukan jeda antarpeserta, interval upload, atau jaminan akurasi waktu. |
| Penggabungan reader | Kandidat milik peserta sama dari reader berbeda pada checkpoint sama, berselisih maksimal 2 detik, digabung dengan waktu paling awal. |

Contoh multi detect dengan jeda 10 detik dan waktu tidak terbaca 2.000 ms: lewat diterima 07:00:00, masih terbaca terakhir 07:00:09. Bacaan 07:00:10 belum dihitung sebagai lewat baru karena baru berselang 1 detik sejak bacaan sebelumnya. Tanpa bacaan tambahan sampai 07:00:12, bacaan 07:00:12 dapat menjadi lewat berikutnya. Dua syarat harus terpenuhi; tag yang terus terbaca tetap satu kali lewat.

Dengan multi-EPC, kedua syarat berlaku terhadap peserta pada reader, bukan masing-masing tag secara terpisah. Reader yang berbeda lokasi fisik jangan diberi checkpoint sama hanya untuk menggabungkan data. Bacaan yang tidak cukup untuk menentukan tahap tetap masuk pemeriksaan.
