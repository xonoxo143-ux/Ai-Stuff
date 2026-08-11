import unittest

from semzip.vm_delta import RelationDelta
from semzip.vm_patch import ReturnObligation, SemanticPatch
from semzip.vm_patch_mdl import (
    PatchMacro,
    candidate_cost,
    canonical_pattern,
    discover_patch_macro_candidates,
    patch_pattern,
    patch_records,
    promote_best_patch_macro,
)


def transfer(subject, source, destination):
    return SemanticPatch.build((
        RelationDelta.build(subject, source, destination, ("owner", "possessor")),
    ))


def exchange(goods, seller, buyer, payment):
    return SemanticPatch.build((
        RelationDelta.build(goods, seller, buyer, ("owner", "possessor")),
        RelationDelta.build(payment, buyer, seller, ("owner", "possessor")),
    ))


class PatchMDLTests(unittest.TestCase):
    def test_entity_renaming_does_not_change_pattern(self):
        a = transfer("book", "john", "mary")
        b = transfer("sword", "alice", "bob")
        self.assertEqual(patch_pattern(a).pattern, patch_pattern(b).pattern)

    def test_patch_order_does_not_change_pattern(self):
        left = exchange("book", "john", "mary", "coin")
        right = SemanticPatch.build(tuple(reversed(left.deltas)))
        self.assertEqual(patch_pattern(left).pattern, patch_pattern(right).pattern)

    def test_reciprocal_exchange_renaming_is_canonical(self):
        a = exchange("book", "john", "mary", "coin")
        b = exchange("gem", "zara", "quinn", "token")
        self.assertEqual(patch_pattern(a).pattern, patch_pattern(b).pattern)

    def test_explicit_effects_participate_in_pattern(self):
        loan_a = SemanticPatch.build(
            (RelationDelta.build("book", "john", "mary", ("possessor",)),),
            return_obligations=(ReturnObligation.build("book", "mary", "john"),),
        )
        loan_b = SemanticPatch.build(
            (RelationDelta.build("key", "alice", "bob", ("possessor",)),),
            return_obligations=(ReturnObligation.build("key", "bob", "alice"),),
        )
        self.assertEqual(patch_pattern(loan_a).pattern, patch_pattern(loan_b).pattern)

    def test_macro_round_trip_is_exact_for_full_patch_pattern(self):
        original = exchange("book", "john", "mary", "coin")
        instance = patch_pattern(original)
        macro = PatchMacro("M_exchange", instance.pattern)
        expanded = macro.expand(instance.bindings)
        self.assertEqual(expanded, original)

    def test_candidate_cost_uses_real_nonoverlapping_substitution(self):
        corpus = (
            exchange("book", "john", "mary", "coin"),
            exchange("sword", "alice", "bob", "token"),
        )
        transfer_pattern = patch_pattern(transfer("x", "a", "b")).pattern
        score = candidate_cost(corpus, transfer_pattern)
        # Each exchange contains two non-overlapping transfer-shaped subpatches.
        self.assertEqual(score.occurrences, 4)
        self.assertGreater(score.savings, 0)
        self.assertLess(score.encoded_cost, score.base_cost)

    def test_discovery_prefers_reusable_transfer_shape_over_whole_exchange(self):
        corpus = (
            transfer("book", "john", "mary"),
            transfer("key", "alice", "bob"),
            transfer("gem", "quinn", "zara"),
            transfer("map", "lee", "sam"),
            exchange("sword", "anna", "ben", "coin"),
            exchange("shield", "cara", "dave", "token"),
        )
        candidates = discover_patch_macro_candidates(corpus, min_records=2, max_records=4)
        self.assertTrue(candidates)
        expected = patch_pattern(transfer("thing", "source", "destination")).pattern
        self.assertEqual(candidates[0].pattern, expected)
        self.assertGreater(candidates[0].savings, 0)

    def test_promote_best_macro_requires_real_savings(self):
        corpus = (
            transfer("book", "john", "mary"),
            transfer("key", "alice", "bob"),
            transfer("gem", "quinn", "zara"),
        )
        macro, score = promote_best_patch_macro(corpus, macro_id="M0")
        self.assertIsNotNone(macro)
        self.assertIsNotNone(score)
        self.assertGreater(score.savings, 0)

    def test_unique_pattern_is_not_promoted(self):
        corpus = (exchange("book", "john", "mary", "coin"),)
        macro, score = promote_best_patch_macro(
            corpus,
            min_occurrences=2,
            min_records=4,
            max_records=4,
        )
        self.assertIsNone(macro)
        self.assertIsNone(score)


if __name__ == "__main__":
    unittest.main()
