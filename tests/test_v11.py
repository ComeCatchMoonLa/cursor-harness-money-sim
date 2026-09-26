"""V11：留出种子上重判路线。规则在看到 10001 到 11000 的结果之前写定。"""

from __future__ import annotations

import unittest

from money_sim.routes import HOLDOUT_MERGED, rank_names, retain_routes, ship_notches, starting_policies


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


def _holdout_rows() -> list[dict]:
    """docs/dev/测试/v11-balance.md 留出种子那张表。"""
    return [
        _row("steady", win_rate=0.584, median_win_month=80, glide_intensity=0.886, glide_autonomy=69.3, mean_net=1_406_292),
        _row("grind", win_rate=0.025, median_win_month=55, hard_fail_rate=0.027, glide_intensity=0.751, glide_autonomy=63.2, mean_net=270_630),
        _row("yolo", win_rate=0.0, median_win_month=None, hard_fail_rate=1.0, glide_intensity=0.0, glide_autonomy=86.1, mean_net=-168_014),
        _row("owner", win_rate=0.064, median_win_month=94.5, glide_intensity=0.788, glide_autonomy=93.0, mean_net=900_622),
        _row("nest", win_rate=0.623, median_win_month=90, glide_intensity=0.885, glide_autonomy=71.1, mean_net=1_448_740),
        _row("ease", win_rate=0.583, median_win_month=83, glide_intensity=0.853, glide_autonomy=72.4, mean_net=1_406_506),
        _row("coast", win_rate=0.486, median_win_month=92, glide_intensity=0.817, glide_autonomy=72.8, mean_net=1_387_250),
    ]


class RouteListTests(unittest.TestCase):
    def test_holdout_merge_drops_nest_and_ease_from_the_listed_routes(self):
        names = [name for name, _policy in starting_policies()]
        self.assertEqual(names, ["steady", "grind", "yolo", "owner", "coast"])
        self.assertEqual(HOLDOUT_MERGED, {"nest": "steady", "ease": "steady"})

    def test_published_holdout_table_merges_nest_and_ease_into_steady(self):
        kept, merged = retain_routes(_holdout_rows())
        self.assertEqual([row["name"] for row in kept], ["steady", "grind", "yolo", "owner", "coast"])
        self.assertEqual(
            merged,
            [
                {"name": "nest", "into": "steady", "gaps": ["达标时间"]},
                {"name": "ease", "into": "steady", "gaps": ["时间自主"]},
            ],
        )


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

    def test_nest_below_the_recorded_plateau_does_not_ship_even_if_steady_holds(self):
        old = [_row("steady"), _row("nest")]
        new = [_row("steady"), _row("nest", win_rate=0.40, glide_autonomy=80)]
        seed1 = [_row("steady", win_rate=0.611), _row("nest", win_rate=0.548)]
        self.assertFalse(ship_notches(old, new, seed1))

    def test_a_new_split_above_the_plateau_ships(self):
        old = [_row("steady"), _row("nest")]
        new = [_row("steady"), _row("nest", win_rate=0.40, glide_autonomy=80)]
        seed1 = [_row("steady", win_rate=0.611), _row("nest", win_rate=0.645)]
        self.assertTrue(ship_notches(old, new, seed1))
