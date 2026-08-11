import unittest

from semzip.meaning import Meaning
from semzip.schema import SemanticValidationError, validate_meaning


class SchemaTests(unittest.TestCase):
    def test_valid_nested_belief(self):
        content = Meaning.build(
            "STATE",
            {"subject": "key", "dimension": "owner", "value": "mary"},
        )
        validate_meaning(
            Meaning.build("BELIEVE", {"holder": "bob", "content": content})
        )

    def test_missing_role_fails(self):
        with self.assertRaises(SemanticValidationError):
            validate_meaning(
                Meaning.build("CHANGE", {"subject": "key", "after": "mary"})
            )

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
                Meaning.build(
                    "BELIEVE", {"holder": "bob", "content": "key_is_marys"}
                )
            )

    def test_recursive_validation_catches_bad_content(self):
        bad = Meaning.build("STATE", {"subject": "key", "value": "mary"})
        outer = Meaning.build("POSSIBLE", {"content": bad})
        with self.assertRaises(SemanticValidationError):
            validate_meaning(outer)


if __name__ == "__main__":
    unittest.main()
