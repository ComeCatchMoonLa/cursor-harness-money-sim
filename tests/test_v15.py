"""V15：开局改成景气，五条的排序没有翻。旋钮不留在界面上。"""

from __future__ import annotations

import unittest
from itertools import combinations
from pathlib import Path

from money_sim.constants import START_CASH, START_PORTFOLIO, WIN_NET
from money_sim.state import new_game


CHOP_RANK = ["steady", "coast", "owner", "grind", "yolo"]
BULL_RANK = ["steady", "coast", "owner", "grind", "yolo"]


def flipped_pairs(before: list[str], after: list[str]) -> list[tuple[str, str]]:
    pairs = []
    for left, right in combinations(before, 2):
        if before.index(left) < before.index(right) and after.index(left) > after.index(right):
            pairs.append((left, right))
    return pairs


class OpeningKnobTests(unittest.TestCase):
    def test_recorded_ranks_do_not_flip_so_the_knob_stays_off_the_page(self):
        self.assertEqual(flipped_pairs(CHOP_RANK, BULL_RANK), [])
        page = Path("web/index.html").read_text(encoding="utf-8")
        self.assertNotIn("开局景气", page)
        state = new_game(1)
        self.assertEqual(state.regime, "chop")
        self.assertEqual(state.cash, START_CASH)
        self.assertEqual(state.portfolio, START_PORTFOLIO)
        self.assertEqual(WIN_NET, 1_500_000)

    def test_a_reversed_pair_would_be_named(self):
        swapped = ["coast", "steady", "owner", "grind", "yolo"]
        self.assertEqual(flipped_pairs(CHOP_RANK, swapped), [("steady", "coast")])


if __name__ == "__main__":
    unittest.main()
