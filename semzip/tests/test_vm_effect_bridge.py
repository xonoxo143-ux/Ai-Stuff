import unittest

from semzip.vm_effect_bridge import (
    AssignmentPrediction,
    ClearPrediction,
    EffectPredictionError,
    SemanticEffectPrediction,
    TransitionPrediction,
    resolve_effect_prediction,
)
from semzip.vm_relations import RelationRegistry


class SemanticEffectBridgeTests(unittest.TestCase):
    def registry(self):
        return RelationRegistry(("owner", "possessor", "location", "color", "tag"))

    def test_resolves_transition_assignment_and_clear_without_free_text(self):
        registry = self.registry()
        prediction = SemanticEffectPrediction(
            registry_signature=registry.signature(),
            transitions=(TransitionPrediction(0, 1, 0, 2),),
            assignments=(AssignmentPrediction(3, 1, 0),),
            clears=(ClearPrediction(4, 1),),
        )
        patch = resolve_effect_prediction(
            prediction,
            ("john", "book", "mary"),
            atoms=("red",),
            registry=registry,
        )
        self.assertEqual(patch.deltas[0].relations, ("owner",))
        self.assertEqual(patch.assignments[0].key(), ("book", "color", "red"))
        self.assertEqual(patch.clears[0].key(), ("book", "tag"))

    def test_signature_mismatch_rejects_compiler_output(self):
        registry = self.registry()
        prediction = SemanticEffectPrediction(
            registry_signature="wrong",
            transitions=(TransitionPrediction(0, 1, 0, 2),),
        )
        with self.assertRaises(EffectPredictionError):
            resolve_effect_prediction(
                prediction, ("john", "book", "mary"), registry=registry
            )

    def test_assignment_value_uses_closed_atom_table(self):
        registry = self.registry()
        prediction = SemanticEffectPrediction(
            registry_signature=registry.signature(),
            assignments=(AssignmentPrediction(3, 0, 2),),
        )
        with self.assertRaises(EffectPredictionError):
            resolve_effect_prediction(
                prediction,
                ("book",),
                atoms=("red", "blue"),
                registry=registry,
            )

    def test_conflicting_effect_types_same_cell_are_rejected(self):
        registry = self.registry()
        prediction = SemanticEffectPrediction(
            registry_signature=registry.signature(),
            transitions=(TransitionPrediction(0, 1, 0, 2),),
            assignments=(AssignmentPrediction(0, 1, 0),),
        )
        with self.assertRaises(EffectPredictionError):
            resolve_effect_prediction(
                prediction,
                ("john", "book", "mary"),
                atoms=("mary",),
                registry=registry,
            )

    def test_identical_duplicate_transition_collapses(self):
        registry = self.registry()
        item = TransitionPrediction(0, 1, 0, 2)
        patch = resolve_effect_prediction(
            SemanticEffectPrediction(registry.signature(), transitions=(item, item)),
            ("john", "book", "mary"),
            registry=registry,
        )
        self.assertEqual(len(patch.deltas), 1)

    def test_empty_effect_set_is_rejected(self):
        registry = self.registry()
        with self.assertRaises(EffectPredictionError):
            resolve_effect_prediction(
                SemanticEffectPrediction(registry.signature()),
                ("book",),
                registry=registry,
            )


if __name__ == "__main__":
    unittest.main()
