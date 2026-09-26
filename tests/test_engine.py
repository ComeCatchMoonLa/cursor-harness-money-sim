"""核心规则：时间、收支、胜负、机会成本和记账恒等式。"""

from __future__ import annotations

import json
import unittest

from money_sim.constants import DEBT_CAP, LOG_FIELDS
from money_sim.economy import business_gross, exit_pct, learn_gain, salary
from money_sim.engine import resolve, validate
from money_sim.policies import POLICIES, policy_yolo
from money_sim.state import Plan, from_save_dict, new_game, net_worth, to_save_dict


def rest_plan() -> Plan:
    return Plan("free", ["rest", "rest", "rest", "rest"])


def assert_identity(before, after, report) -> None:
    sums = {"cash": 0, "portfolio": 0, "book": 0, "debt": 0}
    for row in report["ledger"]:
        sums[row["account"]] += row["amount"]
    if after.cash - before.cash != sums["cash"]:
        raise AssertionError((after.cash, before.cash, sums))
    if after.portfolio - before.portfolio != sums["portfolio"]:
        raise AssertionError((after.portfolio, before.portfolio, sums))
    if after.business_book - before.business_book != sums["book"]:
        raise AssertionError((after.business_book, before.business_book, sums))
    if after.debt - before.debt != sums["debt"]:
        raise AssertionError((after.debt, before.debt, sums))
    delta = sums["cash"] + sums["portfolio"] + sums["book"] - sums["debt"]
    if net_worth(after) - net_worth(before) != delta:
        raise AssertionError((net_worth(after), net_worth(before), delta))
    for key in LOG_FIELDS:
        if key not in report:
            raise AssertionError(key)


class EconomyTests(unittest.TestCase):
    def test_part_time_pays_less_and_salary_is_bounded(self):
        full = salary(100, 100, "full")
        part = salary(100, 100, "part")
        self.assertGreater(full, part)
        self.assertLess(full, 80_000)
        self.assertEqual(salary(24, 4, "free"), 0)

    def test_learning_diminishes(self):
        self.assertGreater(learn_gain(10), learn_gain(90))

    def test_shop_scale_is_not_a_trap_or_a_press(self):
        from money_sim.economy import business_opex

        tended = business_gross(80_000, 50, 100, 1, False, 40) - business_opex(80_000, False)
        neglect = business_gross(80_000, 50, 100, 0, False, 40) - business_opex(80_000, False)
        hired_small = business_gross(30_000, 20, 100, 0, True, 40) - business_opex(30_000, True)
        hired_big = business_gross(300_000, 70, 100, 0, True, 70) - business_opex(300_000, True)
        overbuilt = business_gross(2_000_000, 70, 100, 0, True, 70) - business_opex(2_000_000, True)
        self.assertGreater(tended, 0)
        self.assertLess(neglect, 0)
        self.assertLess(hired_small, 0)
        self.assertGreater(hired_big, 0)
        self.assertLess(overbuilt, hired_big)

    def test_business_marginal_product_falls(self):
        first = business_gross(20_000, 40, 100, 1, False, 40)
        second = business_gross(40_000, 40, 100, 1, False, 40)
        third = business_gross(80_000, 40, 100, 1, False, 40)
        self.assertGreater(second, first)
        self.assertGreater(third, second)
        self.assertLess((second - first) / 20_000, (first or 1))
        self.assertLess((third - second) / 40_000, (second - first) / 20_000)

    def test_exit_never_pays_full_book(self):
        self.assertLess(exit_pct("running", 100, 0, False), 100)
        self.assertLess(exit_pct("building", 0, 0, False), 100)
        self.assertGreater(exit_pct("running", 100, 88, True), exit_pct("running", 100, 0, False))


class EngineTests(unittest.TestCase):
    def test_opening_net_worth(self):
        state = new_game(1)
        self.assertEqual(net_worth(state), 720_000)
        self.assertEqual(state.month, 1)
        self.assertEqual(state.status, "playing")

    def test_month_advances_and_ledger_balances(self):
        state = new_game(7)
        plan = Plan("full", ["rest"])
        after, errors, report = resolve(state, plan)
        self.assertEqual(errors, [])
        self.assertEqual(after.month, 2)
        self.assertGreater(report["salary"], 0)
        self.assertGreater(report["living"], 0)
        self.assertEqual(report["type"], "month_end")
        assert_identity(state, after, report)
        self.assertLess(after.energy, 100)

    def test_same_seed_replays(self):
        def once():
            state = new_game(99)
            state, _, report = resolve(state, Plan("full", ["learn_career"]))
            return report["net_worth"], report["event"], state.career

        self.assertEqual(once(), once())

    def test_learning_does_not_raise_this_months_salary(self):
        state = new_game(3)
        paid = salary(state.career, state.network, "full")
        after, errors, report = resolve(state, Plan("full", ["learn_career"]))
        self.assertEqual(errors, [])
        self.assertEqual(report["salary"], paid)
        self.assertGreater(after.career, state.career)

    def test_full_time_rejected_when_exhausted(self):
        state = new_game(1)
        state.energy = 5
        after, errors, report = resolve(state, Plan("full", ["rest"]))
        self.assertIsNone(report)
        self.assertTrue(any("全职" in item for item in errors))
        self.assertIs(after, state)
        self.assertEqual(state.energy, 5)
        self.assertEqual(state.month, 1)

    def test_two_actions_have_different_costs(self):
        learn = new_game(4)
        rested = new_game(4)
        learn_after, errors, learn_report = resolve(learn, Plan("full", ["learn_career"]))
        rest_after, rest_errors, rest_report = resolve(rested, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(rest_errors, [])
        self.assertGreater(learn_report["salary"], 0)
        tuition = [row for row in learn_report["ledger"] if row["reason"] == "tuition"]
        self.assertEqual(tuition[0]["amount"], -1_000)
        self.assertFalse(any(row["reason"] == "tuition" for row in rest_report["ledger"]))
        self.assertGreater(rest_after.energy, learn_after.energy)

    def test_rest_without_assets_does_not_print_money(self):
        state = new_game(8)
        state.portfolio = 0
        start = net_worth(state)
        for _ in range(8):
            state, errors, report = resolve(state, rest_plan())
            self.assertEqual(errors, [])
            self.assertEqual(report["salary"], 0)
        self.assertLess(net_worth(state), start)
        self.assertEqual(state.portfolio, 0)

    def test_business_transfer_and_exit_do_not_raise_net_worth_by_themselves(self):
        state = new_game(2)
        state.portfolio = 0
        state.business_stage = "building"
        state.business_progress = 1
        state.business_book = 7_000
        before = net_worth(state)
        after, errors, report = resolve(state, Plan("free", ["rest", "rest", "rest", "rest"], to_business=10_000))
        self.assertEqual(errors, [])
        inject = [row for row in report["ledger"] if row["reason"] == "inject"]
        self.assertEqual(sum(row["amount"] for row in inject), 0)
        moved = sum(row["amount"] for row in inject if row["account"] == "book")
        self.assertEqual(moved, 10_000)
        self.assertLess(net_worth(after), before)

        running = new_game(2)
        running.portfolio = 0
        running.business_stage = "running"
        running.business_book = 50_000
        running.last_business_net = 1_000
        worth = net_worth(running)
        exited, exit_errors, _exit_report = resolve(running, Plan("free", ["rest"] * 4, exit_business=True))
        self.assertEqual(exit_errors, [])
        self.assertEqual(exited.business_book, 0)
        self.assertLess(net_worth(exited), worth)

    def test_win_and_bankruptcy_and_shortfall(self):
        rich = new_game(1)
        rich.portfolio = 3_000_000
        won, errors, report = resolve(rich, rest_plan())
        self.assertEqual(errors, [])
        self.assertEqual(won.status, "won")
        self.assertEqual(report["type"], "win")

        broke = new_game(1)
        broke.cash = 0
        broke.portfolio = 0
        broke.debt = DEBT_CAP
        failed, fail_errors, fail_report = resolve(broke, rest_plan())
        self.assertEqual(fail_errors, [])
        self.assertEqual(failed.status, "bankrupt")
        self.assertEqual(fail_report["type"], "fail")
        self.assertEqual(fail_report["fail_reason"], "bankrupt")

        last = new_game(1)
        last.month = 108
        last.portfolio = 0
        last.cash = 80_000
        ended, end_errors, end_report = resolve(last, rest_plan())
        self.assertEqual(end_errors, [])
        self.assertEqual(ended.status, "shortfall")
        self.assertEqual(end_report["type"], "shortfall")

    def test_overdraft_is_allowed_and_counts_toward_burnout(self):
        state = new_game(1)
        state.energy = 10
        after, errors, report = resolve(state, Plan("free", ["venture", "venture", "venture", "venture"]))
        self.assertEqual(errors, [])
        self.assertEqual(after.energy, 0)
        self.assertGreaterEqual(after.burnout_streak, 1)
        self.assertTrue(any("透支" in note for note in report["notes"]))

    def test_game_ends_by_month_108(self):
        state = new_game(11)
        state.portfolio = 0
        guard = 0
        while state.status == "playing":
            state, errors, _report = resolve(state, rest_plan())
            self.assertEqual(errors, [])
            guard += 1
            self.assertLess(guard, 120)
        self.assertNotEqual(state.status, "won")
        self.assertIn(state.status, ("bankrupt", "burnout", "shortfall"))

    def test_save_roundtrip_continues_same_path(self):
        left = new_game(42)
        right = from_save_dict(json.loads(json.dumps(to_save_dict(left))))
        plan = Plan("part", ["learn_venture", "rest"])
        left, _, left_report = resolve(left, plan)
        right, _, right_report = resolve(right, plan)
        self.assertEqual(left_report["net_worth"], right_report["net_worth"])
        self.assertEqual(left_report["event"], right_report["event"])
        self.assertEqual(to_save_dict(left)["rng_state"], to_save_dict(right)["rng_state"])

    def test_policies_survive_and_yolo_is_extreme(self):
        for _name, policy in POLICIES:
            state = new_game(5)
            for _ in range(18):
                if state.status != "playing":
                    break
                plan = policy(state)
                self.assertEqual(validate(state, plan), [])
                previous = state
                state, errors, report = resolve(state, plan)
                self.assertEqual(errors, [])
                assert_identity(previous, state, report)
        opening = new_game(5)
        yolo = policy_yolo(opening)
        self.assertEqual(yolo.employment, "free")
        self.assertIn("venture", yolo.slots)
        self.assertNotIn("learn_career", yolo.slots)

    def test_finished_game_rejects_another_month(self):
        state = new_game(1)
        state.portfolio = 3_000_000
        state, _, _ = resolve(state, rest_plan())
        self.assertEqual(state.status, "won")
        again, errors, report = resolve(state, rest_plan())
        self.assertIsNone(report)
        self.assertTrue(errors)
        self.assertEqual(again.status, "won")


if __name__ == "__main__":
    unittest.main()
