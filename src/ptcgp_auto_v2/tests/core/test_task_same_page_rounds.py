# -*- coding: utf-8 -*-
from ptcgp_auto_v2.core.task_base import Task
from ptcgp_auto_v2.utils.action_result import ActionResult


class SequencePageDetector:
    """按预设序列返回页面检测结果。"""

    def __init__(self, pages: list[str]):
        self.pages = pages
        self.index = 0

    def detect(self, lossless: bool = False):
        del lossless
        if self.index < len(self.pages):
            page_name = self.pages[self.index]
            self.index += 1
        else:
            page_name = self.pages[-1]
        return page_name, {"ocr_results": []}


class DummySamePageTask(Task):
    """用于验证连续相同页面收敛。"""

    task_type = "dummy_same_page"
    pages = []

    def __init__(self, pages: list[str], max_same_page_rounds: int = 3):
        self.page_detector = SequencePageDetector(pages)
        self.adb = None
        self.recognizer = None
        self._completed = False
        self._handlers = {}
        self._stop_event = None
        self._account = None
        self._hook_context = None
        self._preserve_last_completed_at = False
        self.max_iterations = 10
        self.max_same_page_rounds = max_same_page_rounds

    def is_completed(self) -> bool:
        return self._completed

    def handle_page(self, page_name: str, page_info: dict):
        del page_name, page_info
        return ActionResult.wait(0.0)

    def handle_unknown_page(self, page_info):
        del page_info
        return ActionResult.wait(0.0)


def test_execute_should_fail_when_same_known_page_repeats():
    """连续相同已知页面达到阈值时，应直接失败。"""
    task = DummySamePageTask(
        pages=["gift_select_card", "gift_select_card", "gift_select_card"],
        max_same_page_rounds=3,
    )

    result = task.execute()

    assert result.success is False
    assert result.error == "连续 3 次停留在同一页面: gift_select_card"


def test_execute_should_fail_when_same_unknown_page_repeats():
    """连续相同未知页面达到阈值时，也应直接失败。"""
    task = DummySamePageTask(
        pages=["unknown", "unknown"],
        max_same_page_rounds=2,
    )

    result = task.execute()

    assert result.success is False
    assert result.error == "连续 2 次停留在同一页面: unknown"


def test_execute_should_reset_count_after_page_changes():
    """页面变化后应重置连续计数，不应误判失败。"""
    task = DummySamePageTask(
        pages=["page_a", "page_a", "page_b", "page_b", "page_c"],
        max_same_page_rounds=3,
    )
    task.max_iterations = 5

    result = task.execute()

    assert result.success is False
    assert result.error == "超过最大迭代次数 5"
