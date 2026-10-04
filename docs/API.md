# API v1

Base: `https://ALAMAT-ADMIN/api.php?action=...`. HTTPS wajib di produksi. JSON UTF-8. Header autentikasi `Authorization: Bearer TOKEN`; Kodular juga dapat mengirim `token` di objek JSON POST. Token tidak dimasukkan ke URL.

| Aksi | Metode | Isi |
| --- | --- | --- |
| `pair` | POST | `{"code":"KODE_SEKALI_PAKAI"}`; mengembalikan `token`, `config` |
| `time` | GET | `received_ms`, `server_ms` UTC epoch millisecond; respons tidak di-cache |
| `config` | GET | Event, perangkat, kategori, peserta dan reader; autentikasi wajib |
| `upload` | POST | `{"data":[...catatan...]}`; maksimal 500 catatan / 2 MB |
| `cancel` | POST | `{"record_ids":["..."]}`; Android manual, maksimal 100 |
| `heartbeat` | POST | `pending_count`, `clock_quality` |

Contoh catatan manual:

```json
{
  "record_id": "manual-21-000123",
  "event_id": 5,
  "bib": "007",
  "checkpoint": 2,
  "stage": "run_start",
  "lap": 1,
  "captured_ms": 1791075600123,
  "clock_quality": "synced",
  "config_version": 1
}
```

Tahapan manual: `swim_finish` (CP1), `cycle_start` atau `run_start` (CP2), `cycle` (CP3), `run` (CP4). Untuk `cycle` dan `run`, server memetakan nomor `lap` menjadi lintasan antara atau finish sesuai kategori. Nilai eksplisit `cycle_lap`, `cycle_finish`, `run_lap`, `run_finish` juga divalidasi terhadap rute.

Catatan RFID memakai `epc`, `reader_id`, `checkpoint`, `captured_ms`, `config_version`, `clock_quality`, `test`; juga menyimpan `rssi`, `antenna`, `channel`, `session_id`, `monotonic_ns`, `uncertainty_ms`, `detect_mode`, `interval_ms`, `quiet_ms`. BIB RFID ditentukan dari pemetaan EPC saat perhitungan, sehingga tag yang awalnya belum terdaftar tetap tersimpan.

Respons upload dan pembatalan:

```json
{
  "ok": true,
  "accepted_ids": ["manual-21-000123"],
  "rejected": [{"record_id":"manual-21-000124","message":"BIB belum terdaftar dalam event."}]
}
```

`ok=true` tidak berarti seluruh batch berhasil. Tandai hanya ID yang ada di `accepted_ids` dari batch yang dikirim. Simpan ID dan isi catatan yang sama pada setiap retry. ID yang sama dengan isi berbeda ditolak, bukan menimpa bukti.

Pembatalan memiliki ledger tersendiri. Jika pembatalan datang sebelum catatan aslinya, catatan yang menyusul akan ditandai dibatalkan. Perangkat tidak dapat membatalkan catatan milik perangkat lain. Koreksi admin terpisah dari perubahan bukti.

`clock_quality`: `synced`, `holdover`, `unverified`, `stale`, atau `jump`. Catatan tidak ditolak hanya karena jam belum terverifikasi, tetapi hasil memerlukan pemeriksaan. Waktu upload tidak pernah menggantikan waktu pembacaan.

Timestamp harus berupa integer epoch ms, bukan string jam. Batas pemeriksaan penerimaan awal: tahun 2000 sampai 24 jam setelah waktu server. Event lama tetap dapat dikirim dengan tanggal lengkap. Pengubahan body saat retry, termasuk status jam baru untuk catatan lama, tidak diperbolehkan.
