import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QLineEdit
from idlaps.app import Window
from idlaps.storage import Store
from idlaps.network import SERVER_URL


class DesktopConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "capture.db")
        self.cfg = {"event": {"id": 1, "name": "Test", "timezone": "Asia/Jakarta"},
                    "device": {"id": 1, "name": "Swim", "kind": "rfid", "config_version": 1},
                    "participants": [{"bib": "007", "name": "Ayu", "epc": "AA01", "epcs": ["AA01", "0002"]}],
                    "readers": [{"id": 1, "name": "Reader", "checkpoint": 1}]}
        self.store.set("url", "https://old.example.invalid")
        self.store.set("config", self.cfg)
        with patch.object(Window, "network_loop", return_value=None):
            self.window = Window(self.store)
        self.window.timer.stop()
        self.window.background = lambda task: self.window.configured(task())

    def tearDown(self):
        self.window.close()
        self.window.network_thread.join(timeout=2)
        self.store.db.close()
        self.temp.cleanup()

    def test_fixed_server_pair_and_download_without_server_input(self):
        self.assertEqual(self.window.findChildren(QLineEdit), [self.window.code])
        self.window.code.setText("TEST-CODE")
        with patch("idlaps.app.Api") as api:
            api.return_value.call.return_value = {"token": "test-token", "config": self.cfg}
            self.window.pair()
            api.assert_called_with(SERVER_URL)
            api.return_value.call.assert_called_with("pair", {"code": "TEST-CODE"})
            self.window.download()
            api.assert_called_with(SERVER_URL, "test-token")
        self.assertEqual(self.store.get("url"), SERVER_URL)

    def test_both_epcs_display_the_same_participant_and_old_config_works(self):
        for epc in ["AA01", "0002"]:
            self.window.messages.put(("tag", 1, {"epc": epc, "reader_id": 1,
                "captured_ms": 1700000600000, "test": False}))
        self.window.refresh()
        self.assertEqual(self.window.history.rowCount(), 2)
        self.assertEqual([self.window.history.item(i, 0).text() for i in range(2)], ["007 Ayu"] * 2)
        del self.cfg["participants"][0]["epcs"]
        self.window.refresh()
        self.assertEqual(self.window.history.item(0, 0).text(), "007 Ayu")
