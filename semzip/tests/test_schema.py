import unittest

from semzip.meaning import Meaning
from semzip.schema import SemanticValidationError, validate_meaning


class SchemaTests(unittest.TestCase):
    def test_valid_nested_belief(self):
        content = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "mary"}
        )
        validate_meaning(Meaning.build("BELIEVE", {"holder": "bob", "content": content}))

    def test_nested_json_roundtrip_is_exact(self):
        inner = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "mary"}
        )
        original = Meaning.build("BELIEVE", {"holder": "bob", "content": inner})
        restored = Meaning.from_json(original.canonical_json())
        self.assertEqual(restored, original)
        self.assertEqual(restored.semantic_hash(), original.semantic_hash())

    def test_ambiguity_sequence_roundtrips_and_validates(self):
        a = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "john"}
        )
        b = Meaning.build(
            "STATE", {"subject": "key#2", "dimension": "owner", "value": "mary"}
        )
        ambiguity = Meaning.build("AMBIGUITY", {"options": (a, b)})
        validate_meaning(ambiguity)
        restored = Meaning.from_json(ambiguity.canonical_json())
        self.assertEqual(restored, ambiguity)
        self.assertEqual(restored.expressions("OPTIONS"), (a, b))

    def test_missing_role_fails(self):
        with self.assertRaises(SemanticValidationError):
            validate_meaning(Meaning.build("CHANGE", {"subject": "key", "after": "mary"}))

    def test_unknown_role_fails(self):
        with self.assertRaises(SemanticValidationError):
            validate_meaning(
                Meaning.build(
                    "STATE",
                    {
                        "subject": "key",
                        "dimension": "owner",
                        "value": "mary",
                        "banana": "yes",
                    },
                )
            )

    def test_wrong_nested_type_fails(self):
        with self.assertRaises(SemanticValidationError):
            validate_meaning(
                Meaning.build("BELIEVE", {"holder": "bob", "content": "key_is_marys"})
            )

    def test_recursive_validation_catches_bad_content(self):
        bad = Meaning.build("STATE", {"subject": "key", "value": "mary"})
        outer = Meaning.build("POSSIBLE", {"content": bad})
        with self.assertRaises(SemanticValidationError):
            validate_meaning(outer)


class CanonicalCollectionTests(unittest.TestCase):
    def test_ambiguity_order_does_not_change_meaning(self):
        from semzip.collections import ambiguity

        a = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "john"}
        )
        b = Meaning.build(
            "STATE", {"subject": "key#2", "dimension": "owner", "value": "john"}
        )
        self.assertEqual(ambiguity([a, b]), ambiguity([b, a]))
        self.assertEqual(
            ambiguity([a, b]).semantic_hash(), ambiguity([b, a]).semantic_hash()
        )

    def test_bundle_and_set_are_order_independent(self):
        from semzip.collections import bundle, semantic_set

        a = Meaning.build(
            "STATE", {"subject": "key", "dimension": "owner", "value": "john"}
        )
        b = Meaning.build(
            "STATE", {"subject": "key", "dimension": "color", "value": "red"}
        )
        self.assertEqual(bundle([a, b]), bundle([b, a]))
        self.assertEqual(
            semantic_set(["key#2", "key"]), semantic_set(["key", "key#2"])
        )


if __name__ == "__main__":
    unittest.main()
