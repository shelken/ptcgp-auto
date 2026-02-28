import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.claim_gifts import ClaimGiftsTask
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class FakePageDetector:
    def __init__(self, gift_match=None, screenshot=None):
        self._gift_match = gift_match
        self._last_screenshot = screenshot if screenshot is not None else object()
        self._last_ocr_results = []

    def capture(self, screenshot=None):
        return self._last_screenshot, self._last_ocr_results

    def find_template_with_scale(
        self, template_name, scale=1.0, threshold=None, screenshot=None
    ):
        if template_name == "icon_gift":
            return self._gift_match
        return None


class TestClaimGiftsHandleHome(unittest.TestCase):
    def test_handle_home_no_gift_sets_no_gifts_phase(self):
        adb = FakeAdb()
        page_detector = FakePageDetector(gift_match=None)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertTrue(task._completed)
        self.assertEqual([], adb.taps)

    def test_handle_home_gift_icon_taps_and_enters(self):
        adb = FakeAdb()
        gift_match = SimpleNamespace(box=(10, 20, 30, 40))
        page_detector = FakePageDetector(gift_match=gift_match)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertFalse(task._completed)
        self.assertEqual([gift_match.box], adb.taps)


class TestClaimGiftsCardRegister(unittest.TestCase):
    """测试礼物领取后的图鉴登录页处理。"""

    def test_handle_card_register_swipes_up(self):
        adb = FakeAdb()
        page_detector = FakePageDetector(gift_match=None)
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_card_register({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.swipes))
        start, end, _ = adb.swipes[0]
        self.assertEqual(start[0], end[0])
        self.assertGreater(start[1], end[1])


class FakeDetectedCard:
    """模拟 DetectedCard 用于测试"""

    def __init__(self, card_number=1, set_code="A1", rarity="1S", confidence=0.9):
        self.card_number = card_number
        self.set_code = set_code
        self.rarity = rarity
        self.confidence = confidence


class TestClaimGiftsPackOpeningResult(unittest.TestCase):
    """测试礼物盒领取后的开包结果页识别与落库行为。"""

    def test_pack_opening_result_triggers_recognize_once(self):
        """测试 pack_opening_result 首次触发识别"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        # Mock 依赖（直接设置内部属性绕过 property）
        task._pack_record_repo = Mock()
        task._card_repo = Mock()
        task._account_card_repo = Mock()
        task._account = SimpleNamespace(id=1, display_name="test_account")
        task._packs_opened_count = 0
        task._result_recognized = False

        # Mock card_recognizer
        fake_card = FakeDetectedCard(card_number=1, set_code="A1", rarity="1S")
        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [fake_card]

        # Mock map_detected_cards
        with patch(
            "ptcgp_auto_v2.tasks.pack_opening_task_base.map_detected_cards"
        ) as mock_map:
            mock_map.return_value = [
                {
                    "card_name": "妙蛙种子",
                    "rarity": "1S",
                    "card_id": 1,
                    "is_new": True,
                    "position": 1,
                    "confidence": 0.95,
                    "hash_similarity": 0.92,
                }
            ]

            # 首次处理 pack_opening_result
            result = task.handle_page("pack_opening_result", {"ocr_results": []})

            # 验证识别被调用
            task.card_recognizer.scan.assert_called_once()
            # 验证 map_detected_cards 被调用
            mock_map.assert_called_once()
            # 验证 pack_record_repo.create_for_account 被调用
            task._pack_record_repo.create_for_account.assert_called_once()
            # 验证结果标记为已识别
            self.assertTrue(task._result_recognized)
            self.assertTrue(result.success)

    def test_pack_opening_result_skips_recognize_on_second_entry(self):
        """测试 pack_opening_result 二次进入不重复识别"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        # Mock 依赖（直接设置内部属性绕过 property）
        task._pack_record_repo = Mock()
        task._card_repo = Mock()
        task._account_card_repo = Mock()
        task._account = SimpleNamespace(id=1, display_name="test_account")
        task._packs_opened_count = 0
        task._result_recognized = False

        # Mock card_recognizer
        fake_card = FakeDetectedCard(card_number=1, set_code="A1", rarity="1S")
        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [fake_card]

        # Mock map_detected_cards
        with patch(
            "ptcgp_auto_v2.tasks.pack_opening_task_base.map_detected_cards"
        ) as mock_map:
            mock_map.return_value = [
                {
                    "card_name": "妙蛙种子",
                    "rarity": "1S",
                    "card_id": 1,
                    "is_new": True,
                    "position": 1,
                    "confidence": 0.95,
                    "hash_similarity": 0.92,
                }
            ]

            # 首次处理
            task.handle_page("pack_opening_result", {"ocr_results": []})
            # 重置 mock 计数
            task.card_recognizer.scan.reset_mock()
            task._pack_record_repo.create_for_account.reset_mock()

            # 二次处理
            result = task.handle_page("pack_opening_result", {"ocr_results": []})

            # 验证识别没有被再次调用
            task.card_recognizer.scan.assert_not_called()
            # 验证落库没有被再次调用
            task._pack_record_repo.create_for_account.assert_not_called()
            self.assertTrue(result.success)

    def test_pack_opening_result_saves_with_gift_box_pack_type(self):
        """测试 pack_type 使用 gift_box 写入仓储"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = ClaimGiftsTask(adb, recognizer=None, page_detector=page_detector)

        # Mock 依赖（直接设置内部属性绕过 property）
        task._pack_record_repo = Mock()
        task._card_repo = Mock()
        task._account_card_repo = Mock()
        task._account = SimpleNamespace(id=1, display_name="test_account")
        task._packs_opened_count = 0
        task._result_recognized = False

        # Mock card_recognizer
        fake_card = FakeDetectedCard(card_number=1, set_code="A1", rarity="1S")
        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [fake_card]

        # Mock map_detected_cards
        with patch(
            "ptcgp_auto_v2.tasks.pack_opening_task_base.map_detected_cards"
        ) as mock_map:
            mock_map.return_value = [
                {
                    "card_name": "妙蛙种子",
                    "rarity": "1S",
                    "card_id": 1,
                    "is_new": True,
                    "position": 1,
                    "confidence": 0.95,
                    "hash_similarity": 0.92,
                }
            ]

            # 处理 pack_opening_result
            task.handle_page("pack_opening_result", {"ocr_results": []})

            # 验证 create_for_account 调用参数
            call_args = task._pack_record_repo.create_for_account.call_args
            # account_id 是位置参数，pack_type 是关键字参数
            self.assertEqual(call_args.args[0], 1)  # 第一个位置参数是 account_id
            self.assertEqual(call_args.kwargs["pack_type"], "gift_box")


if __name__ == "__main__":
    unittest.main()
