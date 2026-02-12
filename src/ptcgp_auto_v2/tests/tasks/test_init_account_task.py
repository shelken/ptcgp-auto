# -*- coding: utf-8 -*-
"""
新账号初始化任务测试模块

测试任务注册、页面规则构建、状态机转换等基础功能。
"""

import sys
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.init_account import (
    InitAccountPhase,
    InitAccountTask,
    _build_init_pages,
)
from ptcgp_auto_v2.core.task_base import ActionResult, TaskRegistry, ResetType
from ptcgp_auto_v2.tests.fake_adb import FakeAdb


class MockRecognizer(tuple):
    """模拟识别器 (ocr_engine, template_matcher)"""

    def __new__(cls):
        ocr = MockOcr()
        template_matcher = MockTemplateMatcher()
        return super().__new__(cls, (ocr, template_matcher))


class MockOcr:
    """模拟 OCR 引擎"""

    def recognize(self, screenshot):
        return []


class MockTemplateMatcher:
    """模拟模板匹配器"""

    def match(self, screenshot, template_name, threshold=0.8):
        return None


class FakePageDetector:
    """模拟页面检测器"""

    def __init__(
        self,
        screenshot=None,
        ocr_results=None,
        template_matches=None,
    ):
        self._last_screenshot = screenshot if screenshot is not None else object()
        self._last_ocr_results = ocr_results or []
        self._template_matches = template_matches or {}
        self._template_call_count = {}
        self.adb = FakeAdb()

    def get_last_page_context(self):
        return self._last_screenshot, self._last_ocr_results

    def capture(self, screenshot=None):
        return self._last_screenshot, self._last_ocr_results

    def find_template_with_scale(
        self, template_name, scale=1.0, threshold=0.8, screenshot=None
    ):
        count = self._template_call_count.get(template_name, 0)
        self._template_call_count[template_name] = count + 1

        matches = self._template_matches.get(template_name)
        if matches is None:
            return None
        if isinstance(matches, list):
            if count < len(matches):
                return matches[count]
            return None
        return matches

    def find_template(self, template_name, threshold=0.8, screenshot=None):
        """查找模板（不带scale）"""
        return self.find_template_with_scale(
            template_name, scale=1.0, threshold=threshold, screenshot=screenshot
        )


class TestInitAccountRegistration(unittest.TestCase):
    """测试任务注册"""

    def test_task_is_registered(self):
        """测试任务已正确注册到注册表"""
        self.assertTrue(TaskRegistry.is_registered("init_account"))

    def test_task_type_is_set(self):
        """测试任务类型已正确设置"""
        task_class = TaskRegistry.get("init_account")
        self.assertEqual(task_class.task_type, "init_account")

    def test_reset_type_is_once(self):
        """测试重置类型为 ONCE（一次性任务）"""
        task_class = TaskRegistry.get("init_account")
        self.assertEqual(task_class.reset_type, ResetType.ONCE)


class TestInitAccountPages(unittest.TestCase):
    """测试页面规则构建"""

    def test_build_init_pages_returns_list(self):
        """测试页面规则构建返回列表"""
        pages = _build_init_pages()
        self.assertIsInstance(pages, list)
        self.assertGreater(len(pages), 0)

    def test_build_init_pages_contains_required_pages(self):
        """测试页面规则包含必需的页面"""
        pages = _build_init_pages()
        page_names = {p["name"] for p in pages}

        required_pages = [
            "init_select_country",
            "init_terms_privacy",
            "init_data_use",
            "init_create_save",
            "init_account_link",
            "init_set_nickname",
            "init_nickname_input",
            "init_confirm_settings",
            "init_select_pack",
            "init_decide",
            "init_swipe_open",
            "init_next_step",
            "init_open_pack",
            "init_tap_to_flip",
            "init_enjoy",
            "pack_opening_result",
            "pack_card_register",
            "pack_opening_card",
        ]

        for page in required_pages:
            self.assertIn(page, page_names, f"缺少必需的页面: {page}")

    def test_page_rules_have_required_fields(self):
        """测试页面规则包含必需字段"""
        pages = _build_init_pages()

        for page in pages:
            self.assertIn("name", page)
            self.assertIn("priority", page)


class TestInitAccountPhase(unittest.TestCase):
    """测试状态机阶段"""

    def test_phase_enum_values(self):
        """测试状态机阶段枚举值"""
        phases = list(InitAccountPhase)
        expected_phases = [
            InitAccountPhase.INIT,
            InitAccountPhase.SELECT_COUNTRY,
            InitAccountPhase.TERMS_PRIVACY,
            InitAccountPhase.CREATE_SAVE,
            InitAccountPhase.ACCOUNT_LINK,
            InitAccountPhase.SET_NICKNAME,
            InitAccountPhase.SELECT_PACK,
            InitAccountPhase.SWIPE_OPEN,
            InitAccountPhase.COMPLETED,
        ]

        for phase in expected_phases:
            self.assertIn(phase, phases)


class TestInitAccountTaskInit(unittest.TestCase):
    """测试任务初始化"""

    def test_initial_phase_is_init(self):
        """测试初始阶段为 INIT"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        self.assertEqual(task._phase, InitAccountPhase.INIT)


class TestInitAccountConstants(unittest.TestCase):
    """测试任务常量"""

    def test_allowed_countries_is_list(self):
        """测试允许国家列表为列表类型"""
        self.assertIsInstance(InitAccountTask.ALLOWED_COUNTRIES, list)
        self.assertGreater(len(InitAccountTask.ALLOWED_COUNTRIES), 0)

    def test_allowed_countries_contains_expected(self):
        """测试允许国家列表包含预期国家"""
        expected_countries = ["香港", "台湾", "日本", "新加坡"]
        for country in expected_countries:
            self.assertIn(country, InitAccountTask.ALLOWED_COUNTRIES)

    def test_target_country_is_configurable(self):
        """测试目标国家可配置"""
        # 目标国家可以通过修改类属性来配置
        self.assertIsInstance(InitAccountTask.TARGET_COUNTRY, str)
        self.assertGreater(len(InitAccountTask.TARGET_COUNTRY), 0)

    def test_target_nickname_is_skn(self):
        """测试目标昵称为 skn"""
        self.assertEqual(InitAccountTask.NICKNAME_PREFIX, "skn")

    def test_birth_year_offset_is_20(self):
        """测试出生年份偏移为 20"""
        self.assertEqual(InitAccountTask.BIRTH_YEAR_OFFSET, 20)

    def test_birth_month_is_2(self):
        """测试出生月份为 2"""
        self.assertEqual(InitAccountTask.BIRTH_MONTH, 2)


class TestInitAccountIsCompleted(unittest.TestCase):
    """测试任务完成判断"""

    def test_is_completed_when_phase_is_completed(self):
        """测试阶段为 COMPLETED 时返回 True"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = InitAccountPhase.COMPLETED

        self.assertTrue(task.is_completed())

    def test_is_not_completed_when_phase_is_init(self):
        """测试阶段为 INIT 时返回 False"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = InitAccountPhase.INIT

        self.assertFalse(task.is_completed())


class TestHandleSelectCountry(unittest.TestCase):
    """测试选择国家/地区页面处理"""

    def test_clicks_country_button_to_open_list(self):
        """测试点击国家/地区按钮打开列表"""
        adb = FakeAdb()
        ocr_results = [
            {"text": "國家/地區", "box": {"x1": 100, "y1": 200, "x2": 300, "y2": 300}}
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        # 点击后应该标记列表已打开
        self.assertTrue(task._is_action_done("select_country_list_opened"))

    def test_selects_target_country_when_found(self):
        """测试找到目标国家时点击选择"""
        adb = FakeAdb()
        # 使用实际的目标国家进行测试
        target_country = InitAccountTask.TARGET_COUNTRY
        ocr_results = [
            {
                "text": target_country,
                "box": {"x1": 100, "y1": 200, "x2": 200, "y2": 300},
            }
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._mark_action_done("select_country_list_opened")

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        # 验证国家选择已标记为完成
        self.assertTrue(task._is_action_done("select_country_country_clicked"))

    @patch("ptcgp_auto_v2.tasks.init_account.tap_ok")
    def test_resets_country_selection_flags_after_ok(self, tap_ok_mock):
        """测试点击 OK 后会重置国家选择标记，便于下轮重试"""
        adb = FakeAdb()
        page_detector = FakePageDetector(ocr_results=[])
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        task._mark_action_done("select_country_list_opened")
        task._mark_action_done("select_country_country_clicked")
        task._mark_action_done("select_country_year_clicked")
        task._mark_action_done("select_country_year_selected")
        task._mark_action_done("select_country_month_clicked")
        task._mark_action_done("select_country_month_selected")
        tap_ok_mock.return_value = ActionResult.ok(wait=1.0)

        result = task._handle_select_country({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertFalse(task._is_action_done("select_country_list_opened"))
        self.assertFalse(task._is_action_done("select_country_country_clicked"))

    @patch("ptcgp_auto_v2.tasks.init_account.tap_ok")
    def test_keeps_country_selection_flags_on_country_form(self, tap_ok_mock):
        """测试主表单点击 OK 时不重置国家标记，避免重复打开国家列表。"""
        adb = FakeAdb()
        ocr_results = [
            {"text": "年", "box": {"x1": 300, "y1": 1300, "x2": 340, "y2": 1350}},
            {"text": "月", "box": {"x1": 700, "y1": 1300, "x2": 740, "y2": 1350}},
            {"text": "OK", "box": {"x1": 500, "y1": 1600, "x2": 580, "y2": 1680}},
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        task._mark_action_done("select_country_list_opened")
        task._mark_action_done("select_country_country_clicked")
        task._mark_action_done("select_country_year_clicked")
        task._mark_action_done("select_country_year_selected")
        task._mark_action_done("select_country_month_clicked")
        task._mark_action_done("select_country_month_selected")
        tap_ok_mock.return_value = ActionResult.ok(wait=1.0)

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertTrue(task._is_action_done("select_country_list_opened"))
        self.assertTrue(task._is_action_done("select_country_country_clicked"))

    @patch("ptcgp_auto_v2.tasks.init_account.tap_ok")
    @patch("ptcgp_auto_v2.tasks.init_account.tap_text_exact")
    def test_country_list_overlay_should_tap_country_then_ok(
        self, tap_text_exact_mock, tap_ok_mock
    ):
        """国家列表弹层（含 X）应优先点击允许国家，再点击 OK。"""
        adb = FakeAdb()
        ocr_results = [
            {
                "text": "選擇國家/地區",
                "box": {"x1": 200, "y1": 150, "x2": 800, "y2": 250},
            },
            {"text": "香港", "box": {"x1": 450, "y1": 350, "x2": 620, "y2": 420}},
            {"text": "OK", "box": {"x1": 480, "y1": 1600, "x2": 600, "y2": 1680}},
            {"text": "X", "box": {"x1": 980, "y1": 1800, "x2": 1040, "y2": 1860}},
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        def _tap_text_exact_side_effect(_adb, _ocr, patterns, wait=1.0):
            if patterns == ["香港"]:
                return ActionResult.ok(wait=wait)
            return None

        tap_text_exact_mock.side_effect = _tap_text_exact_side_effect
        tap_ok_mock.return_value = ActionResult.ok(wait=1.0)

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertTrue(tap_text_exact_mock.called)
        self.assertTrue(tap_ok_mock.called)


class TestHandleTermsPrivacy(unittest.TestCase):
    """测试条款与隐私页面处理"""

    def test_marks_terms_action_done(self):
        """测试标记条款按钮已点击"""
        adb = FakeAdb()
        ocr_results = [
            {"text": "使用條款", "box": {"x1": 100, "y1": 500, "x2": 300, "y2": 600}}
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._phase = InitAccountPhase.TERMS_PRIVACY

        result = task._handle_terms_privacy({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        # 验证操作已被标记为完成
        self.assertTrue(task._is_action_done("terms_privacy_terms_clicked"))

    def test_clicks_gray_yes_template(self):
        """测试点击灰色勾选图标"""
        adb = FakeAdb()
        ocr_results = []
        # 使用元组格式，与实际代码中的 box 格式一致
        gray_yes_match = (100, 800, 150, 850)
        page_detector = FakePageDetector(
            ocr_results=ocr_results, template_matches={"icon_gray_yes": gray_yes_match}
        )
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        # 标记条款和隐私已点击，让流程走到点击灰色图标
        task._mark_action_done("terms_privacy_terms_clicked")
        task._mark_action_done("terms_privacy_privacy_clicked")

        result = task._handle_terms_privacy({"ocr_results": ocr_results})

        self.assertTrue(result.success)


class TestHandleSetNickname(unittest.TestCase):
    """测试设置昵称页面处理"""

    def test_clicks_pencil_icon(self):
        """测试点击铅笔图标"""
        adb = FakeAdb()
        ocr_results = []
        pencil_match = SimpleNamespace(box=(500, 600, 560, 660))
        page_detector = FakePageDetector(
            ocr_results=ocr_results, template_matches={"icon_pencil": pencil_match}
        )
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._account = SimpleNamespace(id=1)

        result = task._handle_set_nickname({"ocr_results": ocr_results})

        self.assertTrue(result.success)

    def test_skips_when_nickname_visible(self):
        """测试检测到昵称已设置时跳过输入"""
        adb = FakeAdb()
        # 注意：现在使用精确匹配，所以必须是完整的 "skn1"
        ocr_results = [
            {"text": "skn1", "box": {"x1": 800, "y1": 1500, "x2": 900, "y2": 1600}}
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._account = SimpleNamespace(id=1)

        result = task._handle_set_nickname({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        # 检测到昵称后直接点击 OK，不需要再点击铅笔

    def test_handles_nickname_warning(self):
        """测试检测到昵称异常提示时清空重输"""
        adb = FakeAdb()
        # 模拟异常提示 "請勿使用本名"
        ocr_results = [
            {
                "text": "請勿使用本名",
                "box": {"x1": 500, "y1": 1000, "x2": 700, "y2": 1100},
            }
        ]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._account = SimpleNamespace(id=1)

        result = task._handle_set_nickname({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        # 验证输入了正确的昵称
        self.assertIn("skn1", adb.inputs, "应该输入了目标昵称")


class TestHandleSwipeOpen(unittest.TestCase):
    """测试滑动开包页面处理"""

    def test_swipes_horizontally(self):
        """测试横向滑动（调用开包通用工具）"""
        adb = FakeAdb()
        ocr_results = []
        page_detector = FakePageDetector(ocr_results=ocr_results)
        recognizer = MockRecognizer()
        task = InitAccountTask(adb, recognizer=recognizer, page_detector=page_detector)

        result = task._handle_swipe_open({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertEqual(1, len(adb.swipes))
        start, end, _ = adb.swipes[0]
        self.assertGreater(end[0], start[0])
        self.assertEqual(start[1], end[1])


class TestHandleEnjoy(unittest.TestCase):
    """测试完成页面处理"""

    def test_sets_phase_to_completed(self):
        """测试将阶段设置为 COMPLETED"""
        adb = FakeAdb()
        ocr_results = []
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_enjoy({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertEqual(task._phase, InitAccountPhase.COMPLETED)


class TestHandleHomeFallback(unittest.TestCase):
    """测试主页兜底完成逻辑。"""

    def test_handle_page_should_not_complete_on_home_without_favorite_marker(self):
        """未到最终引导阶段时，主页不应直接判定完成。"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task.handle_page("game_home_main", {"ocr_results": []})

        self.assertTrue(result.success)
        self.assertNotEqual(task._phase, InitAccountPhase.COMPLETED)

    def test_handle_page_should_complete_after_home_hits_with_favorite_marker(self):
        """完成“喜欢卡牌”后，连续8次主页应触发兜底完成。"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._mark_action_done("after_favorite_card")

        for _ in range(7):
            result = task.handle_page("game_home_main", {"ocr_results": []})
            self.assertTrue(result.success)
            self.assertNotEqual(task._phase, InitAccountPhase.COMPLETED)

        result = task.handle_page("game_home_main", {"ocr_results": []})
        self.assertTrue(result.success)
        self.assertEqual(task._phase, InitAccountPhase.COMPLETED)

    def test_handle_page_should_reset_home_counter_after_leaving_home(self):
        """主页计数应为连续计数，离开主页后需要清零。"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._mark_action_done("after_favorite_card")

        task.handle_page("game_home_main", {"ocr_results": []})
        task.handle_page("game_home_main", {"ocr_results": []})
        self.assertEqual(task._action_cache.get("home_consecutive_count"), 2)

        task.handle_page("init_open_pack", {"ocr_results": []})
        self.assertIsNone(task._action_cache.get("home_consecutive_count"))


class TestHandleSelectFavoriteCard(unittest.TestCase):
    """测试选择喜欢的卡牌页面处理"""

    def test_uses_card_pick_helper(self):
        """测试调用选卡共用助手"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        with patch(
            "ptcgp_auto_v2.tasks.init_account.tap_favorite_card",
            create=True,
            return_value=ActionResult.ok(wait=0.5),
        ) as mock_helper:
            result = task._handle_select_favorite_card({"ocr_results": []})

        self.assertTrue(result.success)
        self.assertTrue(task._is_action_done("after_favorite_card"))
        mock_helper.assert_called_once_with(adb, wait=1.0)


class TestHandleUnknownPage(unittest.TestCase):
    """测试未知页面兜底点击策略。"""

    @patch("ptcgp_auto_v2.tasks.init_account.quick_tap")
    def test_uses_three_fallback_points(self, quick_tap_mock):
        """未知页面应按三点位顺序快速点击。"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        quick_tap_mock.return_value = ActionResult.ok(wait=0.5)

        result = task.handle_unknown_page({"ocr_results": []})

        self.assertTrue(result.success)
        quick_tap_mock.assert_called_once_with(
            adb,
            tap_points=[
                (adb.center_x(), adb.scaled_y(10)),
                (adb.center_x(), adb.center_y()),
                (adb.scaled_x(960), adb.scaled_y(1740)),
            ],
            times=1,
            wait=0.5,
        )


if __name__ == "__main__":
    unittest.main()
