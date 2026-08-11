import unittest

from semzip.metrics import analyze, repeated_structures, structural_signature
from semzip.molecules import (
    borrow,
    buy,
    give,
    receive,
    sell,
    lend,
    size_change,
    temperature_change,
)


class MetricsTests(unittest.TestCase):
    def test_shape_erases_atoms_but_keeps_structure(self):
        heat = temperature_change("water", "cold", "hot")
        grow = size_change("tree", "small", "large")
        self.assertEqual(structural_signature(heat), structural_signature(grow))

    def test_report_detects_exact_and_structural_reuse(self):
        meanings = [
            give("john", "mary", "book"),
            receive("mary", "book", "john"),
            buy("mary", "book", "john", "cash"),
            sell("john", "mary", "book", "cash"),
            borrow("mary", "book", "john"),
            lend("john", "mary", "book"),
            temperature_change("water", "cold", "hot"),
            size_change("tree", "small", "large"),
        ]
        report = analyze(meanings)
        self.assertEqual(report.surface_forms, 8)
        self.assertEqual(report.unique_meanings, 5)
        self.assertLess(report.unique_shapes, report.unique_meanings)
        self.assertGreater(report.exact_deduplication, 0)
        self.assertGreater(report.shape_reuse, report.exact_deduplication)
        operators = dict(report.operator_counts)
        self.assertGreaterEqual(operators["CHANGE"], 1)

    def test_repeated_substructures_find_change_molecule(self):
        meanings = [
            buy("mary", "book", "john", "cash"),
            sell("john", "mary", "book", "cash"),
            borrow("mary", "book", "john"),
            lend("john", "mary", "book"),
        ]
        candidates = repeated_structures(meanings)
        self.assertTrue(candidates)
        self.assertTrue(
            any(
                candidate.signature[0] == "CHANGE" and candidate.count >= 4
                for candidate in candidates
            )
        )

    def test_operator_inventory_reaches_sequence_options(self):
        from semzip.meaning import Meaning
        from semzip.metrics import operator_inventory

        a = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "john"}
        )
        b = Meaning.build(
            "STATE", {"subject": "key#2", "dimension": "owner", "value": "mary"}
        )
        ambiguity = Meaning.build("AMBIGUITY", {"options": (a, b)})
        counts = operator_inventory(ambiguity)
        self.assertEqual(counts["AMBIGUITY"], 1)
        self.assertEqual(counts["STATE"], 2)

    def test_empty_report_is_defined(self):
        report = analyze([])
        self.assertEqual(report.surface_forms, 0)
        self.assertEqual(report.exact_deduplication, 0.0)


if __name__ == "__main__":
    unittest.main()
