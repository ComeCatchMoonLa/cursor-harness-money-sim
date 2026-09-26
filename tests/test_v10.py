"""V10：条件路线要在两个轴上分开才留下。只比财富更高不算。"""

from __future__ import annotations

import unittest

from money_sim.engine import ease_of
from money_sim.policies import policy_ease, policy_owner
from money_sim.routes import (
    axis_gaps,
    breaks_rules,
    different,
    describe_mainline,
    lighten_automated,
    policy_coast,
    policy_craft,
    policy_dwell,
)
from money_sim.state import Plan, new_game


def _row(**overrides) -> dict:
    base = {
        "name": "sample",
        "win_rate": 0.55,
        "hard_fail_rate": 0.02,
        "mean_intensity": 0.84,
        "mean_autonomy": 48.0,
        "median_win_month": 70,
        "mean_net": 1_400_000,
        "suspect_wealth_games": 0,
        "max_jump": 0.2,
    }
    base.update(overrides)
    return base


def _ahead():
    state = new_game(1)
    state.month = 70
    state.career = 60
    state.career_fresh = 12
    state.network = 4
    state.cash = 200_000
    state.portfolio = 1_200_000
    state.energy = 70
    state.stress = 20
    state.autonomy = 50
    state.condition = 50
    state.regime = "chop"
    state.lifestyle = 100
    state.price_index = 1_000
    return state


def _open_not_covered():
    state = _ahead()
    state.portfolio = 1_000_000
    return state


class AxisTests(unittest.TestCase):
    def test_richer_alone_is_not_a_difference(self):
        left = _row()
        right = _row(name="richer", mean_net=2_000_000)
        self.assertEqual(axis_gaps(left, right), [])
        self.assertFalse(different(left, right))

    def test_one_axis_is_not_enough(self):
        self.assertEqual(axis_gaps(_row(), _row(mean_autonomy=60)), ["时间自主"])
        self.assertFalse(different(_row(), _row(mean_autonomy=60)))

    def test_midgame_window_overrides_the_whole_game_average(self):
        whole = _row(mean_intensity=0.86, mean_autonomy=62, glide_intensity=0.70, glide_autonomy=74)
        other = _row(mean_intensity=0.86, mean_autonomy=62, glide_intensity=0.86, glide_autonomy=62)
        gaps = axis_gaps(whole, other)
        self.assertIn("工作强度", gaps)
        self.assertIn("时间自主", gaps)
        self.assertTrue(different(whole, other))

    def test_two_axes_count(self):
        other = _row(mean_intensity=0.55, mean_autonomy=58, median_win_month=80)
        gaps = axis_gaps(_row(), other)
        self.assertIn("工作强度", gaps)
        self.assertIn("时间自主", gaps)
        self.assertIn("达标时间", gaps)
        self.assertTrue(different(_row(), other))

    def test_missing_wins_do_not_invent_a_month_gap(self):
        self.assertNotIn("达标时间", axis_gaps(_row(), _row(median_win_month=None, mean_intensity=0.5)))

    def test_a_jump_or_a_sweep_is_a_hole(self):
        plain = _row()
        jumper = _row(name="jumper", max_jump=0.8, win_rate=0.4, mean_intensity=0.4, mean_autonomy=70)
        self.assertTrue(breaks_rules(jumper, [plain]))
        swept = _row(
            name="swept",
            win_rate=0.9,
            hard_fail_rate=0.0,
            mean_net=2_000_000,
            mean_intensity=0.4,
            mean_autonomy=70,
        )
        weak = _row(name="weak", win_rate=0.2, hard_fail_rate=0.1, mean_net=800_000)
        self.assertTrue(breaks_rules(swept, [weak]))

    def test_mainline_names_the_second_employment(self):
        text = describe_mainline(
            {
                "mainline": {
                    "early": {"employment": "full", "share": 0.9, "second": {"employment": "free", "share": 0.1}},
                    "mid": {"employment": "light", "share": 0.95, "second": {"employment": "full", "share": 0.04}},
                    "late": {"employment": "free", "share": 0.7, "second": {"employment": "light", "share": 0.2}},
                }
            }
        )
        self.assertIn("前 36 个月多半是全职", text)
        self.assertIn("73 月以后多半是不拿固定工资", text)
        self.assertIn("变招", text)
        self.assertNotIn("37 到 72 月还有", text)


class CoastTests(unittest.TestCase):
    def test_coast_is_promoted_and_played_for_eighteen_months(self):
        from money_sim.engine import resolve, validate
        from money_sim.routes import CANDIDATES, starting_policies
        from tests.test_engine import assert_identity

        names = [name for name, _policy in starting_policies()]
        self.assertEqual(names.count("coast"), 1)
        self.assertNotIn("coast", [name for name, _policy in CANDIDATES])
        state = new_game(5)
        for _ in range(18):
            if state.status != "playing":
                break
            plan = policy_coast(state)
            self.assertEqual(validate(state, plan), [])
            previous = state
            state, errors, report = resolve(state, plan)
            self.assertEqual(errors, [])
            assert_identity(previous, state, report)
    def test_covered_month_drops_wages(self):
        state = _ahead()
        self.assertTrue(ease_of(state)["covered"])
        plan = policy_coast(state)
        self.assertEqual(plan.employment, "free")
        self.assertEqual(len(plan.slots), 4)
        self.assertEqual(policy_ease(state).employment, "light")

    def test_open_but_not_covered_stays_on_light(self):
        state = _open_not_covered()
        position = ease_of(state)
        self.assertTrue(position["open"])
        self.assertFalse(position["covered"])
        self.assertEqual(policy_coast(state).employment, "light")

    def test_bull_and_contract_keep_the_wage(self):
        bull = _ahead()
        bull.regime = "bull"
        self.assertNotEqual(policy_coast(bull).employment, "free")
        bound = _ahead()
        bound.contract_left = 4
        self.assertNotEqual(policy_coast(bound).employment, "free")

    def test_opening_matches_ease(self):
        state = new_game(3)
        coast = policy_coast(state)
        ease = policy_ease(state)
        self.assertEqual(coast.employment, ease.employment)
        self.assertNotEqual(coast.employment, "free")


class OtherRouteTests(unittest.TestCase):
    def test_dwell_buys_only_when_nest_can(self):
        from money_sim.policies import policy_nest

        opening = new_game(1)
        self.assertEqual(policy_dwell(opening).buy_home, policy_nest(opening).buy_home)
        blocked = new_game(1)
        blocked.regime = "bear"
        self.assertFalse(policy_nest(blocked).buy_home)
        self.assertFalse(policy_dwell(blocked).buy_home)
        ahead = _ahead()
        bought = policy_dwell(ahead)
        self.assertTrue(policy_nest(ahead).buy_home)
        self.assertTrue(bought.buy_home)
        self.assertEqual(bought.employment, "light")
        self.assertEqual(bought.from_index, policy_nest(ahead).from_index)

    def test_automated_shop_can_go_light_once_the_position_is_open(self):
        state = _ahead()
        state.business_stage = "running"
        state.business_book = 160_000
        full = Plan("full", ["invest"], automate=True, to_index=1_000)
        eased = lighten_automated(state, full)
        self.assertEqual(eased.employment, "light")
        self.assertEqual(len(eased.slots), 2)
        self.assertTrue(eased.automate)
        watching = Plan("full", ["venture"], automate=False)
        self.assertEqual(lighten_automated(state, watching).employment, "full")
        early = new_game(1)
        self.assertEqual(lighten_automated(early, full).employment, "full")
        self.assertEqual(policy_owner(early).employment, policy_after_shop_employment(early))

    def test_craft_studies_instead_of_investing_before_the_position_opens(self):
        state = new_game(1)
        state.month = 40
        state.career = 60
        state.career_fresh = 12
        state.energy = 80
        state.condition = 78
        state.stress = 20
        state.autonomy = 80
        state.regime = "chop"
        base = policy_ease(state)
        self.assertEqual(base.employment, "full")
        self.assertIn("invest", base.slots)
        studied = policy_craft(state)
        self.assertIn("learn_career", studied.slots)
        self.assertNotIn("invest", studied.slots)


def policy_after_shop_employment(state):
    from money_sim.routes import policy_after_shop

    return policy_after_shop(state).employment
