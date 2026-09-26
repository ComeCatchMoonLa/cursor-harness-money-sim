"""V6：消费槽换时间自主，并把之后的生活费地板抬高。"""

from __future__ import annotations

import unittest

from money_sim.constants import CONSUME_AUTONOMY, MIN_CONSUME
from money_sim.economy import consume_lifestyle_gain, consume_outlook, living_cost, salary
from money_sim.engine import preview, quote, resolve
from money_sim.policies import policy_grind, policy_owner, policy_steady
from money_sim.state import Plan, new_game
from tests.test_engine import assert_identity


def _ready(seed: int = 1):
    state = new_game(seed)
    state.career = 60
    state.career_fresh = 12
    state.energy = 76
    state.stress = 20
    state.autonomy = 42
    state.cash = 180_000
    return state


class ConsumeRuleTests(unittest.TestCase):
    def test_slot_buys_autonomy_and_extra_money_does_not(self):
        small_before = _ready()
        large_before = small_before.clone()
        small, errors, small_report = resolve(small_before, Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        large, large_errors, large_report = resolve(large_before, Plan("full", ["consume"], consume_cash=30_000))
        self.assertEqual(errors, [])
        self.assertEqual(large_errors, [])
        assert_identity(small_before, small, small_report)
        assert_identity(large_before, large, large_report)
        self.assertEqual(small.autonomy, 42 - 3 + CONSUME_AUTONOMY)
        self.assertEqual(large.autonomy, small.autonomy)
        self.assertEqual(small.lifestyle, 102)
        self.assertEqual(large.lifestyle, 103)
        self.assertEqual(consume_lifestyle_gain(MIN_CONSUME), 2)
        self.assertEqual(consume_lifestyle_gain(30_000), 3)
        self.assertEqual(small.career, 60)
        self.assertEqual(large.career, 60)
        self.assertEqual(small.mortgage_payment, 0)
        self.assertEqual(large.mortgage_payment, 0)

    def test_two_consume_slots_do_not_stack_autonomy(self):
        state = _ready()
        out, errors, _ = resolve(state, Plan("part", ["consume", "consume"], consume_cash=4_000))
        self.assertEqual(errors, [])
        self.assertEqual(out.autonomy, 42 + 1 + CONSUME_AUTONOMY)

    def test_rest_restores_more_energy_and_less_autonomy(self):
        state = _ready()
        rested, errors, _ = resolve(state, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        spent, _, _ = resolve(_ready(), Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertGreater(rested.energy, spent.energy)
        self.assertLess(rested.autonomy, spent.autonomy)
        self.assertEqual(rested.lifestyle, 100)
        self.assertGreater(spent.lifestyle, rested.lifestyle)

    def test_this_month_living_matches_the_raised_lifestyle(self):
        state = _ready()
        plan = Plan("full", ["consume"], consume_cash=MIN_CONSUME)
        quoted = quote(state, plan)
        out, errors, report = resolve(state, plan)
        self.assertEqual(errors, [])
        self.assertEqual(quoted["living"], living_cost(102, state.price_index))
        self.assertEqual(report["living"], quoted["living"])
        self.assertGreater(quoted["living_delta_rent"], quoted["living_delta_own"])
        self.assertGreater(quoted["living_delta_own"], 0)
        self.assertEqual(quoted["consume_autonomy"], CONSUME_AUTONOMY)
        preview_text = " ".join(preview(_ready(), plan)["warnings"])
        self.assertIn(str(quoted["living_delta_rent"]), preview_text)
        self.assertIn(str(quoted["living_delta_own"]), preview_text)

    def test_owner_pays_less_of_the_same_lifestyle_step(self):
        renter = _ready()
        owner = _ready()
        owner.home_value = 900_000
        owner.mortgage = 580_000
        owner.mortgage_payment = 3_797
        plan = Plan("full", ["consume"], consume_cash=MIN_CONSUME)
        rent_quote = quote(renter, plan)
        own_quote = quote(owner, plan)
        self.assertGreater(rent_quote["living"], own_quote["living"])
        self.assertEqual(rent_quote["mortgage_payment"], 0)
        self.assertEqual(own_quote["mortgage_payment"], 3_797)
        _, _, rent_report = resolve(renter, plan)
        _, _, own_report = resolve(owner, plan)
        self.assertEqual(rent_report["living"], rent_quote["living"])
        self.assertEqual(own_report["living"], own_quote["living"])
        self.assertEqual(own_report["mortgage_payment"] if "mortgage_payment" in own_report else owner.mortgage_payment, 3_797)

    def test_skipping_a_month_lets_the_floor_fall_back_one(self):
        state, errors, _ = resolve(_ready(), Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertEqual(errors, [])
        self.assertEqual(state.lifestyle, 102)
        state, errors, _ = resolve(state, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(state.lifestyle, 101)

    def test_low_autonomy_makes_next_months_learning_worse_if_you_skip(self):
        broke = _ready()
        broke.autonomy = 26
        broke.career = 40
        broke.career_fresh = 10
        spent_state, _, _ = resolve(broke.clone(), Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        rested_state, _, _ = resolve(broke.clone(), Plan("full", ["rest"]))
        self.assertGreaterEqual(spent_state.autonomy, 28)
        self.assertLess(rested_state.autonomy, 28)
        spent_learn, _, _ = resolve(spent_state, Plan("full", ["learn_career"]))
        rested_learn, _, _ = resolve(rested_state, Plan("full", ["learn_career"]))
        self.assertGreater(spent_learn.career, rested_learn.career)

    def test_late_rust_is_slower_after_the_autonomy_bump(self):
        low = _ready()
        low.month = 70
        low.autonomy = 62
        low.career_fresh = 0
        low.career = 40
        rested, _, _ = resolve(low.clone(), Plan("full", ["rest"]))
        spent, _, _ = resolve(low.clone(), Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertLess(rested.autonomy, 65)
        self.assertGreaterEqual(spent.autonomy, 65)
        _, _, rested_next = resolve(rested, Plan("full", ["rest"]))
        _, _, spent_next = resolve(spent, Plan("full", ["rest"]))
        self.assertTrue(any("掉了 2 点" in note for note in rested_next["notes"]))
        self.assertTrue(any("掉了 1 点" in note for note in spent_next["notes"]))

    def test_outlook_uses_the_engine_delta(self):
        outlook = consume_outlook(100, 1000, MIN_CONSUME, True)
        self.assertEqual(outlook["charged_lifestyle"], 102)
        self.assertGreater(outlook["living_delta_rent"], outlook["living_delta_own"])
        self.assertEqual(outlook["rent_delta"], outlook["living_delta_rent"] - outlook["living_delta_own"])


class ConsumePolicyTests(unittest.TestCase):
    def test_bull_market_keeps_the_invest_slot(self):
        state = _ready()
        state.regime = "bull"
        plan = policy_steady(state)
        self.assertIn("invest", plan.slots)
        self.assertNotIn("consume", plan.slots)

    def test_steady_spends_the_minimum_when_autonomy_is_the_constraint(self):
        state = _ready()
        plan = policy_steady(state)
        self.assertIn("consume", plan.slots)
        self.assertEqual(plan.consume_cash, MIN_CONSUME)
        self.assertNotIn("learn_career", plan.slots)

    def test_grind_never_spends_in_the_same_state(self):
        plan = policy_grind(_ready())
        self.assertNotIn("consume", plan.slots)
        self.assertEqual(plan.consume_cash, 0)

    def test_low_energy_and_high_autonomy_do_not_spend(self):
        tired = _ready()
        tired.energy = 20
        self.assertNotIn("consume", policy_steady(tired).slots)
        full = _ready()
        full.autonomy = 80
        self.assertNotIn("consume", policy_steady(full).slots)

    def test_renter_stops_before_owner_when_the_floor_is_already_expensive(self):
        renter = _ready()
        renter.lifestyle = 110
        renter.autonomy = 50
        owner = renter.clone()
        owner.home_value = 900_000
        owner.mortgage = 580_000
        owner.mortgage_payment = 3_797
        owner.business_stage = "running"
        owner.automated = True
        owner.venture = 50
        owner.venture_fresh = 10
        owner.business_book = 160_000
        owner.last_business_net = 1_000
        self.assertNotIn("consume", policy_steady(renter).slots)
        self.assertIn("consume", policy_steady(owner).slots)
        self.assertIn("consume", policy_owner(owner).slots)
        self.assertEqual(policy_owner(owner).consume_cash, MIN_CONSUME)

    def test_learning_still_comes_before_spending(self):
        state = _ready()
        state.career = 30
        state.career_fresh = 1
        plan = policy_steady(state)
        self.assertIn("learn_career", plan.slots)
        self.assertNotIn("consume", plan.slots)

    def test_salary_formula_is_not_a_consume_bonus(self):
        before = salary(60, 4, "full")
        state, _, _ = resolve(_ready(), Plan("full", ["consume"], consume_cash=MIN_CONSUME))
        self.assertEqual(salary(state.career, state.network, "full"), salary(60, 3, "full"))
        self.assertLess(salary(60, 3, "full"), before)
