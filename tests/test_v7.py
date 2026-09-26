"""V7：状态掉得慢。休息补不满全职，消费只在偏低时补，低到底就不能全职。"""

from __future__ import annotations

import unittest

from money_sim.constants import MIN_CONSUME, START_CONDITION
from money_sim.economy import condition_after, salary
from money_sim.engine import quote, resolve, validate
from money_sim.policies import policy_grind, policy_owner, policy_steady
from money_sim.state import Plan, from_save_dict, new_game, to_save_dict
from tests.test_engine import assert_identity


def _open(condition: int, seed: int = 1):
    state = new_game(seed)
    state.condition = condition
    state.energy = 76
    state.stress = 20
    state.career = 60
    state.career_fresh = 12
    state.autonomy = 42
    state.cash = 180_000
    return state


class ConditionRuleTests(unittest.TestCase):
    def test_full_time_plus_rest_still_falls(self):
        worn = _open(70)
        out, errors, _ = resolve(worn, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(out.condition, condition_after(70, "full", ["rest"]))
        self.assertEqual(out.condition, 68)
        eased = _open(78)
        out, errors, _ = resolve(eased, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(out.condition, 73)

    def test_spend_does_not_buy_condition(self):
        low = _open(50)
        small, small_errors, small_report = resolve(low, Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        large, large_errors, large_report = resolve(low.clone(), Plan("full", ["consume"], consume_cash=30_000))
        self.assertEqual(small_errors, [])
        self.assertEqual(large_errors, [])
        self.assertEqual(small.condition, 53)
        self.assertEqual(large.condition, small.condition)
        assert_identity(low, small, small_report)
        assert_identity(low.clone(), large, large_report)

    def test_consume_fades_as_condition_recovers(self):
        mid = _open(60)
        out, errors, _ = resolve(mid, Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertEqual(errors, [])
        self.assertEqual(out.condition, 57)
        high = _open(80)
        out, errors, _ = resolve(high, Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertEqual(errors, [])
        self.assertEqual(out.condition, 75)

    def test_each_consume_slot_counts_and_quote_matches(self):
        state = _open(50)
        plan = Plan("part", ["consume", "consume"], consume_cash=MIN_CONSUME * 2)
        quoted = quote(state, plan)
        out, errors, _ = resolve(state, plan)
        self.assertEqual(errors, [])
        self.assertEqual(quoted["condition_next"], 64)
        self.assertEqual(out.condition, quoted["condition_next"])

    def test_study_and_shop_wear_it_further(self):
        studied, errors, _ = resolve(_open(70), Plan("full", ["learn_career"]))
        self.assertEqual(errors, [])
        self.assertEqual(studied.condition, 64)
        shop = _open(70)
        shop.business_stage = "running"
        shop.business_book = 20_000
        shop.venture = 40
        worked, errors, _ = resolve(shop, Plan("full", ["venture"]))
        self.assertEqual(errors, [])
        self.assertEqual(worked.condition, 64)

    def test_below_forty_blocks_full_time_and_a_new_contract(self):
        state = _open(39)
        self.assertTrue(any("无法全职" in item for item in validate(state, Plan("full", ["rest"]))))
        self.assertTrue(validate(state, Plan("full", ["rest"], sign_months=6)))
        out, errors, report = resolve(state, Plan("free", ["rest", "rest", "rest", "rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], 0)
        self.assertEqual(out.condition, 53)

    def test_contract_becomes_unpaid_leave(self):
        state = _open(30)
        state.contract_left = 4
        state.contract_term = 6
        blocked = validate(state, Plan("full", ["rest"]))
        self.assertTrue(any("停薪请假" in item for item in blocked))
        out, errors, report = resolve(state, Plan("free", ["rest", "rest", "rest", "rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], 0)
        self.assertTrue(any("停薪请假" in note for note in report["notes"]))
        self.assertEqual(out.contract_left, 3)
        self.assertGreater(out.condition, 30)

    def test_salary_formula_ignores_condition(self):
        state = _open(45)
        state.career = 40
        state.network = 4
        _, errors, report = resolve(state, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], salary(40, 4, "full"))

    def test_old_save_without_condition_loads(self):
        data = to_save_dict(new_game(1))
        del data["condition"]
        loaded = from_save_dict(data)
        self.assertEqual(loaded.condition, START_CONDITION)


class ConditionPolicyTests(unittest.TestCase):
    def test_grind_takes_the_month_off_and_still_does_not_spend(self):
        plan = policy_grind(_open(39))
        self.assertEqual(plan.employment, "free")
        self.assertEqual(plan.slots, ["rest", "rest", "rest", "rest"])
        self.assertEqual(plan.consume_cash, 0)

    def test_steady_spends_to_hold_a_low_condition_even_with_high_autonomy(self):
        state = _open(50)
        state.autonomy = 80
        plan = policy_steady(state)
        self.assertEqual(plan.employment, "full")
        self.assertIn("consume", plan.slots)
        self.assertEqual(plan.consume_cash, MIN_CONSUME)

    def test_high_condition_and_high_autonomy_do_not_spend(self):
        state = _open(80)
        state.autonomy = 80
        plan = policy_steady(state)
        self.assertNotIn("consume", plan.slots)
        self.assertEqual(plan.consume_cash, 0)

    def test_owner_does_not_keep_the_shop_slot_while_crashed(self):
        state = _open(30)
        state.business_stage = "running"
        state.venture = 50
        state.venture_fresh = 10
        state.business_book = 100_000
        state.last_business_net = 1_000
        plan = policy_owner(state)
        self.assertNotEqual(plan.employment, "full")
        self.assertNotIn("venture", plan.slots)
        self.assertNotIn("learn_venture", plan.slots)


if __name__ == "__main__":
    unittest.main()
