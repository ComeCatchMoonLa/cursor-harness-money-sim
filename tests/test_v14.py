"""V14：同一种子并排走到已结算的月份。打平不挑，也不替玩家选。"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from money_sim.match import STAKES, closer_name, collapse_routes, replay_employment
from money_sim.policies import policy_steady, policy_yolo
from money_sim.server import make_server


class MatchRuleTests(unittest.TestCase):
    def test_stakes_name_the_bet_and_stay_unique(self):
        self.assertEqual(len(STAKES), len(set(STAKES.values())))
        for text in STAKES.values():
            self.assertIn("赌", text)
            self.assertIn("怕", text)
            self.assertNotIn("多数月份", text)
        routes = json.loads(Path("web/routes.json").read_text(encoding="utf-8"))["routes"]
        self.assertEqual([route["stake"] for route in routes], [STAKES[route["name"]] for route in routes])
        self.assertEqual(collapse_routes(routes), routes)
        doubled = collapse_routes([routes[0], {**routes[1], "stake": routes[0]["stake"]}])
        self.assertEqual([route["name"] for route in doubled], [routes[0]["name"]])

    def test_a_tie_picks_nobody_and_a_unique_match_names_that_route(self):
        self.assertIsNone(closer_name(["full"], {"steady": ["full"], "coast": ["full"]}))
        self.assertIsNone(closer_name([], {"steady": ["full"]}))
        self.assertEqual(closer_name(["free"], {"steady": ["full"], "yolo": ["free"]}), "yolo")

    def test_replay_stops_at_the_settled_month(self):
        one = replay_employment(policy_steady, 1, 1)
        two = replay_employment(policy_yolo, 1, 1)
        self.assertEqual(len(one), 1)
        self.assertEqual(one, ["full"])
        self.assertEqual(two, ["free"])
        self.assertEqual(len(replay_employment(policy_steady, 1, 0)), 0)


class MatchApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.httpd = make_server("127.0.0.1", 0, root / "game.jsonl", root / "manual.json", seed=3)
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
            return json.loads(response.read().decode("utf-8"))

    def test_before_any_month_the_table_is_empty_and_nobody_is_closer(self):
        report = self.request("/api/match?left=steady&right=coast")
        self.assertEqual(report["months"], [])
        self.assertIsNone(report["closer"])

    def test_one_settled_month_does_not_walk_into_the_next(self):
        self.request("/api/resolve", {"employment": "free", "slots": ["rest", "rest", "rest", "rest"]})
        report = self.request("/api/match?left=steady&right=yolo")
        self.assertEqual(len(report["months"]), 1)
        self.assertEqual(report["months"][0]["player"], "free")
        self.assertEqual(report["months"][0]["month"], 1)
        self.assertEqual(report["closer"], "yolo")

    def test_the_same_route_on_both_sides_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/api/match?left=steady&right=steady")
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
