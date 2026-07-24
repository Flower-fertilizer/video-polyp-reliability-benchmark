from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))

from reliability_metrics import (  # noqa: E402
    audit_mask,
    boundary_iou,
    dice,
    exact_budget_selection,
    group_episodes,
    review_summary,
)


class ReliabilityMetricTests(unittest.TestCase):
    def test_empty_mask_conventions(self) -> None:
        empty = np.zeros((8, 8), dtype=bool)
        nonempty = empty.copy()
        nonempty[2:4, 2:4] = True
        self.assertEqual(dice(empty, empty), 1.0)
        self.assertEqual(boundary_iou(empty, empty), 1.0)
        self.assertEqual(boundary_iou(nonempty, empty), 0.0)

    def test_presence_specific_audit(self) -> None:
        reference = np.zeros((10, 10), dtype=bool)
        reference[2:6, 2:6] = True
        erased = audit_mask(np.zeros_like(reference), reference)
        self.assertEqual(erased["presence_stratum"], "lesion_present")
        self.assertTrue(erased["complete_erasure"])
        self.assertTrue(erased["preservation_failure"])

        false_foreground = np.zeros_like(reference)
        false_foreground[1:3, 1:3] = True
        false_foreground[7, 7] = True
        no_lesion = audit_mask(false_foreground, np.zeros_like(reference))
        self.assertEqual(no_lesion["presence_stratum"], "no_lesion")
        self.assertTrue(no_lesion["false_foreground"])
        self.assertEqual(no_lesion["component_count"], 2)

    def test_exact_budget_and_stable_ties(self) -> None:
        selected = exact_budget_selection(
            [0.8, 0.8, 0.1, 0.9],
            0.50,
            tie_keys=["b", "a", "c", "d"],
        )
        self.assertEqual(selected.tolist(), [False, True, False, True])
        summary = review_summary(
            [True, False, True, True],
            [0.8, 0.8, 0.1, 0.9],
            0.50,
            tie_keys=["b", "a", "c", "d"],
        )
        self.assertEqual(summary["reviewed_frames"], 2)
        self.assertEqual(summary["caught_failures"], 1)
        self.assertEqual(summary["remaining_failures"], 2)

    def test_episode_grouping_and_sequence_boundaries(self) -> None:
        flags = [True, False, True, True, True]
        sequence_ids = ["a", "a", "a", "b", "b"]
        gap_zero = group_episodes(flags, sequence_ids, max_gap=0)
        self.assertEqual(len(gap_zero), 3)
        gap_one = group_episodes(flags, sequence_ids, max_gap=1)
        self.assertEqual(len(gap_one), 2)
        self.assertEqual(gap_one[0].flagged_frames, 2)
        self.assertEqual(gap_one[1].sequence_id, "b")


if __name__ == "__main__":
    unittest.main()
