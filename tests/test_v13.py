"""V13：涨幅拆一半没有让少工作重新分开。拆法不留在结算里。"""

from __future__ import annotations

import unittest

from money_sim.engine import resolve
from money_sim.policies import policy_steady
from money_sim.rule_search import separates
from money_sim.state import new_game
from tests.test_engine import assert_identity


def _row(**overrides) -> dict:
    base = {
        "name": "sample",
        "win_rate": 0.586,
        "median_win_month": 80,
        "hard_fail_rate": 0.0,
        "glide_intensity": 0.8858901324672152,
        "glide_autonomy": 69.38393178394402,
        "mean_intensity": 0.8858901324672152,
        "mean_autonomy": 69.38393178394402,
        "mean_net": 1_406_554.109,
        "suspect_wealth_games": 0,
        "max_jump": 0.1609382345154022,
    }
    base.update(overrides)
    return base


class RevertTests(unittest.TestCase):
    def test_a_settled_month_does_not_split_cash_out_of_the_gain(self):
        state = new_game(1)
        before = state.clone()
        state, errors, report = resolve(state, policy_steady(before))
        self.assertEqual(errors, [])
        assert_identity(before, state, report)
        self.assertNotIn("gain_cash", report)
        self.assertFalse(any(row["reason"] == "gain_cash" for row in report["ledger"]))

    def test_recorded_holdout_ease_still_has_only_one_axis(self):
        steady = _row(name="steady")
        ease = _row(
            name="ease",
            win_rate=0.572,
            median_win_month=83,
            glide_intensity=0.8527325483654536,
            glide_autonomy=72.48297899954497,
            mean_intensity=0.8527325483654536,
            mean_autonomy=72.48297899954497,
            mean_net=1_404_619.373,
            max_jump=0.1541773796461578,
        )
        self.assertFalse(separates(ease, [steady]))
        autonomy_gap = abs(ease["glide_autonomy"] - steady["glide_autonomy"])
        intensity_gap = abs(ease["glide_intensity"] - steady["glide_intensity"])
        self.assertGreaterEqual(autonomy_gap, 3)
        self.assertLess(intensity_gap, 0.05)
        self.assertLess(abs(ease["win_rate"] - steady["win_rate"]), 0.05)
        self.assertLess(abs(ease["median_win_month"] - steady["median_win_month"]), 6)


if __name__ == "__main__":
    unittest.main()
