import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.utils.nickname_utils import extract_nickname_by_lv


class TestNicknameUtils(unittest.TestCase):
    def test_extract_nickname_by_lv_picks_nearest_candidate(self):
        ocr = [
            {"text": "Lv.22", "box": (100, 100, 180, 140)},
            {"text": "玩家甲", "box": (110, 160, 220, 200)},
            {"text": "玩家乙", "box": (110, 230, 220, 270)},
        ]
        nickname = extract_nickname_by_lv(ocr, search_range_y=200, excluded_contains=[])
        self.assertEqual("玩家甲", nickname)

    def test_extract_nickname_by_lv_filters_numeric_noise(self):
        ocr = [
            {"text": "Lv.8", "box": (100, 100, 180, 140)},
            {"text": "1,234", "box": (110, 160, 220, 200)},
            {"text": "12/34", "box": (110, 210, 220, 250)},
            {"text": "有效昵称", "box": (110, 260, 260, 300)},
        ]
        nickname = extract_nickname_by_lv(ocr, search_range_y=240, excluded_contains=[])
        self.assertEqual("有效昵称", nickname)

    def test_extract_nickname_by_lv_returns_none_without_lv(self):
        ocr = [{"text": "玩家甲", "box": (110, 160, 220, 200)}]
        nickname = extract_nickname_by_lv(ocr, search_range_y=200, excluded_contains=[])
        self.assertIsNone(nickname)


if __name__ == "__main__":
    unittest.main()
