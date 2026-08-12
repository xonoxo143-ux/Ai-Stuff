import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_patch import SemanticPatch
from semzip.vm_semantic_parse import AtomicSemanticCandidate
from semzip.vm_sequence_parse import candidate_sequence_splits, parse_semantic_sequence


class SemanticSequenceParserTests(unittest.TestCase):
    def transfer(self, source, destination):
        return SemanticPatch.build((
            RelationDelta.build("book", source, destination, ("owner", "possessor")),
        ))

    def test_explicit_then_is_sequence_boundary(self):
        self.assertIn(
            ("john to mary", "mary to alice"),
            candidate_sequence_splits("john to mary then mary to alice"),
        )

    def test_then_preserves_two_conflicting_time_steps(self):
        def compiler(text):
            if text == "john to mary":
                return (AtomicSemanticCandidate(self.transfer("john", "mary"), 0.99, "first"),)
            if text == "mary to alice":
                return (AtomicSemanticCandidate(self.transfer("mary", "alice"), 0.99, "second"),)
            return ()

        parsed = parse_semantic_sequence(
            "john to mary then mary to alice",
            compiler,
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed.sequence.steps), 2)
        self.assertEqual(parsed.segments, ("john to mary", "mary to alice"))

    def test_conjunction_inside_one_step_can_still_union(self):
        owner = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("owner",)),
        ))
        possessor = SemanticPatch.build((
            RelationDelta.build("book", "john", "mary", ("possessor",)),
        ))

        def compiler(text):
            if text == "owner changed":
                return (AtomicSemanticCandidate(owner, 0.99, "owner"),)
            if text == "possession changed":
                return (AtomicSemanticCandidate(possessor, 0.99, "possessor"),)
            return ()

        parsed = parse_semantic_sequence(
            "owner changed and possession changed",
            compiler,
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed.sequence.steps), 1)
        self.assertEqual(parsed.sequence.steps[0].deltas[0].relations, ("owner", "possessor"))

    def test_multiple_then_markers_recurse(self):
        patches = {
            "a": self.transfer("john", "mary"),
            "b": self.transfer("mary", "alice"),
            "c": self.transfer("alice", "bob"),
        }

        def compiler(text):
            if text in patches:
                return (AtomicSemanticCandidate(patches[text], 0.98, text),)
            return ()

        parsed = parse_semantic_sequence("a then b then c", compiler)
        self.assertIsNotNone(parsed)
        self.assertEqual(len(parsed.sequence.steps), 3)
        self.assertEqual(parsed.segments, ("a", "b", "c"))


if __name__ == "__main__":
    unittest.main()
