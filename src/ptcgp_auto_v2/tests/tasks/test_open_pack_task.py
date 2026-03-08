import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from ptcgp_auto_v2.tasks.open_pack import HOME_CHECK_THRESHOLD, OpenPackTask
from ptcgp_auto_v2.infra.yolo_card_recognizer import DetectedCard
from ptcgp_auto_v2.utils.gesture import scroll_until_template
from ptcgp_auto_v2.config.constants import DEFAULT_TEMPLATE_THRESHOLD
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class FakePageDetector:
    def __init__(
        self,
        free_match=None,
        pack_match=None,
        screenshot=None,
        capture_sequence=None,
        template_sequence=None,
    ):
        self._free_match = free_match
        self._pack_match = pack_match
        self._last_screenshot = screenshot if screenshot is not None else object()
        self._last_ocr_results = []
        self._capture_sequence = capture_sequence or []
        self._capture_index = 0
        self._template_sequence = template_sequence or []
        self._template_index = 0
        self.adb = FakeAdb()

    def get_last_page_context(self):
        return self._last_screenshot, self._last_ocr_results

    def capture(self, screenshot=None):
        if self._capture_index < len(self._capture_sequence):
            item = self._capture_sequence[self._capture_index]
            self._capture_index += 1
            self._last_screenshot = item[0]
            self._last_ocr_results = item[1]
            return item
        self._last_screenshot = None
        self._last_ocr_results = []
        return None, []

    def find_template_with_scale(
        self,
        template_name,
        scale=1.0,
        threshold=DEFAULT_TEMPLATE_THRESHOLD,
        screenshot=None,
    ):
        if template_name == "icon_free_pack_available":
            return self._free_match
        if template_name == "icon_pack_open":
            return self._pack_match
        if self._template_index < len(self._template_sequence):
            match = self._template_sequence[self._template_index]
            self._template_index += 1
            return match
        return None


class TestOpenPackConstantsCleanup(unittest.TestCase):
    """测试清理死代码常量"""

    def test_no_dead_skip_reason_constants(self):
        """验证已移除无用的跳过原因常量"""
        import ptcgp_auto_v2.tasks.open_pack as open_pack_module

        # 确保未使用的常量已被移除
        self.assertFalse(
            hasattr(open_pack_module, "SKIP_REASON_NO_ACCOUNT_ID"),
            "应移除 SKIP_REASON_NO_ACCOUNT_ID 常量",
        )
        self.assertFalse(
            hasattr(open_pack_module, "SKIP_REASON_NO_PACK_CONFIG"),
            "应移除 SKIP_REASON_NO_PACK_CONFIG 常量",
        )

    def test_home_check_threshold_exists(self):
        """验证仍在使用的常量存在"""
        import ptcgp_auto_v2.tasks.open_pack as open_pack_module

        self.assertTrue(
            hasattr(open_pack_module, "HOME_CHECK_THRESHOLD"),
            "HOME_CHECK_THRESHOLD 常量应存在",
        )
        self.assertEqual(open_pack_module.HOME_CHECK_THRESHOLD, 3)


class TestOpenPackHandleHome(unittest.TestCase):
    def test_handle_home_no_free_pack_sets_no_free_pack_phase(self):
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        for _ in range(HOME_CHECK_THRESHOLD):
            result = task._handle_home({})
            self.assertTrue(result.success)

        self.assertTrue(task._completed)
        self.assertEqual(HOME_CHECK_THRESHOLD, task._home_check_count)
        self.assertEqual([], adb.taps)

    def test_handle_home_free_pack_prefers_pack_open_icon(self):
        adb = FakeAdb()
        free_match = SimpleNamespace(box=(10, 20, 30, 40))
        pack_match = SimpleNamespace(box=(50, 60, 70, 80))
        page_detector = FakePageDetector(free_match=free_match, pack_match=pack_match)
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)
        task._home_check_count = 2

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertEqual(0, task._home_check_count)
        self.assertFalse(task._completed)
        self.assertEqual([pack_match.box], adb.taps)

    def test_handle_home_free_pack_skips_free_pack_icon_when_no_open_icon(self):
        adb = FakeAdb()
        free_match = SimpleNamespace(box=(1, 2, 3, 4))
        page_detector = FakePageDetector(free_match=free_match, pack_match=None)
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)
        task._home_check_count = 1

        result = task._handle_home({})

        self.assertTrue(result.success)
        self.assertEqual(0, task._home_check_count)
        self.assertFalse(task._completed)
        self.assertEqual([], adb.taps)


class TestGestureTemplateFlows(unittest.TestCase):
    def test_scroll_until_template_hits_match(self):
        match = SimpleNamespace(box=(1, 2, 3, 4))
        capture_sequence = [
            (object(), [{"text": "alpha"}]),
            (object(), [{"text": "beta"}]),
        ]
        page_detector = FakePageDetector(
            capture_sequence=capture_sequence,
            template_sequence=[None, match],
        )
        result = scroll_until_template(
            page_detector,
            template_name="target",
            scale=1.0,
            max_attempts=3,
            base_distance_y=384,
            wait=0.1,
        )

        self.assertIsNotNone(result)
        self.assertEqual([match.box], page_detector.adb.taps)

    def test_scroll_until_template_stops_on_repeat_signature(self):
        capture_sequence = [
            (object(), [{"text": "same"}]),
            (object(), [{"text": "same"}]),
        ]
        page_detector = FakePageDetector(
            capture_sequence=capture_sequence,
            template_sequence=[None, None],
        )
        result = scroll_until_template(
            page_detector,
            template_name="target",
            scale=1.0,
            max_attempts=3,
            base_distance_y=384,
            wait=0.1,
        )

        self.assertIsNone(result)
        self.assertEqual([], page_detector.adb.taps)


class TestOpenPackRecognizeCards(unittest.TestCase):
    def test_recognize_cards_creates_account_card_records(self):
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        task.bind_account(SimpleNamespace(id=1, display_name="tester"))
        task._target_pack = {"set_code": "A1", "booster_name": "Test"}

        high_card = SimpleNamespace(id=101, name="High", rarity="SR")
        low_card = SimpleNamespace(id=202, name="Low", rarity="C")
        task._card_repo = Mock()
        task._card_repo.get_card_by_set_and_number.side_effect = [high_card, low_card]

        task._pack_record_repo = Mock()
        task._account_card_repo = Mock()

        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [
            DetectedCard(
                set_code="A1",
                card_number=1,
                confidence=0.9,
                similarity=0.85,
                bbox=(0, 0, 1, 1),
                center=(0.0, 0.0),
            ),
            DetectedCard(
                set_code="A1",
                card_number=2,
                confidence=0.7,
                similarity=0.4,
                bbox=(0, 0, 1, 1),
                center=(0.0, 0.0),
            ),
        ]

        task._recognize_cards()

        task._account_card_repo.upsert.assert_called_once_with(
            account_id=1,
            card_id=101,
            count=1,
            yolo_conf=0.9,
            hash_similarity=0.85,
        )

    def test_recognize_cards_uses_high_rarity_saver_for_notification(self):
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        task.bind_account(SimpleNamespace(id=1, display_name="tester"))
        task._target_pack = {"set_code": "A1", "booster_name": "Test"}

        high_card = SimpleNamespace(id=101, name="High", rarity="SR")
        task._card_repo = Mock()
        task._card_repo.get_card_by_set_and_number.return_value = high_card
        task._pack_record_repo = Mock()
        task._account_card_repo = Mock()

        task.card_recognizer = Mock()
        task.card_recognizer.scan.return_value = [
            DetectedCard(
                set_code="A1",
                card_number=1,
                confidence=0.9,
                similarity=0.85,
                bbox=(0, 0, 1, 1),
                center=(0.0, 0.0),
            )
        ]

        with patch(
            "ptcgp_auto_v2.tasks.pack_opening_task_base.get_notifier"
        ) as mock_get_notifier:
            with patch(
                "ptcgp_auto_v2.tasks.pack_opening_task_base.save_high_rarity_cards"
            ) as mock_save:
                mock_get_notifier.return_value = Mock()
                task._recognize_cards()

        self.assertTrue(mock_save.called)
        kwargs = mock_save.call_args.kwargs
        self.assertIn("notifier", kwargs)
        self.assertIn("rows", kwargs)
        # 基类使用 get_rare_card_notify_message() 获取中文通知消息
        self.assertEqual("开包获得稀有卡牌", kwargs.get("notify_message"))


class TestOpenPackExtractPackPoints(unittest.TestCase):
    """测试开包点数提取与落库"""

    def test_extract_pack_points_should_use_set_code(self):
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        task.bind_account(SimpleNamespace(id=1, display_name="tester"))
        task._target_pack = {"set_code": "A1", "booster_name": "Test"}
        task._pack_point_repo = Mock()

        task._extract_pack_points([{"text": "1,230 pt"}])

        task._pack_point_repo.upsert_points.assert_called_once_with(1, "A1", 1230)


class TestOpenPackPrepareResourcesFailure(unittest.TestCase):
    """测试资源准备失败状态传播"""

    @patch("ptcgp_auto_v2.db.repositories.AccountPackConfigRepository")
    def test_on_start_sets_failed_when_prepare_resources_fails(self, mock_repo_cls):
        """测试资源准备失败时设置 _failed 和 _fail_reason"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        # 绑定账号
        task.bind_account(SimpleNamespace(id=1, display_name="tester"))

        # Mock 配置仓库返回有配置
        mock_config_repo = Mock()
        mock_config = Mock()
        mock_config.set_code = "A1"
        mock_config.booster_name = "Test Pack"
        mock_config_repo.get_by_account_and_type.return_value = mock_config
        mock_repo_cls.return_value = mock_config_repo

        # Mock _prepare_image_resources 返回失败
        task._prepare_image_resources = Mock(return_value=False)

        # 调用 on_start
        task.on_start()

        # 验证失败状态
        self.assertTrue(task._failed)
        self.assertEqual(task._fail_reason, "准备卡包图片资源失败")
        self.assertTrue(task.is_completed())

    @patch("ptcgp_auto_v2.db.repositories.AccountPackConfigRepository")
    def test_handle_page_returns_fail_when_resources_failed(self, mock_repo_cls):
        """测试资源准备失败后 handle_page 返回失败结果"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = OpenPackTask(adb, recognizer=None, page_detector=page_detector)

        task.bind_account(SimpleNamespace(id=1, display_name="tester"))

        # Mock 配置仓库返回有配置
        mock_config_repo = Mock()
        mock_config = Mock()
        mock_config.set_code = "A1"
        mock_config.booster_name = "Test Pack"
        mock_config_repo.get_by_account_and_type.return_value = mock_config
        mock_repo_cls.return_value = mock_config_repo

        # Mock _prepare_image_resources 返回失败
        task._prepare_image_resources = Mock(return_value=False)

        task.on_start()

        # 验证 handle_page 返回失败
        result = task.handle_page("game_home_main", {"ocr_results": []})
        self.assertFalse(result.success)
        self.assertEqual(result.error, "准备卡包图片资源失败")


if __name__ == "__main__":
    unittest.main()
