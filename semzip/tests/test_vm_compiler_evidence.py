import unittest

from semzip.vm_compiler_evidence import RelationEvidence, resolve_relation_evidence
from semzip.vm_relations import DEFAULT_RELATION_REGISTRY


class CompilerEvidenceTests(unittest.TestCase):
    def signature(self):
        return DEFAULT_RELATION_REGISTRY.signature()

    def test_high_confidence_single_candidate_becomes_patch_prediction(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (RelationEvidence(0, 1, 0, 2, 0.95),),
        )
        self.assertTrue(resolution.executable)
        prediction = resolution.patch_prediction()
        self.assertIsNotNone(prediction)
        self.assertEqual(prediction.cells[0].destination, 2)

    def test_low_confidence_candidate_is_withheld(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (RelationEvidence(0, 1, 0, 2, 0.55),),
            min_confidence=0.80,
        )
        self.assertFalse(resolution.executable)
        self.assertEqual(len(resolution.low_confidence), 1)
        self.assertIsNone(resolution.patch_prediction())

    def test_near_tie_remains_ambiguous(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (
                RelationEvidence(0, 1, 0, 2, 0.91),
                RelationEvidence(0, 1, 0, 3, 0.87),
            ),
            min_margin=0.10,
        )
        self.assertFalse(resolution.executable)
        self.assertEqual(len(resolution.ambiguous), 1)
        self.assertIsNone(resolution.patch_prediction())

    def test_clear_winner_over_runner_up_is_accepted(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (
                RelationEvidence(0, 1, 0, 2, 0.96),
                RelationEvidence(0, 1, 0, 3, 0.70),
            ),
            min_margin=0.10,
        )
        self.assertTrue(resolution.executable)
        self.assertEqual(resolution.accepted[0].destination, 2)

    def test_identical_effect_candidates_collapse_to_strongest(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (
                RelationEvidence(1, 1, 0, 2, 0.82),
                RelationEvidence(1, 1, 0, 2, 0.94),
            ),
        )
        self.assertTrue(resolution.executable)
        self.assertEqual(resolution.accepted[0].confidence, 0.94)

    def test_cells_resolve_independently(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (
                RelationEvidence(0, 1, 0, 2, 0.95),
                RelationEvidence(1, 1, 0, 2, 0.93),
            ),
        )
        self.assertTrue(resolution.executable)
        self.assertEqual(len(resolution.accepted), 2)

    def test_ambiguous_cell_blocks_execution_even_if_other_cell_is_clear(self):
        resolution = resolve_relation_evidence(
            self.signature(),
            (
                RelationEvidence(0, 1, 0, 2, 0.95),
                RelationEvidence(1, 1, 0, 2, 0.91),
                RelationEvidence(1, 1, 0, 3, 0.88),
            ),
        )
        self.assertFalse(resolution.executable)
        self.assertEqual(len(resolution.accepted), 1)
        self.assertEqual(len(resolution.ambiguous), 1)


if __name__ == "__main__":
    unittest.main()
