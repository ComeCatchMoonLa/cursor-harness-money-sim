"""V8：到了靠储蓄仍可能碰到 150 万的位置，可以少工作。没到这个位置，轻职不合法。"""

from __future__ import annotations

import unittest

from money_sim.constants import LIGHT_DEN, LIGHT_NUM
from money_sim.economy import ease_position, salary
from money_sim.engine import ease_of, quote, resolve, validate
from money_sim.policies import policy_ease, policy_grind, policy_steady
from money_sim.state import Plan, new_game, realizable_net
from tests.test_engine import assert_identity


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


class EaseRuleTests(unittest.TestCase):
    def test_opening_position_is_closed_and_light_is_illegal(self):
        state = new_game(1)
        self.assertFalse(ease_of(state)["open"])
        self.assertTrue(validate(state, Plan("light", ["rest", "rest"])))

    def test_light_pays_less_than_full_and_more_than_part(self):
        full = salary(60, 4, "full")
        light = salary(60, 4, "light")
        part = salary(60, 4, "part")
        self.assertEqual(light, full * LIGHT_NUM // LIGHT_DEN)
        self.assertLess(light, full)
        self.assertGreater(light, part)

    def test_ahead_and_worn_can_ease_and_autonomy_rises(self):
        state = _ahead()
        self.assertTrue(ease_of(state)["open"])
        self.assertGreaterEqual(ease_of(state)["projected"], 1_500_000)
        quoted = quote(state, Plan("light", ["rest", "rest"]))
        out, errors, report = resolve(state, Plan("light", ["rest", "rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], quoted["salary"])
        self.assertEqual(report["salary"], salary(60, 4, "light"))
        self.assertEqual(out.autonomy, 50 + 2 + 2 + 2)
        self.assertEqual(quoted["autonomy_next"], out.autonomy)
        self.assertEqual(quoted["condition_next"], out.condition)
        self.assertGreater(out.condition, 50)
        assert_identity(state, out, report)

    def test_same_wealth_with_a_heavy_mortgage_stays_closed(self):
        renter = _ahead()
        owner = renter.clone()
        owner.home_value = 900_000
        owner.mortgage = 580_000
        owner.mortgage_payment = 12_000
        owner.portfolio -= realizable_net(owner) - realizable_net(renter)
        self.assertEqual(realizable_net(owner), realizable_net(renter))
        self.assertTrue(ease_of(renter)["open"])
        self.assertFalse(ease_of(owner)["open"])
        self.assertTrue(validate(owner, Plan("light", ["rest", "rest"])))

    def test_projection_uses_savings_not_a_fixed_sum(self):
        closed = ease_position(900_000, 40, 24, 4, 13_200)
        opened = ease_position(1_400_000, 70, 60, 4, 13_200)
        self.assertFalse(closed["open"])
        self.assertTrue(opened["open"])
        self.assertNotEqual(closed["projected"], opened["projected"])

    def test_fewer_than_six_months_left_stays_closed(self):
        late = ease_position(1_450_000, 104, 60, 4, 13_200)
        still = ease_position(1_450_000, 103, 60, 4, 13_200)
        self.assertGreaterEqual(late["projected_full"], 1_500_000)
        self.assertGreater(late["monthly_save"], 0)
        self.assertEqual(late["months_left"], 5)
        self.assertFalse(late["open"])
        self.assertEqual(still["months_left"], 6)
        self.assertTrue(still["open"])

    def test_early_career_growth_does_not_open_the_position(self):
        early = ease_position(800_000, 8, 48, 4, 13_200)
        self.assertFalse(early["open"])

    def test_contested_band_opens_before_light_savings_cover_the_line(self):
        band = ease_position(1_200_000, 70, 60, 4, 13_200)
        self.assertTrue(band["open"])
        self.assertGreaterEqual(band["projected_full"], 1_500_000)
        self.assertLess(band["projected"], 1_500_000)
        self.assertFalse(band["covered"])


class EasePolicyTests(unittest.TestCase):
    def test_ease_works_less_only_when_the_position_is_open_and_worn(self):
        early = policy_ease(new_game(1))
        self.assertNotEqual(early.employment, "light")
        worn = _ahead()
        self.assertEqual(policy_ease(worn).employment, "light")
        self.assertEqual(len(policy_ease(worn).slots), 2)
        self.assertEqual(policy_steady(worn).employment, "full")
        self.assertNotEqual(policy_grind(worn).employment, "light")

    def test_contract_blocks_light_and_an_open_position_does_not_renew(self):
        bound = _ahead()
        bound.contract_left = 3
        self.assertNotEqual(policy_ease(bound).employment, "light")
        self.assertEqual(policy_ease(bound).sign_months, 0)
        bull = _ahead()
        bull.regime = "bull"
        stayed = policy_ease(bull)
        self.assertNotEqual(stayed.employment, "light")
        self.assertEqual(stayed.sign_months, 0)
        self.assertEqual(policy_steady(bull).sign_months, 6)

    def test_a_recovered_state_stays_on_light_and_a_bull_market_does_not(self):
        healthy = _ahead()
        healthy.condition = 70
        healthy.autonomy = 70
        stayed = policy_ease(healthy)
        self.assertEqual(stayed.employment, "light")
        self.assertEqual(len(stayed.slots), 2)
        bull = healthy.clone()
        bull.regime = "bull"
        self.assertNotEqual(policy_ease(bull).employment, "light")
        self.assertEqual(policy_steady(healthy).employment, "full")

    def test_contract_rejects_light_and_light_cannot_sign(self):
        bound = _ahead()
        bound.contract_left = 2
        self.assertIn("合同没到期", validate(bound, Plan("light", ["rest", "rest"])))
        free = _ahead()
        errors = validate(free, Plan("light", ["rest", "rest"], sign_months=6))
        self.assertTrue(any("不能再签" in item for item in errors))

    def test_the_month_after_light_work_is_not_steady(self):
        state = _ahead()
        first = policy_ease(state)
        self.assertEqual(first.employment, "light")
        state, errors, _ = resolve(state, first)
        self.assertEqual(errors, [])
        self.assertGreater(state.autonomy, 50)
        self.assertEqual(policy_ease(state).employment, "light")
        self.assertEqual(policy_steady(state).employment, "full")


if __name__ == "__main__":
    unittest.main()
