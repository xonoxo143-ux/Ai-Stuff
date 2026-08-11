import unittest

from semzip.multilingual import MiniTransferAdapter, UnsupportedAdapterText


class MultilingualTests(unittest.TestCase):
    def setUp(self):
        self.adapter = MiniTransferAdapter()

    def test_english_and_spanish_give_converge(self):
        english = self.adapter.encode("John gave Mary the book.")
        spanish = self.adapter.encode("John le dio el libro a Mary.")
        self.assertEqual(english, spanish)
        self.assertEqual(english.semantic_hash(), spanish.semantic_hash())

    def test_receive_viewpoint_and_language_both_converge(self):
        forms = [
            "John gave Mary the book.",
            "Mary received the book from John.",
            "John le dio el libro a Mary.",
            "Mary recibió el libro de John.",
        ]
        meanings = [self.adapter.encode(text) for text in forms]
        self.assertTrue(all(item == meanings[0] for item in meanings[1:]))

    def test_language_specific_words_map_to_same_concept(self):
        self.assertEqual(
            self.adapter.encode("John gave Mary the key."),
            self.adapter.encode("John le dio la llave a Mary."),
        )

    def test_unknown_lexical_concept_fails_loudly(self):
        with self.assertRaises(UnsupportedAdapterText):
            self.adapter.encode("John le dio el sombrero a Mary.")


if __name__ == "__main__":
    unittest.main()
