"""V5：外部报价是有期限的工资，接手那个月没有工资，也不是加薪。"""

from __future__ import annotations

import unittest

from money_sim.economy import outside_offer, salary
from money_sim.engine import resolve, validate
from money_sim.policies import policy_grind, policy_steady
from money_sim.state import Plan, new_game
from tests.test_engine import assert_identity


class OfferTests(unittest.TestCase):
    def test_accepting_pays_nothing_this_month_and_the_offer_next_month(self):
        state = new_game(1)
        state.pending_offer = 20_000
        before = state.clone()
        jumped, errors, report = resolve(state, Plan("full", ["rest"], accept_job=True))
        self.assertEqual(errors, [])
        assert_identity(before, jumped, report)
        self.assertEqual(report["salary"], 0)
        self.assertEqual(jumped.career, before.career)
        self.assertEqual(jumped.career_fresh, before.career_fresh)
        self.assertEqual(jumped.offer_pay, 20_000)
        self.assertEqual(jumped.offer_left, 12)
        paid_before = jumped.clone()
        paid, errors, paid_report = resolve(jumped, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        assert_identity(paid_before, paid, paid_report)
        self.assertEqual(paid_report["salary"], 20_000)
        self.assertEqual(paid.offer_left, 11)
        self.assertEqual(paid.career, before.career)

    def test_stale_skill_is_refreshed_without_a_raise(self):
        state = new_game(1)
        state.career = 30
        state.career_fresh = 0
        state.pending_offer = 12_000
        out, errors, _ = resolve(state, Plan("full", ["rest"], accept_job=True))
        self.assertEqual(errors, [])
        self.assertEqual(out.career, 30)
        self.assertEqual(out.career_fresh, 8)

    def test_cannot_take_an_offer_that_is_not_there_or_breaks_a_contract_quietly(self):
        state = new_game(1)
        self.assertTrue(validate(state, Plan("full", ["rest"], accept_job=True)))
        state.pending_offer = 22_000
        state.contract_left = 5
        self.assertTrue(validate(state, Plan("full", ["rest"], accept_job=True)))
        self.assertEqual(validate(state, Plan("full", ["rest"], accept_job=True, break_contract=True)), [])

    def test_offer_size_follows_freshness(self):
        market = salary(40, 4, "full")
        self.assertGreater(outside_offer(40, 4, 14), market)
        self.assertLess(outside_offer(40, 4, 0), market)

    def test_grind_ignores_a_better_offer_and_steady_can_take_it(self):
        state = new_game(1)
        state.pending_offer = outside_offer(state.career, state.network, state.career_fresh)
        self.assertFalse(policy_grind(state).accept_job)
        self.assertTrue(policy_steady(state).accept_job)
        state.cash = 1_000
        state.home_value = 900_000
        state.mortgage_payment = 8_000
        self.assertFalse(policy_steady(state).accept_job)

    def test_wage_returns_to_the_skill_formula_after_the_term(self):
        state = new_game(2)
        state.pending_offer = 19_000
        state, errors, _ = resolve(state, Plan("full", ["rest"], accept_job=True))
        self.assertEqual(errors, [])
        for _ in range(12):
            state, errors, report = resolve(state, Plan("full", ["rest"]))
            self.assertEqual(errors, [])
            self.assertEqual(report["salary"], 19_000)
        self.assertEqual(state.offer_left, 0)
        market = salary(state.career, state.network, "full")
        _, errors, report = resolve(state, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], market)


if __name__ == "__main__":
    unittest.main()
