"""钉住 FEATURES 底线：不许删条目，也不许改写既有 steps 来放宽标准。"""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "docs" / "dev" / "FEATURES.json"
FLOOR = ROOT / "docs" / "dev" / "FEATURES.floor.json"
REQUIRED = ("id", "category", "description", "steps", "passes")


class FeaturesFloorTest(unittest.TestCase):
    def test_list_keeps_floor_steps(self):
        features = json.loads(FEATURES.read_text(encoding="utf-8"))
        floor = json.loads(FLOOR.read_text(encoding="utf-8"))
        self.assertIsInstance(features, list)
        self.assertGreater(len(floor), 0)

        ids = []
        by_id = {}
        for item in features:
            for key in REQUIRED:
                self.assertIn(key, item, item)
            self.assertIsInstance(item["id"], str)
            self.assertTrue(item["id"].strip())
            self.assertIsInstance(item["category"], str)
            self.assertTrue(item["category"].strip())
            self.assertIsInstance(item["description"], str)
            self.assertTrue(item["description"].strip())
            self.assertIsInstance(item["steps"], list)
            self.assertGreaterEqual(len(item["steps"]), 1)
            self.assertTrue(all(isinstance(step, str) and step.strip() for step in item["steps"]))
            self.assertIsInstance(item["passes"], bool)
            ids.append(item["id"])
            by_id[item["id"]] = item
        self.assertEqual(len(ids), len(set(ids)))

        for feature_id, locked in floor.items():
            self.assertIn(feature_id, by_id, feature_id)
            current = by_id[feature_id]
            self.assertEqual(current["category"], locked["category"], feature_id)
            for step in locked["steps"]:
                self.assertIn(step, current["steps"], feature_id)


if __name__ == "__main__":
    unittest.main()
