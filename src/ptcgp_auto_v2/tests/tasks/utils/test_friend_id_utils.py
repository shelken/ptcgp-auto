import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.utils.friend_id_utils import extract_friend_id_from_text


class TestFriendIdUtils(unittest.TestCase):
    def test_extract_friend_id_from_standard_text(self):
        text = "朋友id: 1234-5678-9012-3456"
        self.assertEqual("1234567890123456", extract_friend_id_from_text(text))

    def test_extract_friend_id_from_mixed_text(self):
        text = "abc 0000-1111-2222-3333 xyz"
        self.assertEqual("0000111122223333", extract_friend_id_from_text(text))

    def test_extract_friend_id_returns_none_when_missing(self):
        text = "这里没有朋友id"
        self.assertIsNone(extract_friend_id_from_text(text))


if __name__ == "__main__":
    unittest.main()
