"""V2：任期、封闭仓、试营业，胜利看可兑现而不是账面。"""

from __future__ import annotations

import unittest

from money_sim.engine import resolve, validate
from money_sim.state import Plan, new_game, net_worth, realizable_net


def rest(employment: str = "free") -> Plan:
    slots = {"full": ["rest"], "part": ["rest", "rest"], "free": ["rest"] * 4}[employment]
    return Plan(employment, slots)


class ContractTests(unittest.TestCase):
    def test_signing_locks_employment_and_leave_does_not_softlock(self):
        state = new_game(1)
        signed, errors, report = resolve(state, Plan("full", ["rest"], sign_months=6))
        self.assertEqual(errors, [])
        self.assertEqual(signed.contract_left, 5)
        self.assertGreater(report["salary"], 0)
        self.assertTrue(validate(signed, rest("free")))
        self.assertEqual(validate(signed, rest("full")), [])

        signed.energy = 8
        left, leave_errors, leave_report = resolve(signed, rest("free"))
        self.assertEqual(leave_errors, [])
        self.assertEqual(leave_report["salary"], 0)
        self.assertEqual(left.contract_left, 4)
        self.assertIn("病假", " ".join(leave_report["notes"]))

    def test_contract_rest_recovers_less_than_a_free_month(self):
        open_job, _, _ = resolve(new_game(4), Plan("full", ["rest"]))
        covered = new_game(4)
        covered.contract_left = 4
        bound, _, _ = resolve(covered, Plan("full", ["rest"]))
        self.assertGreater(open_job.energy, bound.energy)

    def test_contract_blocks_layoff(self):
        protected = 0
        exposed = 0
        for seed in range(40):
            covered = new_game(seed)
            covered.contract_left = 6
            covered.stress = 90
            covered.regime = "bear"
            _, _, covered_report = resolve(covered, Plan("full", ["rest"]))
            protected += covered_report["event"] == "layoff"
            open_job = new_game(seed)
            open_job.stress = 90
            open_job.regime = "bear"
            _, _, open_report = resolve(open_job, Plan("full", ["rest"]))
            exposed += open_report["event"] == "layoff"
        self.assertEqual(protected, 0)
        self.assertGreater(exposed, 0)

    def test_breach_costs_money(self):
        state = new_game(1)
        signed, _, _ = resolve(state, Plan("full", ["rest"], sign_months=12))
        before = net_worth(signed)
        out, errors, report = resolve(signed, Plan("free", ["rest"] * 4, break_contract=True))
        self.assertEqual(errors, [])
        self.assertEqual(out.contract_left, 0)
        self.assertLess(net_worth(out), before)
        self.assertTrue(any(row["reason"] == "breach" for row in report["ledger"]))


class LockTests(unittest.TestCase):
    def test_locked_index_cannot_be_sold_or_raided(self):
        state = new_game(2)
        locked, errors, _ = resolve(state, Plan("full", ["rest"], lock_amount=200_000))
        self.assertEqual(errors, [])
        self.assertGreater(locked.locked, 0)
        self.assertEqual(locked.lock_left, 12)
        self.assertTrue(validate(locked, Plan("full", ["rest"], from_index=locked.portfolio)))

        broke = new_game(2)
        broke.cash = 0
        broke.portfolio = 80_000
        broke.locked = 80_000
        broke.lock_left = 6
        after, fail_errors, report = resolve(broke, rest("free"))
        self.assertEqual(fail_errors, [])
        self.assertGreater(after.debt, 0)
        self.assertFalse(any(row["reason"] == "emergency_sell" for row in report["ledger"]))
        self.assertGreater(after.locked, 0)


class ShopTests(unittest.TestCase):
    def test_launch_enters_trial_and_paper_book_does_not_win(self):
        state = new_game(3)
        state.business_stage = "building"
        state.business_progress = 2
        state.business_book = 14_000
        launched, errors, _ = resolve(state, Plan("full", ["venture"]))
        self.assertEqual(errors, [])
        self.assertEqual(launched.business_stage, "trial")
        self.assertTrue(validate(launched, Plan("full", ["rest"], automate=True)))

        paper = new_game(3)
        paper.cash = 50_000
        paper.portfolio = 0
        paper.business_stage = "running"
        paper.business_book = 2_000_000
        paper.last_business_net = 1_000
        self.assertGreaterEqual(net_worth(paper), 1_500_000)
        self.assertLess(realizable_net(paper), 1_500_000)
        after, paper_errors, report = resolve(paper, rest("free"))
        self.assertEqual(paper_errors, [])
        self.assertNotEqual(after.status, "won")
        self.assertLess(report["realizable"], 1_500_000)


if __name__ == "__main__":
    unittest.main()
