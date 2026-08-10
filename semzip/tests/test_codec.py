import unittest

from semzip import SemZipCodec, UnsupportedMeaningError


class CodecTests(unittest.TestCase):
    def setUp(self) -> None:
        self.codec = SemZipCodec()

    def test_paraphrases_converge(self) -> None:
        texts = [
            "John gave Mary the book.",
            "Mary received the book from John.",
            "The book was given to Mary by John.",
        ]
        graphs = [self.codec.encode(text) for text in texts]
        self.assertTrue(all(graph == graphs[0] for graph in graphs[1:]))
        self.assertEqual(len({graph.semantic_hash() for graph in graphs}), 1)

    def test_role_change_is_not_equivalent(self) -> None:
        a = self.codec.encode("John gave Mary the book.")
        b = self.codec.encode("Mary gave John the book.")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a.semantic_hash(), b.semantic_hash())

    def test_negation_is_preserved(self) -> None:
        positive = self.codec.encode("John gave Mary the book.")
        negative = self.codec.encode("John did not give Mary the book.")
        self.assertTrue(positive.polarity)
        self.assertFalse(negative.polarity)
        self.assertNotEqual(positive.semantic_hash(), negative.semantic_hash())

    def test_roundtrip_is_semantically_stable(self) -> None:
        first, generated, second = self.codec.roundtrip(
            "The old red bicycle was given to Mary by John."
        )
        self.assertEqual(first, second)
        self.assertEqual(generated, "John gave Mary the old red bicycle.")

    def test_unsupported_input_fails_loudly(self) -> None:
        with self.assertRaises(UnsupportedMeaningError):
            self.codec.encode("John probably wanted Mary to have the book.")


if __name__ == "__main__":
    unittest.main()
