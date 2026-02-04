# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.locales import get_text_patterns


class TestZhHantPatterns(unittest.TestCase):
    def test_card_challenge_remaining_plays_variants(self):
        patterns = get_text_patterns("card_challenge_remaining_plays")
        self.assertIn("剩餘遊玩次數", patterns)


if __name__ == "__main__":
    unittest.main()
