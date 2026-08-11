import unittest

from semzip.vm_mentions import slotize_mentions


class MentionSlotizerTests(unittest.TestCase):
    def test_slots_mentions_left_to_right(self):
        text = "Alice handed the old brass telescope to Bob."
        spans = (
            (0, 5),
            (17, 36),
            (40, 43),
        )
        result = slotize_mentions(text, spans)
        self.assertEqual(result.text, "E0 handed the E1 to E2.")
        self.assertEqual(result.entities, ("Alice", "old brass telescope", "Bob"))

    def test_input_span_order_does_not_control_ids(self):
        text = "Alice gave Bob the book."
        result = slotize_mentions(text, ((19, 23), (11, 14), (0, 5)))
        self.assertEqual(result.text, "E0 gave E1 the E2.")
        self.assertEqual(result.entities, ("Alice", "Bob", "book"))

    def test_duplicate_span_collapses(self):
        result = slotize_mentions("Alice left.", ((0, 5), (0, 5)))
        self.assertEqual(result.text, "E0 left.")
        self.assertEqual(result.entities, ("Alice",))

    def test_overlapping_spans_are_rejected(self):
        with self.assertRaises(ValueError):
            slotize_mentions("old brass telescope", ((0, 9), (4, 19)))

    def test_invalid_offsets_are_rejected(self):
        with self.assertRaises(ValueError):
            slotize_mentions("Alice", ((0, 99),))


if __name__ == "__main__":
    unittest.main()
