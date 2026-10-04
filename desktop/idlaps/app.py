import ctypes
import json
import os
import queue
import sys
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from PySide6.QtCore import QTimer, Signal, QObject
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QFileDialog)
from .storage import Store
from .clock import RaceClock
from .network import Api
from .reader import ReaderWorker


class Bus(QObject):
    completed = Signal(object)
    failed = Signal(str)
    network = Signal(str)


class Window(QMainWindow):
    def __init__(self, store):
        super().__init__()
        self.store = store
        self.clock = RaceClock()
        self.config = store.get("config")
        self.workers = []
        self.messages = queue.SimpleQueue()
        self.latest = {}
        self.reader_status = {}
        self.reader_totals = {}
        self.stop_network = threading.Event()
        self.bus = Bus()
        self.bus.completed.connect(self.configured)
        self.bus.failed.connect(self.failure)
        self.bus.network.connect(self.network_status)
        self.setWindowTitle("IDLAPS · Pencatatan Triathlon")
        self.resize(1040, 720)
        root = QWidget(); self.setCentralWidget(root); layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24); layout.setSpacing(15)
        title = QLabel("IDLAPS  /  TRIATHLON"); title.setObjectName("brand"); layout.addWidget(title)
        self.assignment = QLabel("Pasangkan komputer dengan event"); self.assignment.setObjectName("title"); layout.addWidget(self.assignment)
        self.connection = QLabel("Konfigurasi belum diunduh"); layout.addWidget(self.connection)
        self.pair_box = QWidget(); pair = QVBoxLayout(self.pair_box)
        self.url = QLineEdit(store.get("url", "")); self.url.setPlaceholderText("https://alamat-admin-anda.com")
        self.code = QLineEdit(); self.code.setPlaceholderText("Kode pemasangan dari admin")
        self.pair_button = QPushButton("Hubungkan & unduh konfigurasi"); self.pair_button.clicked.connect(self.pair)
        pair.addWidget(QLabel("Alamat aplikasi admin")); pair.addWidget(self.url); pair.addWidget(self.code); pair.addWidget(self.pair_button)
        layout.addWidget(self.pair_box)
        self.tabs = QTabWidget(); layout.addWidget(self.tabs)
        race = QWidget(); race_layout = QVBoxLayout(race)
        self.state = QLabel("Siap untuk tes reader"); self.state.setObjectName("state"); race_layout.addWidget(self.state)
        self.counters = QLabel(); race_layout.addWidget(self.counters)
        self.reader_health = QLabel(); self.reader_health.setWordWrap(True); race_layout.addWidget(self.reader_health)
        buttons = QHBoxLayout(); race_layout.addLayout(buttons)
        self.start_btn = QPushButton("Mulai Pencatatan"); self.start_btn.clicked.connect(lambda: self.start(False)); buttons.addWidget(self.start_btn)
        self.stop_btn = QPushButton("Hentikan"); self.stop_btn.clicked.connect(self.stop); buttons.addWidget(self.stop_btn)
        self.download_btn = QPushButton("Unduh konfigurasi"); self.download_btn.clicked.connect(self.download); buttons.addWidget(self.download_btn)
        self.history = QTableWidget(0, 5); self.history.setHorizontalHeaderLabels(["BIB / nama", "Tag", "Reader", "Waktu UTC", "Mode"])
        self.history.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); race_layout.addWidget(self.history)
        self.tabs.addTab(race, "Pencatatan")
        test = QWidget(); test_layout = QVBoxLayout(test)
        test_layout.addWidget(QLabel("Lewatkan tag pada setiap reader. Data tes disimpan terpisah dan tidak masuk hasil lomba."))
        self.test_btn = QPushButton("Mulai Tes Semua Reader"); self.test_btn.clicked.connect(lambda: self.start(True)); test_layout.addWidget(self.test_btn)
        self.test_stop = QPushButton("Selesai Tes"); self.test_stop.clicked.connect(self.stop); test_layout.addWidget(self.test_stop)
        self.readers_table = QTableWidget(0, 5); self.readers_table.setHorizontalHeaderLabels(["Reader / titik", "Koneksi", "Tag terakhir", "Sinyal dBm", "Jumlah bacaan"])
        self.readers_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch); test_layout.addWidget(self.readers_table)
        self.tabs.addTab(test, "Tes Reader")
        self.errors_label = QLabel(); self.errors_label.setWordWrap(True); layout.addWidget(self.errors_label)
        footer = QHBoxLayout(); layout.addLayout(footer)
        self.retry = QPushButton("Kirim ulang catatan yang ditolak"); self.retry.clicked.connect(store.retry_rejected); footer.addWidget(self.retry)
        backup = QPushButton("Simpan salinan data"); backup.clicked.connect(self.backup); footer.addWidget(backup)
        reconnect = QPushButton("Kode pemasangan baru"); reconnect.clicked.connect(lambda: self.pair_box.setVisible(not self.pair_box.isVisible()) if not self.workers else None); footer.addWidget(reconnect)
        self.bus.network.connect(lambda _: self.refresh())
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(500)
        self.refresh_config()
        self.network_thread = threading.Thread(target=self.network_loop, daemon=True); self.network_thread.start()
        if store.get("was_recording", False) and self.config:
            QTimer.singleShot(5000, lambda: self.start(False))

    def background(self, task):
        self.pair_button.setEnabled(False); self.download_btn.setEnabled(False)
        def run():
            try: self.bus.completed.emit(task())
            except Exception as e: self.bus.failed.emit(str(e))
        threading.Thread(target=run, daemon=True).start()

    def pair(self):
        url, code = self.url.text().strip(), self.code.text().strip()
        def task():
            api = Api(url); data = api.call("pair", {"code": code})
            if data["config"]["device"]["kind"] != "rfid":
                raise ValueError("Kode ini untuk Android manual. Buat ulang kode desktop RFID melalui admin.")
            counts = self.store.counts()
            if self.config and (counts.get("pending", 0) or counts.get("rejected", 0)) and int(data["config"]["device"]["id"]) != int(self.config["device"]["id"]):
                raise ValueError("Masih ada antrean pada penugasan lama. Kirim dahulu. Kode baru sudah terpakai; minta admin membuat ulang setelah antrean selesai.")
            self.store.set("url", url); self.store.set("token", data["token"])
            return data["config"]
        self.background(task)

    def download(self):
        if self.workers: return
        self.background(lambda: Api(self.store.get("url"), self.store.get("token")).call("config")["config"])

    def configured(self, config):
        self.config = config; self.store.set("config", config)
        self.pair_button.setEnabled(True); self.download_btn.setEnabled(True)
        self.refresh_config(); self.state.setText("Konfigurasi tersimpan. Jalankan tes reader sebelum lomba.")

    def failure(self, message):
        self.pair_button.setEnabled(True); self.download_btn.setEnabled(not self.workers)
        QMessageBox.warning(self, "Belum berhasil", message)

    def refresh_config(self):
        ready = bool(self.config)
        self.pair_box.setVisible(not ready); self.tabs.setEnabled(ready)
        if ready:
            self.assignment.setText(self.config["event"]["name"] + " · " + self.config["device"]["name"])
            self.reader_status = {int(r["id"]): "Belum diuji" for r in self.config["readers"]}
            self.readers_table.setRowCount(len(self.config["readers"]))
            self.history.setHorizontalHeaderItem(3, QTableWidgetItem("Waktu " + self.config["event"]["timezone"]))
            self.connection.setText("Konfigurasi tersimpan · memeriksa koneksi server…")

    def start(self, test):
        if self.workers or not self.config: return
        if not self.config["readers"]:
            QMessageBox.warning(self, "Belum ada reader", "Admin perlu menambahkan reader, lalu unduh konfigurasi ulang."); return
        self.store.set("was_recording", not test)
        self.latest.clear(); self.reader_totals.clear()
        for reader in self.config["readers"]:
            worker = ReaderWorker(reader, int(self.config["event"]["id"]), int(self.config["device"]["config_version"]), self.store, self.clock,
                                  lambda *args: self.messages.put(args), test=test)
            self.workers.append(worker); worker.start()
        self.start_btn.setEnabled(False); self.test_btn.setEnabled(False); self.download_btn.setEnabled(False)
        self.state.setText("MODE TES · tidak masuk hasil lomba" if test else "PENCATATAN AKTIF · data disimpan lokal terlebih dahulu")
        if sys.platform == "win32": ctypes.windll.kernel32.SetThreadExecutionState(0x80000003)

    def stop(self):
        for worker in self.workers: worker.stop()
        for worker in self.workers: worker.join(timeout=6)
        if any(w.is_alive() for w in self.workers):
            self.state.setText("Menunggu reader berhenti…"); QTimer.singleShot(1000, self.stop); return
        self.workers = []; self.store.set("was_recording", False)
        self.start_btn.setEnabled(True); self.test_btn.setEnabled(True); self.download_btn.setEnabled(True)
        self.state.setText("Pencatatan berhenti · antrean tetap dikirim saat internet tersedia")
        if sys.platform == "win32": ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

    def network_status(self, text): self.connection.setText(text)

    def network_loop(self):
        last_clock = 0; backoff = 2
        while not self.stop_network.is_set():
            token, cfg = self.store.get("token"), self.store.get("config")
            if not token or not cfg:
                self.stop_network.wait(1); continue
            try:
                api = Api(self.store.get("url"), token)
                if time.monotonic() - last_clock > 60:
                    try: api.synchronize(self.clock, self.store)
                    except Exception as e: self.bus.network.emit("Jam belum terverifikasi: " + str(e))
                    last_clock = time.monotonic()
                batch = self.store.pending(int(cfg["event"]["id"]))
                if batch:
                    reply = api.call("upload", {"data": batch})
                    self.store.acknowledge([r["record_id"] for r in batch], reply.get("accepted_ids", []), reply.get("rejected", []))
                counts = self.store.counts(); clock = self.clock.stamp()
                api.call("heartbeat", {"pending_count": counts.get("pending", 0)+counts.get("rejected", 0), "clock_quality": clock["clock_quality"]})
                self.bus.network.emit("Server terhubung · jam " + clock["clock_quality"])
                backoff = 2
            except Exception:
                self.bus.network.emit("Server belum terhubung · data tetap disimpan di komputer")
                backoff = min(backoff * 2, 30)
            self.stop_network.wait(backoff)

    def refresh(self):
        for _ in range(2000):
            try: kind, rid, value = self.messages.get_nowait()
            except queue.Empty: break
            if kind == "status": self.reader_status[rid] = value
            elif kind == "fatal":
                self.reader_status[rid] = value; self.state.setText("PERLU TINDAKAN · " + value)
            else:
                self.latest[(rid, value["epc"])] = value
                self.reader_totals[rid] = self.reader_totals.get(rid, 0) + 1
                if len(self.latest) > 200: del self.latest[next(iter(self.latest))]
        if not self.config: return
        participants = {p["epc"]: p for p in self.config["participants"] if p["epc"]}
        readers = {int(r["id"]): r for r in self.config["readers"]}
        newest = sorted(self.latest.values(), key=lambda x: x["captured_ms"], reverse=True)
        self.history.setRowCount(len(newest))
        for n, record in enumerate(newest):
            p = participants.get(record["epc"], {})
            tz = self.config["event"]["timezone"]
            stamp = datetime.fromtimestamp(record["captured_ms"] / 1000, timezone.utc).astimezone(ZoneInfo(tz)).strftime("%d/%m %H:%M:%S")
            self.history.setHorizontalHeaderItem(3, QTableWidgetItem("Waktu " + tz))
            cells = [str(p.get("bib", "Tag belum terdaftar")) + " " + p.get("name", ""), record["epc"], readers[record["reader_id"]]["name"], stamp, "Tes" if record["test"] else "Lomba"]
            for c, text in enumerate(cells): self.history.setItem(n, c, QTableWidgetItem(str(text)))
        for n, r in enumerate(self.config["readers"]):
            rid = int(r["id"]); recent = next((x for x in newest if x["reader_id"] == rid), {})
            cells = [r["name"] + " · titik " + str(r["checkpoint"]), self.reader_status.get(rid, ""), recent.get("epc", "—"), recent.get("rssi", "—"), self.reader_totals.get(rid, 0)]
            for c, text in enumerate(cells): self.readers_table.setItem(n, c, QTableWidgetItem(str(text)))
        self.reader_health.setText("\n".join(r["name"] + ": " + self.reader_status.get(int(r["id"]), "Belum diuji") for r in self.config["readers"]))
        counts = self.store.counts(); stamp = self.clock.stamp()
        self.counters.setText(f"Tersimpan: {sum(counts.values())}  ·  Menunggu kirim: {counts.get('pending', 0)}  ·  Perlu diperiksa: {counts.get('rejected', 0)}  ·  Jam: {stamp['clock_quality']}")
        self.errors_label.setText("\n".join(f"{r}: {e}" for r, e in self.store.errors()))
        self.retry.setVisible(bool(counts.get("rejected")))

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Simpan salinan catatan", "idlaps-backup.jsonl", "JSON Lines (*.jsonl)")
        if path:
            with self.store.lock, open(path, "w", encoding="utf-8") as out:
                for row in self.store.db.execute("SELECT payload FROM reads ORDER BY rowid"): out.write(row[0] + "\n")
            QMessageBox.information(self, "Salinan tersimpan", "Salinan memuat seluruh catatan. Simpan dengan baik; pengiriman otomatis tetap berjalan.")

    def closeEvent(self, event):
        if self.workers and QMessageBox.question(self, "Hentikan pencatatan?", "Menutup aplikasi akan menghentikan pembacaan reader. Catatan yang tersimpan tetap aman.") != QMessageBox.StandardButton.Yes:
            event.ignore(); return
        self.stop(); self.stop_network.set()
        event.accept()


def main():
    base = Path(os.getenv("LOCALAPPDATA", str(Path.home() / ".local" / "share"))) / "IDLAPS-Triathlon"
    app = QApplication(sys.argv); app.setStyle("Fusion")
    app.setStyleSheet("""QWidget{font-family:Segoe UI;font-size:14px;color:#173942;background:#f5f8f7} QLabel#brand{font-size:18px;font-weight:800;color:#147467} QLabel#title{font-size:26px;font-weight:700} QLabel#state{font-size:18px;font-weight:650;padding:16px;background:#e2f1e8;border-radius:8px} QPushButton{background:#176c65;color:white;padding:12px 16px;border:0;border-radius:6px} QPushButton:disabled{background:#c4d2ce;color:#61716d} QLineEdit{background:white;border:1px solid #cedad7;padding:12px;border-radius:6px} QTableWidget{background:white;border:1px solid #d5e0dd;gridline-color:#e4ebe8} QHeaderView::section{padding:8px;background:#e7efeb;border:0} QTabBar::tab{padding:12px 24px} QTabBar::tab:selected{background:#d4ebde} """)
    window = Window(Store(base / "capture.sqlite3")); window.show()
    return app.exec()
