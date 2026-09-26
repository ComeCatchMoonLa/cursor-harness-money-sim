"""V11：留出种子上重判路线。规则在看到 10001 到 11000 的结果之前写定。"""

from __future__ import annotations

import unittest

from money_sim.routes import rank_names, retain_routes, ship_notches


def _row(name: str, **overrides) -> dict:
    base = {
        "name": name,
        "win_rate": 0.50,
        "hard_fail_rate": 0.0,
        "median_win_month": 80,
        "mean_intensity": 0.80,
        "mean_autonomy": 70.0,
        "glide_intensity": 0.80,
        "glide_autonomy": 70.0,
        "mean_net": 1_400_000,
    }
    base.update(overrides)
    return base


class RetainTests(unittest.TestCase):
    def test_one_axis_merges_into_the_earlier_route(self):
        rows = [
            _row("steady"),
            _row("ease", win_rate=0.40),
        ]
        kept, merged = retain_routes(rows, ("steady", "ease"))
        self.assertEqual([row["name"] for row in kept], ["steady"])
        self.assertEqual(merged, [{"name": "ease", "into": "steady", "gaps": ["达成"]}])

    def test_two_axes_stay_apart(self):
        rows = [
            _row("steady"),
            _row("ease", win_rate=0.40, glide_autonomy=80.0),
        ]
        kept, merged = retain_routes(rows, ("steady", "ease"))
        self.assertEqual([row["name"] for row in kept], ["steady", "ease"])
        self.assertEqual(merged, [])

    def test_equal_gap_counts_merge_into_the_earlier_name(self):
        rows = [
            _row("steady", glide_intensity=0.90),
            _row("nest", win_rate=0.40, glide_intensity=0.70),
            _row("ease", glide_intensity=0.70),
        ]
        _kept, merged = retain_routes(rows, ("steady", "nest", "ease"))
        self.assertEqual([item["name"] for item in merged], ["ease"])
        self.assertEqual(merged[0]["into"], "steady")
        self.assertEqual(len(merged[0]["gaps"]), 1)

    def test_rank_puts_higher_win_rate_first_and_no_wins_last(self):
        rows = [
            _row("nest", win_rate=0.60, median_win_month=90),
            _row("steady", win_rate=0.60, median_win_month=80),
            _row("yolo", win_rate=0.0, median_win_month=None),
        ]
        self.assertEqual(rank_names(rows), ["steady", "nest", "yolo"])


class NotchTests(unittest.TestCase):
    def test_same_retained_names_do_not_ship(self):
        old = [_row("steady"), _row("nest", win_rate=0.40, glide_autonomy=80)]
        new = [_row("steady", win_rate=0.58), _row("nest", win_rate=0.40, glide_autonomy=80)]
        seed1 = [_row("steady", win_rate=0.611), _row("nest", win_rate=0.645)]
        self.assertFalse(ship_notches(old, new, seed1))

    def test_a_new_split_that_lowers_the_plateau_does_not_ship(self):
        old = [_row("steady"), _row("nest")]
        new = [_row("steady"), _row("nest", win_rate=0.40, glide_autonomy=80)]
        seed1 = [_row("steady", win_rate=0.60), _row("nest", win_rate=0.645)]
        self.assertFalse(ship_notches(old, new, seed1))

    def test_a_new_split_above_the_plateau_ships(self):
        old = [_row("steady"), _row("nest")]
        new = [_row("steady"), _row("nest", win_rate=0.40, glide_autonomy=80)]
        seed1 = [_row("steady", win_rate=0.611), _row("nest", win_rate=0.645)]
        self.assertTrue(ship_notches(old, new, seed1))
