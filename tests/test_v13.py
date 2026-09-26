"""V13：正的流动涨幅拆一半进现金。当月净资产不因此增加。亏损不拆。"""

from __future__ import annotations

import unittest

from money_sim.constants import GAIN_CASH_DEN, GAIN_CASH_NUM
from money_sim.engine import cash_from_gain, resolve
from money_sim.policies import policy_steady
from money_sim.state import new_game
from tests.test_engine import assert_identity


class SplitTests(unittest.TestCase):
    def test_half_of_a_positive_gain_and_nothing_from_a_loss(self):
        self.assertEqual((GAIN_CASH_NUM, GAIN_CASH_DEN), (1, 2))
        self.assertEqual(cash_from_gain(0), 0)
        self.assertEqual(cash_from_gain(-80_000), 0)
        self.assertEqual(cash_from_gain(100), 50)
        self.assertEqual(cash_from_gain(101), 50)

    def test_opening_month_moves_half_the_liquid_gain_without_printing_net_worth(self):
        state = new_game(1)
        self.assertEqual(state.locked, 0)
        before = state.clone()
        plan = policy_steady(state)
        state, errors, report = resolve(state, plan)
        self.assertEqual(errors, [])
        assert_identity(before, state, report)
        self.assertEqual(report["gain_cash"], max(0, report["invest_return"]) // 2)
        moved = [row for row in report["ledger"] if row["reason"] == "gain_cash"]
        if report["gain_cash"] == 0:
            self.assertEqual(moved, [])
        else:
            self.assertEqual(sum(row["amount"] for row in moved), 0)
            self.assertEqual(sum(row["amount"] for row in moved if row["account"] == "cash"), report["gain_cash"])

    def test_a_down_month_does_not_pay_cash_and_books_still_balance(self):
        found = False
        for seed in range(1, 40):
            state = new_game(seed)
            before = state.clone()
            state, errors, report = resolve(state, policy_steady(before))
            self.assertEqual(errors, [])
            assert_identity(before, state, report)
            if report["invest_return"] < 0:
                self.assertEqual(report["gain_cash"], 0)
                found = True
                break
        self.assertTrue(found)


if __name__ == "__main__":
    unittest.main()
