"""ebook_polisher.polisher 단위 테스트."""
import unittest

from ebook_polisher.polisher import RulesPolisher


class TestPolisher(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "chunk_id": "chunk-1",
            "source_blocks": [
                {"block_id": "b1", "page": 1, "type": "paragraph",
                 "text": "이  문장에는   두 칸  공백이 있다."},
                {"block_id": "b2", "page": 1, "type": "paragraph",
                 "text": "이것은 추정에 근거한 서술이다."},
                {"block_id": "b3", "page": 2, "type": "paragraph",
                 "text": "2026년에 일어난 일이다."},
            ],
        }

    def test_block_count_matches(self):
        result = RulesPolisher().polish(self.payload)
        self.assertEqual(len(result.polished_blocks), 3)

    def test_block_ids_preserved(self):
        result = RulesPolisher().polish(self.payload)
        ids = [b.block_id for b in result.polished_blocks]
        self.assertEqual(ids, ["b1", "b2", "b3"])

    def test_spaced_block_collapsed_and_light(self):
        result = RulesPolisher().polish(self.payload)
        b1 = result.polished_blocks[0]
        self.assertEqual(b1.change_level, "light")
        self.assertEqual(b1.polished_text, "이 문장에는 두 칸 공백이 있다.")
        self.assertNotIn("  ", b1.polished_text)

    def test_ambiguity_block_crescent(self):
        result = RulesPolisher().polish(self.payload)
        b2 = result.polished_blocks[1]
        self.assertEqual(b2.honest_marker, "crescent")

    def test_number_lossless(self):
        result = RulesPolisher().polish(self.payload)
        b3 = result.polished_blocks[2]
        self.assertIn("2026", b3.polished_text)

    def test_chunk_id_preserved(self):
        result = RulesPolisher().polish(self.payload)
        self.assertEqual(result.chunk_id, "chunk-1")

    def test_no_change_block_is_none(self):
        result = RulesPolisher().polish(self.payload)
        # b3 has no formatting issues -> change_level none.
        b3 = result.polished_blocks[2]
        self.assertEqual(b3.change_level, "none")


if __name__ == "__main__":
    unittest.main()
