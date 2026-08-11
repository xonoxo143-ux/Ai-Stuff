import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_patch import SemanticPatch
from semzip.vm_semantic_parse import AtomicSemanticCandidate, candidate_splits, parse_semantics


class RecursiveSemanticParserTests(unittest.TestCase):
    def owner_patch(self, who="mary"):
        return SemanticPatch.build((
            RelationDelta.build("book", "john", who, ("owner",)),
        ))

    def possessor_patch(self):
        return SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("possessor",)),
        ))

    def test_candidate_split_is_only_a_hypothesis(self):
        splits = candidate_splits("John left and Mary stayed")
        self.assertIn(("John left", "Mary stayed"), splits)

    def test_recursively_composes_atomic_meanings(self):
        def compiler(text):
            if text == "ownership changed":
                return (AtomicSemanticCandidate(self.owner_patch(), 0.98, "owner"),)
            if text == "possession changed":
                return (AtomicSemanticCandidate(self.possessor_patch(), 0.97, "possessor"),)
            return ()

        parsed = parse_semantics("ownership changed and possession changed", compiler)
        self.assertIsNotNone(parsed)
        expected = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
        ))
        self.assertEqual(parsed.patch, expected)
        self.assertEqual(parsed.atomic_labels, ("owner", "possessor"))

    def test_invalid_split_disappears_when_atomic_pieces_do_not_compile(self):
        whole = self.owner_patch()

        def compiler(text):
            if text == "bread and butter":
                return (AtomicSemanticCandidate(whole, 0.9, "idiom"),)
            return ()

        parsed = parse_semantics("bread and butter", compiler)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.parts, 1)
        self.assertEqual(parsed.atomic_labels, ("idiom",))

    def test_conflicting_composition_is_rejected(self):
        def compiler(text):
            if text == "mary owns":
                return (AtomicSemanticCandidate(self.owner_patch("mary"), 0.99),)
            if text == "alice owns":
                return (AtomicSemanticCandidate(self.owner_patch("alice"), 0.99),)
            return ()

        parsed = parse_semantics("mary owns and alice owns", compiler)
        self.assertIsNone(parsed)

    def test_high_confidence_atomic_parse_can_beat_split(self):
        whole = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner", "possessor")),
        ))

        def compiler(text):
            if text == "ownership changed and possession changed":
                return (AtomicSemanticCandidate(whole, 0.99, "whole"),)
            if text == "ownership changed":
                return (AtomicSemanticCandidate(self.owner_patch(), 0.75, "owner"),)
            if text == "possession changed":
                return (AtomicSemanticCandidate(self.possessor_patch(), 0.75, "possessor"),)
            return ()

        parsed = parse_semantics("ownership changed and possession changed", compiler)
        self.assertEqual(parsed.parts, 1)
        self.assertEqual(parsed.atomic_labels, ("whole",))

    def test_wrong_whole_parse_can_lose_to_stronger_composed_evidence(self):
        weak_wrong = self.owner_patch()

        def compiler(text):
            if text == "ownership changed and possession changed":
                return (AtomicSemanticCandidate(weak_wrong, 0.30, "weak_whole"),)
            if text == "ownership changed":
                return (AtomicSemanticCandidate(self.owner_patch(), 0.99, "owner"),)
            if text == "possession changed":
                return (AtomicSemanticCandidate(self.possessor_patch(), 0.99, "possessor"),)
            return ()

        parsed = parse_semantics(
            "ownership changed and possession changed",
            compiler,
            split_penalty=0.02,
        )
        self.assertEqual(parsed.parts, 2)
        self.assertEqual(parsed.atomic_labels, ("owner", "possessor"))


if __name__ == "__main__":
    unittest.main()
