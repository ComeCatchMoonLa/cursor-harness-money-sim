"""批量模拟能跑完，并给出验收要求的三项指标。"""

import unittest

from money_sim.batch import run_batch


class BatchSmokeTest(unittest.TestCase):
    def test_three_metrics_and_an_extreme(self):
        report = run_batch(8, 11)
        self.assertGreaterEqual(len(report["strategies"]), 3)
        names = [row["name"] for row in report["strategies"]]
        self.assertIn("yolo", names)
        for row in report["strategies"]:
            self.assertEqual(row["games"], 8)
            self.assertGreaterEqual(row["win_rate"], 0)
            self.assertLessEqual(row["win_rate"], 1)
            self.assertGreaterEqual(row["hard_fail_rate"], 0)
            self.assertLessEqual(row["hard_fail_rate"], 1)
            self.assertIsInstance(row["mean_net"], float)
            self.assertEqual(row["suspect_wealth_games"], 0)


if __name__ == "__main__":
    unittest.main()
