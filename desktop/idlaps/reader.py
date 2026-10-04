import socket
import threading
import time
import uuid
from .protocol import Parser, command, tag_from_frame


class ReaderWorker(threading.Thread):
    def __init__(self, config, event_id, version, store, clock, emit, test=False):
        super().__init__(daemon=True, name="reader-" + str(config["id"]))
        self.config, self.event_id, self.version = config, event_id, version
        self.store, self.clock, self.emit, self.test = store, clock, emit, test
        self.stop_event = threading.Event()
        self.sock = None
        self.session = uuid.uuid4().hex
        self.parser = Parser()

    def stop(self):
        self.stop_event.set()

    def request(self, code, data=b""):
        self.sock.sendall(command(code, data))
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and not self.stop_event.is_set():
            try:
                raw = self.sock.recv(4096)
            except socket.timeout:
                continue
            if not raw:
                raise ConnectionError("Koneksi reader ditutup")
            for frame in self.parser.feed(raw):
                if frame.command == code:
                    if frame.status != 0:
                        raise ValueError(f"Reader menolak perintah {code:04X}: status {frame.status:02X}")
                    return frame.data
        raise TimeoutError("Reader belum menjawab perintah")

    def configure(self):
        self.request(0x0050)
        settings = bytearray(self.request(0x0072))
        if len(settings) != 25:
            raise ValueError("Format konfigurasi reader tidak sesuai RC4 (25 byte)")
        desired = settings[:]
        desired[2] = 0  # Answer mode, inventory controlled by this recorder.
        desired[3] = 0x20  # Ethernet output.
        desired[15] = int(self.config["power"])
        desired[16] = 1  # EPC
        desired[21] = 0  # No firmware duplicate filter; keep raw evidence.
        desired[24] = 5  # Vendor recommended 50 ms inventory interval.
        if settings != desired:
            self.request(0x0071, bytes(desired))
        self.sock.sendall(command(0x0001, bytes(5)))

    def run(self):
        backoff = 1
        while not self.stop_event.is_set():
            try:
                self.emit("status", self.config["id"], "Menghubungkan…")
                self.sock = socket.create_connection((self.config["host"], int(self.config["port"])), timeout=3)
                self.sock.settimeout(0.5)
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if hasattr(socket, "SIO_KEEPALIVE_VALS"):
                    self.sock.ioctl(socket.SIO_KEEPALIVE_VALS, (1, 10000, 3000))
                self.parser = Parser()
                self.configure()
                backoff = 1
                self.emit("status", self.config["id"], "Tes berjalan" if self.test else "Pencatatan berjalan")
                while not self.stop_event.is_set():
                    try:
                        raw = self.sock.recv(8192)
                    except socket.timeout:
                        continue
                    received = self.clock.stamp()
                    if not raw:
                        raise ConnectionError("Reader terputus")
                    for frame in self.parser.feed(raw):
                        if frame.command == 1 and frame.status == 0x12:
                            self.sock.sendall(command(1, bytes(5)))
                            continue
                        tag = tag_from_frame(frame)
                        if not tag:
                            continue
                        record = dict(tag, **received, record_id=uuid.uuid4().hex, event_id=self.event_id,
                                      reader_id=int(self.config["id"]), checkpoint=int(self.config["checkpoint"]),
                                      config_version=self.version, test=self.test, session_id=self.session,
                                      detect_mode=self.config["detect_mode"], interval_ms=int(self.config["interval_ms"]),
                                      quiet_ms=int(self.config["quiet_ms"]))
                        self.store.append(record)  # Durable storage precedes UI/network.
                        self.emit("tag", self.config["id"], record)
            except (OSError, ValueError, TimeoutError) as e:
                self.emit("status", self.config["id"], f"Terputus: {e}. Mencoba kembali…")
            except Exception as e:
                # A storage failure must not look like successful recording.
                self.emit("fatal", self.config["id"], f"Gagal menyimpan lokal: {e}")
                self.stop_event.set()
            finally:
                if self.sock:
                    try:
                        self.sock.sendall(command(2))
                    except OSError:
                        pass
                    self.sock.close()
                    self.sock = None
            self.stop_event.wait(backoff)
            backoff = min(backoff * 2, 15)
        self.emit("status", self.config["id"], "Berhenti")
