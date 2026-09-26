"""V4：自住房是月供加一块不好变现的权益，不是第二条指数。"""

from __future__ import annotations

import unittest

from money_sim.economy import living_cost
from money_sim.engine import preview, quote, resolve, validate
from money_sim.policies import policy_grind, policy_nest
from money_sim.state import Plan, net_worth, new_game, realizable_net


def _reasons(report: dict) -> set[str]:
    return {row["reason"] for row in report["ledger"]}


class HousingTests(unittest.TestCase):
    def test_buying_drops_realizable_and_locked_index_cannot_fund_it(self):
        state = new_game(1)
        before = realizable_net(state)
        bought, errors, report = resolve(state, Plan("full", ["rest"], from_index=360_000, buy_home=True))
        self.assertEqual(errors, [])
        self.assertGreater(bought.home_value, 0)
        self.assertGreater(bought.mortgage, 0)
        self.assertLess(realizable_net(bought), before)
        self.assertLess(net_worth(bought) - bought.home_value + bought.mortgage, net_worth(state))
        self.assertTrue(_reasons(report) & {"home_down", "home_loan", "mortgage"})

        locked = new_game(1)
        locked.locked = locked.portfolio
        locked.lock_left = 6
        self.assertTrue(validate(locked, Plan("full", ["rest"], buy_home=True)))

    def test_owning_cuts_rent_and_charges_the_mortgage(self):
        renter, _, rented = resolve(new_game(2), Plan("full", ["rest"]))
        owner = new_game(2)
        owner.home_value = 900_000
        owner.mortgage = 500_000
        owner.mortgage_payment = 3_000
        lived, errors, owned = resolve(owner, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertLess(owned["living"], rented["living"])
        self.assertIn("mortgage", _reasons(owned))
        self.assertGreater(lived.home_value, 0)
        self.assertLess(lived.mortgage, 500_000)

    def test_voluntary_sale_clears_the_loan_and_keeps_less_than_the_price(self):
        state = new_game(3)
        state.home_value = 200_000
        state.mortgage = 80_000
        state.mortgage_payment = 2_000
        state.cash = 100_000
        sold, errors, report = resolve(state, Plan("free", ["rest"] * 4, sell_home=True))
        self.assertEqual(errors, [])
        self.assertEqual(sold.home_value, 0)
        self.assertEqual(sold.mortgage, 0)
        sale = [row for row in report["ledger"] if row["reason"] == "sell_home" and row["account"] == "cash"]
        cash_in = sum(row["amount"] for row in sale)
        self.assertLess(cash_in, 200_000)
        self.assertGreater(cash_in, 0)

    def test_distress_sells_the_house_when_index_cannot(self):
        state = new_game(4)
        state.cash = 0
        state.portfolio = 0
        state.home_value = 400_000
        state.mortgage = 100_000
        state.mortgage_payment = 2_000
        out, errors, report = resolve(state, Plan("free", ["rest"] * 4))
        self.assertEqual(errors, [])
        self.assertEqual(out.home_value, 0)
        self.assertEqual(out.mortgage, 0)
        self.assertIn("distress_home", _reasons(report))

    def test_preview_living_is_what_owning_actually_charges(self):
        state = new_game(1)
        plan = Plan("full", ["rest"], from_index=360_000, buy_home=True)
        quoted = quote(state, plan)
        _, errors, report = resolve(state.clone(), plan)
        self.assertEqual(errors, [])
        self.assertEqual(quoted["living"], quoted["housing_living"])
        self.assertEqual(quoted["living"], report["living"])
        self.assertLess(quoted["living"], living_cost(state.lifestyle, state.price_index))

        owned = new_game(1)
        owned.cash = 10_000
        owned.home_value = 900_000
        owned.mortgage = 500_000
        owned.mortgage_payment = 20_000
        shown = preview(owned, Plan("full", ["rest"]))
        self.assertEqual(shown["quote"]["living"], shown["quote"]["housing_living"])
        self.assertTrue(any("月供" in item for item in shown["warnings"]))

    def test_grind_keeps_renting_and_nest_can_buy(self):
        state = new_game(1)
        self.assertFalse(policy_grind(state).buy_home)
        bought = False
        for _ in range(8):
            if state.home_value or state.status != "playing":
                break
            plan = policy_nest(state)
            bought = bought or plan.buy_home
            state, errors, _ = resolve(state, plan)
            self.assertEqual(errors, [])
        self.assertTrue(bought)
        self.assertGreater(state.home_value, 0)


if __name__ == "__main__":
    unittest.main()
