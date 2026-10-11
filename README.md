# IDLAPS Triathlon

Implementasi admin/API PHP native, pencatat RFID Windows (Python/PySide6), dan proyek Android Kodular. Manual menjadi sumber utama; RFID melengkapi checkpoint yang tidak memiliki catatan manual.

## Isi proyek

| Folder | Isi |
| --- | --- |
| `web/` | Admin Bahasa Indonesia, API, skema MySQL/MariaDB, impor XLSX, ekspor XLSX/PDF |
| `desktop/` | Penerima Electron RC4 melalui TCP, SQLite lokal, sinkronisasi dan GUI dua halaman |
| `android/IDLAPSTriathlonTap.aia` | Proyek Kodular yang dapat diimpor dan dibangun menjadi APK |
| `tools/` | Generator AIA, demo, pengujian integrasi dan pembuat paket hosting |
| `docs/` | Panduan pemasangan, operasi dan batas pengujian |

Mulai dari [panduan pemasangan](docs/PEMASANGAN.md) dan [panduan operator](docs/OPERASI.md). Detail API ada di [API.md](docs/API.md).

Hosting yang sudah tersambung ke repository dapat diperbarui dengan pull branch `main`, tanpa mengunduh ZIP lagi. Ikuti [panduan pembaruan melalui GitHub](docs/PEMBARUAN-GITHUB.md).

Pembaruan 2.2 menambahkan status DNS/DNF/DSQ dari hasil, penetapan resmi per kategori, dan antrean Android lintas penugasan. BIB dibatasi 1–3 digit dengan nama/kategori ditampilkan sebelum pencatatan. Server Android tetap `https://triathlon.idlaps.com`. Menu arsip manual lama sudah dihapus. Lihat [panduan pembaruan](docs/PEMBARUAN-2.2.md). File untuk dibuild ulang adalah `dist/IDLAPSTriathlonTap-2.2.aia`.

Paket shared hosting beserta dependensinya ada di `dist/idlaps-shared-hosting.zip`; sumber Windows beserta skrip build ada di `dist/idlaps-desktop-windows-source.zip`. Buat ulang paket setelah perubahan dengan `python tools/package.py`.

Pembaruan web/desktop 2.3 mendukung beberapa EPC per BIB, termasuk impor Excel dan penggabungan hasil. Alamat desktop juga tetap `https://triathlon.idlaps.com`. Lihat [panduan 2.3 dan arti pengaturan reader](docs/PEMBARUAN-2.3.md). Kodular tetap versi 2.2.

## Keputusan utama

- Satu kategori memiliki satu pelepasan dan gun time masing-masing; tanggal lengkap mendukung event beberapa hari.
- Jadwal menjadi gun time sementara. Gun time resmi dapat dimasukkan admin; perhitungan ulang tidak mengubah bukti pembacaan.
- Titik 1: finish swim. Titik 2: start cycle dan start run. Titik 3: lintasan/finish cycle. Titik 4: lintasan/finish run.
- Putaran yang didukung adalah lintasan berulang di titik 3 untuk sepeda dan titik 4 untuk lari. Topologi rute lain harus dipastikan dahulu, bukan ditebak oleh algoritma.
- Data lokal disimpan dahulu. Pengiriman berulang memakai ID unik; respons mengonfirmasi setiap catatan.
- Manual valid diprioritaskan. Manual ganda, waktu mundur, data tidak lengkap atau RFID ambigu masuk pemeriksaan.
- Tes reader tidak ikut hasil. Bukti asli tetap tersimpan setelah koreksi/pembatalan.
- Hasil diurutkan memakai durasi milidetik penuh; layar dan PDF menampilkan detik. XLSX menyimpan durasi numerik lengkap dengan format detik.

## Menjalankan demo lokal

PHP 8.2+, Composer, dan ekstensi PHP yang diminta Composer diperlukan pada komputer pengembangan, bukan terminal hosting.

```sh
cd web
composer install --no-dev
cd ..
php tools/demo.php
IDLAPS_CONFIG="$PWD/web/storage/demo/local.php" php -S 127.0.0.1:8765 -t web/public
```

Buka `http://127.0.0.1:8765`. Kredensial demo dibuat secara acak di `web/storage/demo/login.txt`. Konfigurasi dan data demo diabaikan Git dan tidak masuk paket hosting. Demo hanya untuk localhost.

Desktop untuk pengembangan:

```sh
python -m venv .venv
.venv/bin/pip install -r desktop/requirements.txt
.venv/bin/python desktop/main.py
```

Pada Windows gunakan `.venv\Scripts\python` atau jalankan `desktop/build-windows.bat`. Build `.exe` wajib dilakukan di Windows; workflow GitHub Actions disediakan bila repositori dipasang ke GitHub.

## Pengujian

```sh
php web/tests/run.php
php web/tests/categories.php
php web/tests/multi_epc.php
PYTHONPATH=desktop .venv/bin/python -m unittest discover -s desktop/tests -v
.venv/bin/python tools/test_integration.py
python3 tools/validate_android.py android/IDLAPSTriathlonTap.aia
python3 tools/test_android_runtime.py
```

`web/tests/run.php` secara default membuat database SQLite sementara. `IDLAPS_TEST_CONFIG=/path/test-config.php` menjalankan tes yang sama terhadap **database MySQL kosong khusus tes**. Jangan arahkan ke database produksi.

## Status dan batas

Lihat [VALIDASI.md](docs/VALIDASI.md). Tes perangkat lunak tidak membuktikan akurasi lintasan RFID. Build Windows, impor/build Kodular, dan uji reader fisik harus diselesaikan pada lingkungan target sebelum digunakan untuk hasil resmi.

Referensi: protokol Electron EL-UHF-RC v1.1 dari pengguna dan peninjauan [idlaps-12db](https://github.com/long-life-learner/idlaps-12db) pada commit `a1f0ecb3fff610a1d02370f44d84d19ceb573699`. Proyek `.aia` asli pengguna tidak diubah. Protokol TCP baru ditulis terpisah dengan pengumpulan frame dan pemeriksaan CRC.
