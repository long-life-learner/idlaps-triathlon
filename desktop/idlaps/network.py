import time
from urllib.parse import urlparse
import requests


SERVER_URL = "https://triathlon.idlaps.com"


class Api:
    def __init__(self, url, token=""):
        url = url.strip().rstrip("/")
        p = urlparse(url)
        if p.scheme != "https" and not (p.scheme == "http" and p.hostname in ("localhost", "127.0.0.1")):
            raise ValueError("Gunakan alamat HTTPS aplikasi admin.")
        if p.query or p.fragment:
            raise ValueError("Alamat server tidak boleh memuat query/fragment.")
        self.url = url if url.endswith("api.php") else url + "/api.php"
        self.token = token

    def call(self, action, body=None):
        method = requests.get if body is None else requests.post
        kwargs = {"params": {"action": action}, "headers": {"Authorization": "Bearer " + self.token}, "timeout": (3, 8)}
        if body is not None:
            kwargs["json"] = body
        r = method(self.url, **kwargs)
        r.raise_for_status()
        value = r.json()
        if not value.get("ok"):
            raise ValueError(value.get("message", "Server belum menerima data"))
        return value

    def synchronize(self, clock, store):
        samples = []
        for _ in range(4):
            start = time.monotonic_ns()
            r = self.call("time")
            end = time.monotonic_ns()
            server_processing = max(0, r["server_ms"] - r["received_ms"])
            network_ms = (end - start) / 1e6 - server_processing
            if 0 <= network_ms <= 2000:
                samples.append((network_ms, r["server_ms"] + network_ms / 2, end))
        if not samples:
            raise ValueError("Penyelarasan jam belum stabil; pencatatan tetap tersedia dengan penanda jam.")
        rtt, utc, anchor = min(samples)
        accepted = clock.discipline(utc, anchor, rtt / 2 + 5)
        store.clock_sample({"server_ms": utc, "monotonic_ns": anchor, "rtt_ms": rtt, "accepted": accepted})
        if not accepted:
            raise ValueError("Perbedaan jam besar. Catatan ditandai untuk diperiksa; hentikan lalu mulai ulang aplikasi setelah memastikan jam server.")
