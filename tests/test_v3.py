"""V3：技能会过时，收缩月的冲击叠在一起，时间自主改合同月的休息。"""

from __future__ import annotations

import unittest

from money_sim.engine import apply_contraction_bundle, resolve
from money_sim.policies import policy_grind, policy_steady
from money_sim.state import Plan, from_save_dict, new_game, to_save_dict


def _ledger_reasons(report: dict) -> set[str]:
    return {row["reason"] for row in report["ledger"]}


class RustTests(unittest.TestCase):
    def test_stale_skill_drops_and_learning_resets_freshness(self):
        stale = new_game(1)
        stale.career = 40
        stale.career_fresh = 0
        stale.month = 10
        after, errors, report = resolve(stale, Plan("full", ["rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(after.career, 39)
        self.assertIn("职业技能过时", " ".join(report["notes"]))

        holding = new_game(1)
        holding.career = 40
        holding.career_fresh = 5
        holding.month = 10
        held, _, held_report = resolve(holding, Plan("full", ["rest"]))
        self.assertEqual(held.career, 40)
        self.assertEqual(held.career_fresh, 4)
        self.assertNotIn("职业技能过时", " ".join(held_report["notes"]))

        studied = new_game(1)
        studied.career = 40
        studied.career_fresh = 0
        studied.month = 10
        learned, _, learned_report = resolve(studied, Plan("full", ["learn_career"]))
        self.assertGreater(learned.career, 40)
        self.assertEqual(learned.career_fresh, 14)
        self.assertNotIn("职业技能过时", " ".join(learned_report["notes"]))

        late = new_game(1)
        late.career = 40
        late.career_fresh = 0
        late.month = 50
        late_learned, _, _ = resolve(late, Plan("full", ["learn_career"]))
        self.assertEqual(late_learned.career_fresh, 7)

    def test_cramming_does_not_outpace_deliberate_study(self):
        cram = new_game(1)
        cram.career = 30
        cram.career_fresh = 2
        after, errors, _ = resolve(cram, Plan("full", ["learn_career"]))
        self.assertEqual(errors, [])
        self.assertEqual(after.career, 31)

        study = new_game(1)
        study.career = 30
        study.career_fresh = 10
        studied, _, _ = resolve(study, Plan("full", ["learn_career"]))
        self.assertGreater(studied.career, 31)

        kept = new_game(1)
        kept.career = 60
        kept.career_fresh = 10
        capped, _, _ = resolve(kept, Plan("full", ["learn_career"]))
        self.assertEqual(capped.career, 61)

    def test_late_rust_is_faster_unless_autonomy_is_high(self):
        low = new_game(2)
        low.career = 40
        low.career_fresh = 0
        low.month = 70
        low.autonomy = 20
        dropped, _, _ = resolve(low, Plan("full", ["rest"]))
        self.assertEqual(dropped.career, 38)

        high = new_game(2)
        high.career = 40
        high.career_fresh = 0
        high.month = 70
        high.autonomy = 80
        spared, _, _ = resolve(high, Plan("full", ["rest"]))
        self.assertEqual(spared.career, 39)

    def test_practice_refreshes_without_raising_the_skill(self):
        state = new_game(3)
        state.venture = 30
        state.venture_fresh = 0
        state.business_stage = "running"
        state.business_book = 20_000
        after, errors, _ = resolve(state, Plan("free", ["venture", "rest", "rest", "rest"]))
        self.assertEqual(errors, [])
        self.assertEqual(after.venture, 30)
        self.assertEqual(after.venture_fresh, 8)


class ContractionTests(unittest.TestCase):
    def test_bundle_hits_locked_index_and_the_shop(self):
        state = new_game(1)
        state.portfolio = 200_000
        state.locked = 200_000
        state.lock_left = 5
        state.business_stage = "running"
        state.business_book = 50_000
        state.stress = 80
        state.cash = 180_000
        ledger: list[dict] = []
        notes: list[str] = []
        apply_contraction_bundle(state, "none", ledger, notes)
        self.assertEqual(state.portfolio, 194_000)
        self.assertEqual(state.locked, 194_000)
        self.assertEqual(state.business_book, 47_500)
        self.assertEqual(state.cash, 172_000)
        self.assertIn("contraction_index", {row["reason"] for row in ledger})

        spared = new_game(1)
        spared.portfolio = 200_000
        spared.business_stage = "running"
        spared.business_book = 50_000
        spared.stress = 80
        spared.cash = 180_000
        again: list[dict] = []
        apply_contraction_bundle(spared, "setback", again, [])
        self.assertEqual(spared.business_book, 50_000)
        self.assertNotIn("contraction_book", {row["reason"] for row in again})

    def test_contract_blocks_layoff_but_not_the_stacked_shock(self):
        shocks = 0
        for seed in range(80):
            state = new_game(seed)
            state.regime = "bear"
            state.contract_left = 6
            state.stress = 80
            state.business_stage = "running"
            state.business_book = 40_000
            state.locked = 100_000
            state.lock_left = 8
            _, errors, report = resolve(state, Plan("full", ["rest"]))
            self.assertEqual(errors, [])
            self.assertNotEqual(report["event"], "layoff")
            if report["shock"] == "contraction":
                shocks += 1
                self.assertIn("contraction_index", _ledger_reasons(report))
                self.assertNotIn("layoff_clawback", _ledger_reasons(report))
        self.assertGreater(shocks, 0)


class AutonomyTests(unittest.TestCase):
    def test_high_autonomy_rests_better_inside_a_contract(self):
        low = new_game(4)
        low.contract_left = 4
        low.autonomy = 20
        low.energy = 50
        high = new_game(4)
        high.contract_left = 4
        high.autonomy = 80
        high.energy = 50
        tired, _, _ = resolve(low, Plan("full", ["rest"]))
        fresh, _, _ = resolve(high, Plan("full", ["rest"]))
        self.assertGreater(fresh.energy, tired.energy)


class StageTests(unittest.TestCase):
    def test_steady_relearns_only_after_the_skill_goes_stale(self):
        early = new_game(1)
        early.month = 20
        early.career = 80
        early.career_fresh = 10
        early.energy = 80
        early.stress = 10
        early.autonomy = 50
        self.assertNotIn("learn_career", policy_steady(early).slots)

        late = new_game(1)
        late.month = 70
        late.career = 80
        late.career_fresh = 0
        late.energy = 80
        late.stress = 10
        late.autonomy = 50
        self.assertIn("learn_career", policy_steady(late).slots)
        self.assertNotIn("learn_career", policy_grind(late).slots)

    def test_old_save_without_freshness_still_loads(self):
        data = to_save_dict(new_game(1))
        del data["career_fresh"]
        del data["venture_fresh"]
        del data["invest_fresh"]
        loaded = from_save_dict(data)
        self.assertEqual(loaded.career_fresh, 18)
        self.assertEqual(loaded.venture_fresh, 8)
        self.assertEqual(loaded.invest_fresh, 12)


if __name__ == "__main__":
    unittest.main()
