import unittest

from ebook_polisher.coverage_gate import coverage_gate


class TestCoverageGate(unittest.TestCase):
    def test_all_equal_ok(self):
        counts = {
            "source": 3000,
            "parsed": 3000,
            "chunked": 3000,
            "polished": 3000,
            "verified": 3000,
            "assembled": 3000,
        }
        res = coverage_gate(counts)
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["expected"], 3000)
        self.assertEqual(res["stages_failed"], [])

    def test_one_mismatch(self):
        counts = {
            "source": 3000,
            "parsed": 3000,
            "chunked": 2999,
            "polished": 3000,
            "verified": 3000,
            "assembled": 3000,
        }
        res = coverage_gate(counts)
        self.assertFalse(res["ok"], res)
        self.assertEqual(res["expected"], 3000)
        self.assertIn("chunked", res["stages_failed"])

    def test_zero_counts_not_ok(self):
        counts = {
            "source": 0,
            "parsed": 0,
            "chunked": 0,
        }
        res = coverage_gate(counts)
        self.assertFalse(res["ok"], res)

    def test_multiple_mismatch_sorted(self):
        counts = {
            "source": 100,
            "parsed": 99,
            "chunked": 100,
            "verified": 50,
        }
        res = coverage_gate(counts)
        self.assertFalse(res["ok"])
        self.assertEqual(res["stages_failed"], ["parsed", "verified"])


if __name__ == "__main__":
    unittest.main()
