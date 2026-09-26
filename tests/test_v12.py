"""V12：if-then 是数据。非法就业跳过。适应度不是最高达成率。

预算在跑搜索之前写死。看到结果不改这些数，也不改这一种子抽到的 24 条。
"""

from __future__ import annotations

import hashlib
import random
import unittest

from money_sim.engine import ease_of, validate
from money_sim.policies import policy_steady
from money_sim.rule_search import (
    CONFIRM_GAMES,
    GAME_SEED,
    HOLDOUT_GAMES,
    HOLDOUT_SEED,
    N_CANDIDATES,
    RULES_PER,
    SCREEN_GAMES,
    SEARCH_SEED,
    describe_rule,
    make_policy,
    matches,
    sample_rules,
    separates,
)
from money_sim.state import new_game


CATALOG_SHA256 = "e141d2ab953f1398f5a080b09783aadc0426a855bcc7fd4ff285225c0593177d"


def _any(**overrides) -> dict:
    rule = {
        "worth": None,
        "condition": None,
        "regime": None,
        "contract": None,
        "position": "any",
        "automated": None,
        "employment": "full",
    }
    rule.update(overrides)
    return rule


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


def _row(**overrides) -> dict:
    base = {
        "name": "candidate",
        "win_rate": 0.55,
        "hard_fail_rate": 0.0,
        "mean_intensity": 0.84,
        "mean_autonomy": 70.0,
        "median_win_month": 80,
        "mean_net": 1_400_000,
        "suspect_wealth_games": 0,
        "max_jump": 0.2,
    }
    base.update(overrides)
    return base


class BudgetTests(unittest.TestCase):
    def test_search_budget_and_catalog_stay_the_ones_drawn_before_the_run(self):
        self.assertEqual(
            (SEARCH_SEED, N_CANDIDATES, RULES_PER, SCREEN_GAMES, CONFIRM_GAMES, HOLDOUT_GAMES, HOLDOUT_SEED, GAME_SEED),
            (11, 24, 2, 60, 200, 1000, 10001, 1),
        )
        rng = random.Random(SEARCH_SEED)
        catalog = [sample_rules(rng) for _ in range(N_CANDIDATES)]
        digest = hashlib.sha256(repr(catalog).encode()).hexdigest()
        self.assertEqual(digest, CATALOG_SHA256)
        self.assertEqual(len(catalog[0]), 2)


class InterpreterTests(unittest.TestCase):
    def test_covered_month_can_drop_wages(self):
        state = _ahead()
        self.assertEqual(ease_of(state)["covered"], True)
        policy = make_policy((_any(position="covered", employment="free"),))
        plan = policy(state)
        self.assertEqual(validate(state, plan), [])
        self.assertEqual(plan.employment, "free")
        self.assertEqual(plan.sign_months, 0)
        self.assertFalse(plan.accept_job)
        self.assertEqual(policy.fires[0], 1)

    def test_a_rule_that_does_not_match_stays_on_steady(self):
        state = new_game(1)
        self.assertFalse(matches(state, _any(worth=1_400_000, employment="free")))
        policy = make_policy((_any(worth=1_400_000, employment="free"),))
        plan = policy(state)
        steady = policy_steady(state)
        self.assertEqual(plan.employment, steady.employment)
        self.assertEqual(plan.slots, steady.slots)
        self.assertEqual(policy.fires[-1], 1)
        self.assertEqual(policy.fires[0], 0)

    def test_illegal_light_falls_through_to_the_next_rule(self):
        state = new_game(1)
        self.assertFalse(ease_of(state)["open"])
        policy = make_policy((_any(employment="light"), _any(employment="free")))
        plan = policy(state)
        self.assertEqual(validate(state, plan), [])
        self.assertEqual(plan.employment, "free")
        self.assertEqual(policy.fires[0], 0)
        self.assertEqual(policy.fires[1], 1)

    def test_illegal_light_with_nothing_after_it_stays_on_steady(self):
        state = new_game(1)
        policy = make_policy((_any(employment="light"),))
        plan = policy(state)
        self.assertEqual(plan.employment, policy_steady(state).employment)
        self.assertEqual(policy.fires[-1], 1)

    def test_condition_is_a_ceiling_and_worth_is_a_floor(self):
        state = _ahead()
        state.condition = 50
        self.assertFalse(matches(state, _any(condition=40)))
        self.assertTrue(matches(state, _any(condition=58)))
        state.portfolio = 0
        state.cash = 800_000
        self.assertFalse(matches(state, _any(worth=900_000)))
        self.assertTrue(matches(state, _any(worth=None)))

    def test_trigger_text_names_the_condition(self):
        text = describe_rule(_any(position="covered", employment="free"), 0)
        self.assertIn("少工作已经盖住", text)
        self.assertIn("不拿固定工资", text)
        self.assertNotIn("多数月份", text)
        blank = describe_rule(_any(), 1)
        self.assertIn("任何月份", blank)
        self.assertIn("全职", blank)


class FitnessTests(unittest.TestCase):
    def test_a_higher_win_rate_alone_does_not_enter(self):
        kept = [_row(name="steady")]
        richer = _row(win_rate=0.90, mean_net=3_000_000)
        self.assertFalse(separates(richer, kept))

    def test_one_axis_does_not_enter_and_a_jump_past_55_percent_does_not(self):
        kept = [_row(name="steady")]
        one = _row(win_rate=0.70)
        self.assertFalse(separates(one, kept))
        two = _row(win_rate=0.70, mean_autonomy=80)
        self.assertTrue(separates(two, kept))
        hole = _row(win_rate=0.70, mean_autonomy=80, max_jump=0.56)
        self.assertFalse(separates(hole, kept))

    def test_must_separate_from_every_kept_route(self):
        steady = _row(name="steady")
        coast = _row(name="coast", win_rate=0.70, mean_autonomy=80)
        candidate = _row(win_rate=0.70, mean_autonomy=80)
        self.assertTrue(separates(candidate, [steady]))
        self.assertFalse(separates(candidate, [steady, coast]))


if __name__ == "__main__":
    unittest.main()
