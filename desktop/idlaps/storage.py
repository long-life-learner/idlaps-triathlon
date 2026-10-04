import json
import sqlite3
import threading
from pathlib import Path


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS reads(record_id TEXT PRIMARY KEY,event_id INTEGER NOT NULL,
        payload TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'pending',error TEXT);
        CREATE INDEX IF NOT EXISTS reads_pending ON reads(state,event_id);
        CREATE TABLE IF NOT EXISTS clock_samples(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        """)

    def get(self, key, default=None):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.lock, self.db:
            self.db.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                            (key, json.dumps(value)))

    def append(self, record):
        with self.lock, self.db:
            self.db.execute("INSERT INTO reads(record_id,event_id,payload) VALUES(?,?,?)",
                            (record["record_id"], record["event_id"], json.dumps(record, separators=(",", ":"))))

    def pending(self, event_id, limit=250):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute(
                "SELECT payload FROM reads WHERE state='pending' AND event_id=? ORDER BY rowid LIMIT ?", (event_id, limit))]

    def acknowledge(self, sent_ids, accepted, rejected):
        # Only IDs in this exact request can change. Newly captured rows are unaffected.
        sent = set(sent_ids)
        with self.lock, self.db:
            for record_id in set(accepted) & sent:
                self.db.execute("UPDATE reads SET state='sent',error=NULL WHERE record_id=?", (record_id,))
            for item in rejected:
                if item.get("record_id") in sent:
                    self.db.execute("UPDATE reads SET state='rejected',error=? WHERE record_id=?",
                                    (str(item.get("message", "Ditolak server")), item["record_id"]))

    def retry_rejected(self):
        with self.lock, self.db:
            self.db.execute("UPDATE reads SET state='pending',error=NULL WHERE state='rejected'")

    def counts(self):
        with self.lock:
            return dict(self.db.execute("SELECT state,COUNT(*) FROM reads GROUP BY state"))

    def errors(self):
        with self.lock:
            return self.db.execute("SELECT record_id,error FROM reads WHERE state='rejected' LIMIT 10").fetchall()

    def clock_sample(self, sample):
        with self.lock, self.db:
            self.db.execute("INSERT INTO clock_samples(payload) VALUES(?)", (json.dumps(sample),))

    def close(self):
        with self.lock:
            self.db.close()
