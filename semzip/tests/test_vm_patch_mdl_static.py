import unittest

from semzip.vm_patch import SemanticPatch, StateAssignment, StateClear
from semzip.vm_patch_mdl import PatchMacro, patch_pattern, patch_records


class StaticPatchMDLTests(unittest.TestCase):
    def test_assignment_is_not_dropped_from_effect_records(self):
        patch = SemanticPatch.build(
            assignments=(StateAssignment.build("book", "color", "red"),)
        )
        self.assertEqual(
            patch_records(patch),
            (("SET", "color", "book", "red", "_"),),
        )

    def test_clear_is_not_dropped_from_effect_records(self):
        patch = SemanticPatch.build(
            clears=(StateClear.build("book", "tag"),)
        )
        self.assertEqual(
            patch_records(patch),
            (("CLEAR", "tag", "book", "_", "_"),),
        )

    def test_assignment_pattern_abstracts_subject_and_value(self):
        red_book = SemanticPatch.build(
            assignments=(StateAssignment.build("book", "color", "red"),)
        )
        blue_shirt = SemanticPatch.build(
            assignments=(StateAssignment.build("shirt", "color", "blue"),)
        )
        self.assertEqual(
            patch_pattern(red_book).pattern,
            patch_pattern(blue_shirt).pattern,
        )

    def test_assignment_dimension_remains_semantic_constant(self):
        color = SemanticPatch.build(
            assignments=(StateAssignment.build("book", "color", "red"),)
        )
        temperature = SemanticPatch.build(
            assignments=(StateAssignment.build("book", "temperature", "hot"),)
        )
        self.assertNotEqual(
            patch_pattern(color).pattern,
            patch_pattern(temperature).pattern,
        )

    def test_clear_pattern_abstracts_subject_but_not_dimension(self):
        left = SemanticPatch.build(clears=(StateClear.build("book", "tag"),))
        right = SemanticPatch.build(clears=(StateClear.build("key", "tag"),))
        other = SemanticPatch.build(clears=(StateClear.build("key", "location"),))
        self.assertEqual(patch_pattern(left).pattern, patch_pattern(right).pattern)
        self.assertNotEqual(patch_pattern(left).pattern, patch_pattern(other).pattern)

    def test_static_macro_round_trip_is_exact(self):
        original = SemanticPatch.build(
            assignments=(StateAssignment.build("switch", "powered", "on"),),
            clears=(StateClear.build("switch", "fault"),),
        )
        instance = patch_pattern(original)
        expanded = PatchMacro("M_static", instance.pattern).expand(instance.bindings)
        self.assertEqual(expanded, original)


if __name__ == "__main__":
    unittest.main()
