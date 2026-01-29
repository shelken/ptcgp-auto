# -*- coding: utf-8 -*-
"""
新账号初始化任务测试模块

测试任务注册、页面规则构建、状态机转换等基础功能。
"""

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.tasks.init_account import InitAccountPhase, InitAccountTask, _build_init_pages
from ptcgp_auto_v2.core.task_base import TaskRegistry, ResetType


class FakeAdb:
    """模拟 ADB 控制器"""

    def __init__(self):
        self.taps = []
        self.tap_points = []
        self.swipes = []
        self.inputs = []
        self._screen_width = 1080
        self._screen_height = 1920

    @property
    def screen_width(self):
        return self._screen_width

    @property
    def screen_height(self):
        return self._screen_height

    def tap(self, x, y):
        self.tap_points.append((x, y))

    def tap_center(self, box):
        """点击边界框中心"""
        # 处理字典类型 (来自 OCR 结果)
        if isinstance(box, dict):
            x = (box["x1"] + box["x2"]) // 2
            y = (box["y1"] + box["y2"]) // 2
        # 处理元组/命名空间类型 (来自模板匹配)
        elif isinstance(box, (tuple, list)):
            x = (box[0] + box[2]) // 2
            y = (box[1] + box[3]) // 2
        else:
            # 尝试从命名空间获取属性
            x = (box.x1 + box.x2) // 2 if hasattr(box, 'x1') else (box[0][0] + box[0][2]) // 2
            y = (box.y1 + box.y2) // 2 if hasattr(box, 'y1') else (box[0][1] + box[0][3]) // 2
        self.tap_points.append((x, y))

    def long_press(self, x, y, duration=1000):
        self.taps.append(("long_press", x, y, duration))

    def swipe(self, x1, y1, x2, y2, duration=500):
        """执行滑动操作"""
        self.swipes.append(((x1, y1), (x2, y2), duration))

    def input_text(self, text):
        self.inputs.append(text)

    def scaled_x(self, x):
        return int(x * self._screen_width / 1080)

    def scaled_y(self, y):
        return int(y * self._screen_height / 1920)


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

    def find_template_with_scale(self, template_name, scale=1.0, threshold=0.8, screenshot=None):
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
            "init_create_save",
            "init_account_link",
            "init_set_nickname",
            "init_nickname_input",
            "init_confirm_settings",
            "init_select_pack",
            "init_swipe_open",
            "init_next_step",
            "init_mission",
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
            InitAccountPhase.SET_BIRTHDAY,
            InitAccountPhase.TERMS_PRIVACY,
            InitAccountPhase.CREATE_SAVE,
            InitAccountPhase.ACCOUNT_LINK,
            InitAccountPhase.SET_NICKNAME,
            InitAccountPhase.SELECT_PACK,
            InitAccountPhase.SWIPE_OPEN,
            InitAccountPhase.MISSION_GUIDE,
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

    def test_initial_flags_are_false(self):
        """测试初始标志位为 False"""
        adb = FakeAdb()
        page_detector = FakePageDetector()
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        self.assertFalse(task._country_selected)
        self.assertFalse(task._birthday_set)
        self.assertFalse(task._terms_accepted)
        self.assertFalse(task._save_created)
        self.assertFalse(task._nickname_set)
        self.assertFalse(task._pack_selected)
        self.assertFalse(task._pack_opened)


class TestInitAccountConstants(unittest.TestCase):
    """测试任务常量"""

    def test_target_country_is_taiwan(self):
        """测试目标国家为台湾"""
        self.assertEqual(InitAccountTask.TARGET_COUNTRY, "台灣")

    def test_target_nickname_is_skn(self):
        """测试目标昵称为 skn"""
        self.assertEqual(InitAccountTask.TARGET_NICKNAME, "skn")

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

    def test_clicks_country_button_when_not_selected(self):
        """测试未选择国家时点击国家/地区按钮"""
        adb = FakeAdb()
        ocr_results = []
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._country_selected = False

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertEqual(len(adb.tap_points), 1)

    def test_selects_taiwan_when_found(self):
        """测试找到台湾时点击选择"""
        adb = FakeAdb()
        ocr_results = [{"text": "台灣", "box": {"x1": 100, "y1": 200, "x2": 200, "y2": 300}}]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_select_country({"ocr_results": ocr_results})

        self.assertTrue(result.success)


class TestHandleTermsPrivacy(unittest.TestCase):
    """测试条款与隐私页面处理"""

    def test_clicks_terms_button_first(self):
        """测试首先点击使用条款按钮"""
        adb = FakeAdb()
        ocr_results = [{"text": "使用條款", "box": {"x1": 100, "y1": 500, "x2": 300, "y2": 600}}]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._terms_clicked = False

        result = task._handle_terms_privacy({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertTrue(task._terms_clicked)

    def test_clicks_gray_yes_template(self):
        """测试点击灰色勾选图标"""
        adb = FakeAdb()
        ocr_results = []
        gray_yes_match = SimpleNamespace(box=(100, 800, 150, 850))
        page_detector = FakePageDetector(
            ocr_results=ocr_results,
            template_matches={"icon_gray_yes": gray_yes_match}
        )
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)
        task._terms_clicked = True
        task._privacy_clicked = True
        task._gray_yes_clicked = False

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
            ocr_results=ocr_results,
            template_matches={"icon_pencil": pencil_match}
        )
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_set_nickname({"ocr_results": ocr_results})

        self.assertTrue(result.success)

    def test_inputs_nickname_on_input_page(self):
        """测试在输入页面输入昵称"""
        adb = FakeAdb()
        ocr_results = [{"text": "OK", "box": {"x1": 800, "y1": 1500, "x2": 900, "y2": 1600}}]
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_nickname_input({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertEqual(adb.inputs, ["skn"])


class TestHandleSwipeOpen(unittest.TestCase):
    """测试滑动开包页面处理"""

    def test_swipes_horizontally(self):
        """测试横向滑动"""
        adb = FakeAdb()
        ocr_results = []
        page_detector = FakePageDetector(ocr_results=ocr_results)
        task = InitAccountTask(adb, recognizer=None, page_detector=page_detector)

        result = task._handle_swipe_open({"ocr_results": ocr_results})

        self.assertTrue(result.success)
        self.assertEqual(len(adb.swipes), 1)


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
        self.assertTrue(task._pack_opened)


if __name__ == "__main__":
    unittest.main()
