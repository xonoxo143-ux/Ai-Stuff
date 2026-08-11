import unittest

from semzip.vm_delta_bridge import (
    NONE_POINTER,
    DeltaPrediction,
    DeltaPredictionError,
    resolve_delta_prediction,
)
from semzip.vm_delta import compile_delta_frame
from semzip.vm_compile import seed_object
from semzip.vm_kernel import SemanticVM


class DeltaPredictionBridgeTests(unittest.TestCase):
    def test_resolves_anonymous_gift_prediction(self):
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(True, True, False),
        )
        frame = resolve_delta_prediction(prediction, ("john", "book", "mary"))
        self.assertEqual(frame.primary.subject, "book")
        self.assertEqual(frame.primary.relations, ("owner", "possessor"))

    def test_resolved_prediction_executes(self):
        vm = SemanticVM()
        vm.execute(seed_object("book", "john"))
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(True, True, False),
        )
        frame = resolve_delta_prediction(prediction, ("john", "book", "mary"))
        vm.execute(compile_delta_frame(frame))
        self.assertEqual(vm.ledger.current("book", "owner"), "mary")

    def test_rejects_out_of_range_pointer(self):
        prediction = DeltaPrediction(
            primary_subject=9,
            primary_source=0,
            primary_destination=1,
            primary_relations=(False, True, False),
        )
        with self.assertRaises(DeltaPredictionError):
            resolve_delta_prediction(prediction, ("john", "mary"))

    def test_rejects_hidden_secondary_payload(self):
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(True, True, False),
            secondary_present=False,
            secondary_subject=3,
        )
        with self.assertRaises(DeltaPredictionError):
            resolve_delta_prediction(prediction, ("john", "book", "mary", "coin"))

    def test_resolves_reciprocal_exchange(self):
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(True, True, False),
            secondary_present=True,
            secondary_subject=3,
            secondary_source=2,
            secondary_destination=0,
            secondary_relations=(True, True, False),
        )
        frame = resolve_delta_prediction(
            prediction, ("john", "book", "mary", "coin")
        )
        self.assertIsNotNone(frame.secondary)
        self.assertEqual(frame.secondary.subject, "coin")
        self.assertEqual(frame.secondary.source, "mary")
        self.assertEqual(frame.secondary.destination, "john")

    def test_rejects_obligation_without_possession(self):
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(True, False, False),
            return_obligation=True,
        )
        with self.assertRaises(DeltaPredictionError):
            resolve_delta_prediction(prediction, ("john", "book", "mary"))

    def test_default_secondary_is_explicitly_empty(self):
        prediction = DeltaPrediction(
            primary_subject=1,
            primary_source=0,
            primary_destination=2,
            primary_relations=(False, True, False),
        )
        self.assertEqual(prediction.secondary_subject, NONE_POINTER)
        resolve_delta_prediction(prediction, ("john", "book", "mary"))


if __name__ == "__main__":
    unittest.main()
