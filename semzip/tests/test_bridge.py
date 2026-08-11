import unittest

from semzip.bridge import ExternalMeaningError, SemanticJSONBridge
from semzip.meaning import Meaning


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = SemanticJSONBridge()

    def test_valid_external_meaning_is_accepted(self):
        proposed = Meaning.build(
            "POSSIBLE",
            {
                "content": Meaning.build(
                    "STATE",
                    {"subject": "door", "dimension": "open", "value": "true"},
                )
            },
        )
        result = self.bridge.decode(proposed.canonical_json(), source="test-parser")
        self.assertEqual(result.meaning, proposed)
        self.assertEqual(result.source, "test-parser")

    def test_unknown_operator_is_rejected(self):
        proposed = Meaning.build("MAGICALLY_TRUE", {"thing": "door"})
        with self.assertRaises(ExternalMeaningError):
            self.bridge.decode(proposed.canonical_json())

    def test_schema_invalid_nested_output_is_rejected(self):
        bad = '{"operator":"POSSIBLE","roles":{"CONTENT":{"operator":"STATE","roles":{"SUBJECT":"door"}}}}'
        with self.assertRaises(ExternalMeaningError):
            self.bridge.decode(bad)

    def test_malformed_json_is_rejected(self):
        with self.assertRaises(ExternalMeaningError):
            self.bridge.decode('{not-json')


if __name__ == "__main__":
    unittest.main()
