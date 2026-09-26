"""V16：中途存档向前打分。标准五条和 routes.json 不动。"""

from __future__ import annotations

import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from money_sim.constants import (
    LOCK_TERM,
    START_AUTONOMY,
    START_CAREER_FRESH,
    START_ENERGY,
    START_LIFESTYLE,
)
from money_sim.economy import mortgage_payment
from money_sim.policies import policy_steady
from money_sim.routes import AUTONOMY_GAP, FAIL_GAP, INTENSITY_GAP, MONTH_GAP, WIN_GAP
from money_sim.server import make_server
from money_sim.snapshot import (
    SNAPSHOT_GAMES,
    SNAPSHOT_SEED,
    _at_least,
    assemble,
    build_snapshot,
    covers,
    describe_forward,
    glide_bounds,
    play_forward,
    score_snapshot,
)


def example_form(**overrides):
    form = {
        "month": 40,
        "cash": 200_000,
        "portfolio": 400_000,
        "locked": 0,
        "debt": 0,
        "home_value": 0,
        "mortgage": 0,
        "career": 40,
        "venture": 10,
        "invest": 20,
        "condition": 70,
        "contract_left": 0,
        "price_index": 1000,
    }
    form.update(overrides)
    return form


def row(name, win, month, fail, intensity, autonomy, **extra):
    data = {
        "name": name,
        "games": SNAPSHOT_GAMES,
        "win_rate": win,
        "median_win_month": month,
        "hard_fail_rate": fail,
        "mean_intensity": intensity,
        "glide_intensity": intensity,
        "mean_autonomy": autonomy,
        "glide_autonomy": autonomy,
        "mainline": {
            "early": {"employment": "full", "share": 0.9, "second": {"employment": "free", "share": 0.08}},
            "mid": {"employment": "full", "share": 0.8, "second": {"employment": "free", "share": 0.1}},
            "late": {"employment": "light", "share": 1.0, "second": None},
        },
    }
    data.update(extra)
    return data


def board(**overrides):
    base = {
        "steady": row("steady", 0.20, 80, 0.10, 0.90, 50),
        "grind": row("grind", 0.20, 80, 0.10, 0.90, 50),
        "yolo": row("yolo", 0.20, 80, 0.10, 0.90, 50),
        "owner": row("owner", 0.20, 80, 0.10, 0.90, 50),
        "coast": row("coast", 0.20, 80, 0.10, 0.90, 50),
        "nest": row("nest", 0.20, 80, 0.10, 0.90, 50),
        "ease": row("ease", 0.20, 80, 0.10, 0.90, 50),
    }
    base.update(overrides)
    return base


def names(report):
    return [item["name"] for item in report["routes"]]


class SnapshotRuleTests(unittest.TestCase):
    def test_windows_stay_on_the_old_band_until_the_snapshot_is_late(self):
        self.assertEqual(glide_bounds(13), (37, 72))
        self.assertEqual(glide_bounds(72), (37, 72))
        self.assertEqual(glide_bounds(73), (73, 108))
        self.assertEqual(glide_bounds(80), (80, 108))
        batch = Path("money_sim/batch.py").read_text(encoding="utf-8")
        self.assertIn("elif month <= 72:", batch)

    def test_unlisted_fields_use_opening_defaults(self):
        state = build_snapshot(
            example_form(locked=50_000, portfolio=200_000, home_value=800_000, mortgage=500_000, contract_left=6)
        )
        self.assertEqual(state.regime, "chop")
        self.assertEqual(state.business_stage, "none")
        self.assertEqual(state.business_book, 0)
        self.assertEqual(state.energy, START_ENERGY)
        self.assertEqual(state.autonomy, START_AUTONOMY)
        self.assertEqual(state.lifestyle, START_LIFESTYLE)
        self.assertEqual(state.career_fresh, START_CAREER_FRESH)
        self.assertEqual(state.lock_left, LOCK_TERM)
        self.assertEqual(state.mortgage_payment, mortgage_payment(500_000))
        self.assertEqual(state.condition, 70)
        self.assertEqual(state.career, 40)
        self.assertEqual(state.price_index, 1000)
        self.assertEqual(build_snapshot(example_form()).lock_left, 0)

    def test_rejects_a_snapshot_the_form_cannot_mean(self):
        with self.assertRaises(ValueError):
            build_snapshot(example_form(locked=10, portfolio=0))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(mortgage=1))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(month=109))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(career=101))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(contract_left=13))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(price_index=0))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(cash=1.5))
        with self.assertRaises(ValueError):
            build_snapshot(example_form(cash=True))

    def test_month_108_is_not_scored(self):
        with patch("money_sim.snapshot.play_forward") as played:
            report = score_snapshot(example_form(month=108))
        played.assert_not_called()
        self.assertFalse(report["scored"])
        self.assertEqual(report["routes"], [])
        self.assertIn("没有剩下的月份", report["message"])

    def test_cover_needs_all_five_axes_and_ignores_mean_net(self):
        better = row("coast", 0.20 + WIN_GAP, 80 - MONTH_GAP, 0.10 - FAIL_GAP, 0.90 - INTENSITY_GAP, 50 + AUTONOMY_GAP)
        worse = row("grind", 0.20, 80, 0.10, 0.90, 50, mean_net=9_000_000)
        better["mean_net"] = 1
        self.assertTrue(covers(better, worse))
        short = dict(better)
        short["glide_autonomy"] = 50 + AUTONOMY_GAP - 1
        short["mean_autonomy"] = short["glide_autonomy"]
        self.assertFalse(covers(short, worse))
        no_month = dict(worse)
        no_month["median_win_month"] = None
        self.assertFalse(covers(better, no_month))
        same = row("steady", 0.20, 80, 0.10, 0.90, 50, mean_net=1)
        rich = row("grind", 0.20, 80, 0.10, 0.90, 50, mean_net=9_000_000)
        self.assertFalse(covers(rich, same))
        self.assertTrue(_at_least(0.20 + WIN_GAP - 0.20, WIN_GAP))
        self.assertFalse(_at_least(0.049, WIN_GAP))
        self.assertFalse(_at_least(0.04989686, WIN_GAP))
        self.assertNotIn("dominates", Path("money_sim/snapshot.py").read_text(encoding="utf-8"))

    def test_shortlist_keeps_order_and_does_not_promote_a_covered_parent(self):
        rows = board(
            yolo=row("yolo", 0.99, 100, 0.50, 1.0, 30),
        )
        report = assemble(rows, 40, (37, 72), SNAPSHOT_GAMES, SNAPSHOT_SEED)
        self.assertEqual(names(report), ["steady", "grind", "yolo", "owner", "coast"])
        self.assertEqual([item["name"] for item in report["routes"][0]["variants"]], ["nest", "ease"])
        self.assertNotIn("best", report)

        buried = board(
            ease=row("ease", 0.10, 90, 0.20, 1.0, 40),
        )
        report = assemble(buried, 40, (37, 72), SNAPSHOT_GAMES, SNAPSHOT_SEED)
        self.assertEqual(names(report), ["steady", "grind", "yolo", "owner", "coast"])
        self.assertEqual([item["name"] for item in report["routes"][0]["variants"]], ["nest"])
        self.assertIn("不挂在一直上班下面", "".join(report["notes"]))
        self.assertEqual(report["omitted"], [{"name": "ease", "by": "steady"}])

        nest = row("nest", 0.90, 40, 0.0, 0.2, 80)
        dominated = board(nest=nest)
        for name in ("steady", "grind", "yolo", "owner", "coast", "ease"):
            dominated[name] = row(name, 0.20, 80, 0.10, 0.90, 50)
        dominated["nest"] = nest
        report = assemble(dominated, 40, (37, 72), SNAPSHOT_GAMES, SNAPSHOT_SEED)
        self.assertEqual(report["routes"], [])
        self.assertNotIn("nest", names(report))
        self.assertIn("不另升上来", "".join(report["notes"]))

    def test_forward_wording_starts_at_the_snapshot_month(self):
        summary = row("steady", 0.2, 80, 0.1, 0.9, 50)
        early = describe_forward(summary, 13)
        self.assertIn("第 13 到 36 月", early)
        self.assertIn("第 37 到 72 月", early)
        self.assertIn("73 月以后", early)
        self.assertNotIn("前 36 个月", early)
        self.assertIn("8%", early)
        quiet = row("steady", 0.2, 80, 0.1, 0.9, 50)
        quiet["mainline"]["early"]["second"]["share"] = 0.079
        self.assertNotIn("前 36 个月还有 8%", describe_forward(quiet, 13))
        self.assertNotIn("8%", describe_forward(quiet, 13).split("37")[0])
        mid = describe_forward(summary, 40)
        self.assertIn("第 40 到 72 月", mid)
        self.assertNotIn("前 36 个月", mid)
        self.assertNotIn("第 13", mid)
        late = describe_forward(summary, 80)
        self.assertIn("第 80 月以后", late)
        self.assertNotIn("前 36 个月", late)
        self.assertNotIn("37 到 72", late)

    def test_the_button_uses_the_locked_count_not_the_form(self):
        seen = []

        def fake(policy, state, seed, window):
            seen.append((seed, window, state.regime, state.business_stage))
            return {
                "status": "shortfall",
                "net_worth": 1,
                "win_month": None,
                "mean_autonomy": 40.0,
                "mean_intensity": 1.0,
                "glide_autonomy": 40.0,
                "glide_intensity": 1.0,
                "glide_months": 1,
                "phase_employ": {"early": {}, "mid": {"full": 1}, "late": {}},
            }

        form = example_form()
        form["games"] = 1
        form["seed"] = 1
        with patch("money_sim.snapshot.play_forward", fake):
            report = score_snapshot(form)
        self.assertEqual(SNAPSHOT_GAMES, 200)
        self.assertEqual(SNAPSHOT_SEED, 20001)
        self.assertEqual(report["games"], 200)
        self.assertEqual(report["seed"], 20001)
        self.assertEqual(len(seen), 200 * 7)
        self.assertEqual(min(seed for seed, *_rest in seen), 20001)
        self.assertEqual(max(seed for seed, *_rest in seen), SNAPSHOT_SEED + SNAPSHOT_GAMES - 1)
        self.assertTrue(all(window == (37, 72) and regime == "chop" and shop == "none" for _seed, window, regime, shop in seen))
        self.assertEqual(names(report), ["steady", "grind", "yolo", "owner", "coast"])
        server = Path("money_sim/server.py").read_text(encoding="utf-8")
        self.assertIn("score_snapshot(data)", server)
        self.assertNotIn("score_snapshot(data,", server)

    def test_a_real_forward_month_uses_only_its_window(self):
        early = build_snapshot(example_form(month=13))
        played = play_forward(policy_steady, early, 20001, glide_bounds(13))
        self.assertEqual(early.month, 13)
        self.assertGreater(sum(played["phase_employ"]["early"].values()), 0)
        self.assertEqual(played["glide_months"], sum(played["phase_employ"]["mid"].values()))

        late = build_snapshot(example_form(month=80, cash=1_000, portfolio=0))
        played = play_forward(policy_steady, late, 20001, glide_bounds(80))
        self.assertEqual(played["phase_employ"]["early"], {})
        self.assertEqual(played["phase_employ"]["mid"], {})
        self.assertEqual(played["glide_months"], sum(played["phase_employ"]["late"].values()))
        self.assertGreater(played["glide_months"], 0)

        on_the_line = build_snapshot(example_form(month=72, cash=1_000, portfolio=0))
        played = play_forward(policy_steady, on_the_line, 20001, glide_bounds(72))
        self.assertEqual(sum(played["phase_employ"]["mid"].values()), 1)
        self.assertEqual(played["glide_months"], 1)

    def test_example_forward_does_not_rewrite_the_standard_table(self):
        before = Path("web/routes.json").read_text(encoding="utf-8")
        report = score_snapshot(example_form(), games=1)
        self.assertEqual(Path("web/routes.json").read_text(encoding="utf-8"), before)
        self.assertTrue(report["scored"])
        self.assertEqual(report["glide_from"], 37)
        self.assertEqual(report["glide_to"], 72)
        self.assertIn("不把达成率最高的标成最优", report["message"])
        self.assertEqual(names(report), [name for name in ["steady", "grind", "yolo", "owner", "coast"] if name in set(names(report))])
        kept = ["steady", "grind", "yolo", "owner", "coast"]
        self.assertEqual(names(report), [name for name in kept if name in names(report)])
        for route in report["routes"]:
            self.assertNotIn("前 36 个月", route["mainline"])
            self.assertNotIn("best", route)
            if route["name"] != "steady":
                self.assertEqual(route["variants"], [])
            for variant in route["variants"]:
                self.assertIn(variant["name"], ("nest", "ease"))
                self.assertNotIn("前 36 个月", variant["mainline"])
        table = json.loads(before)
        steady = next(item for item in table["routes"] if item["name"] == "steady")
        self.assertEqual(table["seed"], 1)
        self.assertEqual(steady["win_rate"], 0.611)
        self.assertIn("前 36 个月", steady["mainline"])
        self.assertEqual([item["name"] for item in table["routes"]], kept)
        page = Path("web/index.html").read_text(encoding="utf-8")
        self.assertIn("从这一月打分", page)
        self.assertIn("结算本月", page)
        self.assertNotIn("开局景气", page)


class SnapshotApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.httpd = make_server("127.0.0.1", 0, root / "game.jsonl", root / "manual.json", seed=1)
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
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def test_scoring_does_not_move_the_open_game(self):
        status, before = self.request("/api/state")
        self.assertEqual(status, 200)
        status, body = self.request("/api/snapshot", example_form(month=108))
        self.assertEqual(status, 200)
        self.assertFalse(body["scored"])
        status, after = self.request("/api/state")
        self.assertEqual(after["month"], before["month"])
        self.assertEqual(after["realizable"], before["realizable"])
        self.assertEqual(after["realizable"], 720_000)
        status, rejected = self.request("/api/snapshot", example_form(locked=10, portfolio=0))
        self.assertEqual(status, 400)
        self.assertIn("封闭", rejected["error"])


if __name__ == "__main__":
    unittest.main()
