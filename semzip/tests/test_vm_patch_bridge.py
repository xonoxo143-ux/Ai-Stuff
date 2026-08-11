import unittest

from semzip.vm_patch_bridge import (
    PatchPrediction,
    PatchPredictionError,
    RelationCellPrediction,
    ReturnObligationPrediction,
    resolve_patch_prediction,
)
from semzip.vm_relations import DEFAULT_RELATION_REGISTRY, RelationRegistry


class SemanticPatchPredictionBridgeTests(unittest.TestCase):
    def prediction(self, cells=(), obligations=()):
        return PatchPrediction(
            DEFAULT_RELATION_REGISTRY.signature(),
            tuple(cells),
            tuple(obligations),
        )

    def test_resolves_factorized_owner_and_possessor_cells(self):
        prediction = self.prediction((
            RelationCellPrediction(0, 1, 0, 2),
            RelationCellPrediction(1, 1, 0, 2),
        ))
        patch = resolve_patch_prediction(prediction, ("john", "book", "mary"))
        self.assertEqual(len(patch.deltas), 1)
        delta = patch.deltas[0]
        self.assertEqual(delta.subject, "book")
        self.assertEqual(delta.relations, ("owner", "possessor"))

    def test_resolves_reciprocal_exchange_without_event_class(self):
        prediction = self.prediction((
            RelationCellPrediction(0, 1, 0, 2),
            RelationCellPrediction(1, 1, 0, 2),
            RelationCellPrediction(0, 3, 2, 0),
            RelationCellPrediction(1, 3, 2, 0),
        ))
        patch = resolve_patch_prediction(
            prediction, ("john", "book", "mary", "coin")
        )
        self.assertEqual(len(patch.deltas), 2)

    def test_relation_registry_signature_mismatch_is_rejected(self):
        other = RelationRegistry(("owner", "possessor", "location", "powered"))
        prediction = self.prediction((RelationCellPrediction(0, 1, 0, 2),))
        with self.assertRaises(PatchPredictionError):
            resolve_patch_prediction(
                prediction,
                ("john", "book", "mary"),
                registry=other,
            )

    def test_unknown_relation_id_is_rejected(self):
        prediction = self.prediction((RelationCellPrediction(99, 1, 0, 2),))
        with self.assertRaises(PatchPredictionError):
            resolve_patch_prediction(prediction, ("john", "book", "mary"))

    def test_out_of_range_entity_pointer_is_rejected(self):
        prediction = self.prediction((RelationCellPrediction(0, 9, 0, 2),))
        with self.assertRaises(PatchPredictionError):
            resolve_patch_prediction(prediction, ("john", "book", "mary"))

    def test_conflicting_same_relation_is_rejected(self):
        prediction = self.prediction((
            RelationCellPrediction(0, 1, 0, 2),
            RelationCellPrediction(0, 1, 0, 3),
        ))
        with self.assertRaises(PatchPredictionError):
            resolve_patch_prediction(
                prediction, ("john", "book", "mary", "alice")
            )

    def test_duplicate_identical_cells_collapse(self):
        cell = RelationCellPrediction(0, 1, 0, 2)
        patch = resolve_patch_prediction(
            self.prediction((cell, cell)),
            ("john", "book", "mary"),
        )
        self.assertEqual(len(patch.deltas), 1)

    def test_return_obligation_uses_only_entity_pointers(self):
        prediction = self.prediction(
            (RelationCellPrediction(1, 1, 0, 2),),
            (ReturnObligationPrediction(1, 2, 0),),
        )
        patch = resolve_patch_prediction(prediction, ("john", "book", "mary"))
        self.assertEqual(patch.return_obligations[0].key(), ("book", "mary", "john"))

    def test_empty_prediction_is_rejected(self):
        with self.assertRaises(PatchPredictionError):
            resolve_patch_prediction(self.prediction(), ("john",))


if __name__ == "__main__":
    unittest.main()
