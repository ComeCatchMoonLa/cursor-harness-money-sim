"""图形界面和引擎共用一个状态：开局、行动、结算、日志。"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from money_sim.constants import LOG_FIELDS
from money_sim.server import make_server


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.log_path = root / "game.jsonl"
        self.save_path = root / "manual.json"
        self.httpd = make_server("127.0.0.1", 0, self.log_path, self.save_path, seed=3)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def request(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            raw = response.read().decode("utf-8")
            if path == "/":
                return raw
            return json.loads(raw)

    def test_page_has_a_decision_panel(self):
        html = self.request("/")
        self.assertIn("结算本月", html)
        self.assertIn("决策", html)
        self.assertIn("工作", html)
        self.assertIn("副业", html)

    def test_action_then_month_changes_assets_and_writes_log(self):
        opening = self.request("/api/state")
        self.assertEqual(opening["net_worth"], 720_000)
        self.assertEqual(opening["month"], 1)
        self.assertEqual(opening["status"], "playing")
        result = self.request("/api/resolve", {"employment": "full", "slots": ["rest"]})
        self.assertEqual(result["errors"], [])
        state = result["state"]
        self.assertEqual(state["month"], 2)
        self.assertNotEqual(state["cash"], opening["cash"])
        self.assertEqual(state["net_worth"], state["recent"][-1]["net_worth"])
        lines = self.log_path.read_text(encoding="utf-8").strip().splitlines()
        report = json.loads(lines[-1])
        for key in LOG_FIELDS:
            self.assertIn(key, report)
        self.assertEqual(report["type"], "month_end")
        self.assertEqual(report["net_worth"], state["net_worth"])
        self.assertEqual(report["month"], 1)
        self.assertGreater(report["salary"], 0)
        self.assertGreater(report["living"], 0)

    def test_exhausted_full_time_does_not_move_the_month(self):
        self.request("/api/new", {"seed": 3})
        # 先透支到低精力，再拒绝全职。直接改不了服务器状态，就连着高负荷直到接口拒绝。
        state = self.request("/api/state")
        guard = 0
        while state["energy"] >= 14 and state["status"] == "playing" and guard < 8:
            result = self.request("/api/resolve", {"employment": "full", "slots": ["learn_career"]})
            self.assertEqual(result["errors"], [])
            state = result["state"]
            guard += 1
        rejected = self.request("/api/resolve", {"employment": "full", "slots": ["learn_career"]})
        self.assertTrue(rejected["errors"])
        self.assertEqual(rejected["state"]["month"], state["month"])
        self.assertEqual(rejected["state"]["net_worth"], state["net_worth"])

    def test_save_and_load_keep_the_same_numbers(self):
        first = self.request("/api/resolve", {"employment": "part", "slots": ["rest", "learn_invest"]})
        saved = first["state"]["net_worth"]
        month = first["state"]["month"]
        self.request("/api/save", {})
        continued = self.request("/api/resolve", {"employment": "full", "slots": ["rest"]})
        self.assertGreater(len(continued["state"]["recent"]), 1)
        loaded = self.request("/api/load", {})
        self.assertEqual(loaded["state"]["net_worth"], saved)
        self.assertEqual(loaded["state"]["month"], month)
        self.assertEqual(loaded["state"]["recent"], [])


if __name__ == "__main__":
    unittest.main()
