# -*- coding: utf-8 -*-
"""manage_friendship 好友图标状态测试。"""

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks import manage_friendship
from ptcgp_auto_v2.tasks.manage_friendship import ManageFriendshipTask
from ptcgp_auto_v2.tasks.utils.friend_status_icons import friend_status_by_icons


class FakePageDetector:
    def __init__(self, matches=None):
        self.matches = matches or {}
        self.find_calls = []

    def find_template_with_scale(self, template_name, *, scale, threshold):
        self.find_calls.append((template_name, scale, threshold))
        return self.matches.get((template_name, scale))


def _build_task(page_detector):
    task = ManageFriendshipTask.__new__(ManageFriendshipTask)
    task.page_detector = page_detector
    return task


def test_friend_status_by_icons_reads_two_icons_and_two_scales_once():
    page_detector = FakePageDetector(
        {
            ("icon_green_yes", 1.0): "green-1x",
            ("icon_green_yes", 0.8): "green-08",
            ("icon_red_no", 0.8): "red-08",
        }
    )

    status = friend_status_by_icons(page_detector)

    assert status.green_1x == "green-1x"
    assert status.red_1x is None
    assert status.green_08 == "green-08"
    assert status.red_08 == "red-08"
    assert page_detector.find_calls == [
        ("icon_green_yes", 1.0, 0.8),
        ("icon_red_no", 1.0, 0.8),
        ("icon_green_yes", 0.8, 0.8),
        ("icon_red_no", 0.8, 0.8),
    ]


def test_friend_icon_status_preserves_manage_friendship_state_semantics():
    pending_detector = FakePageDetector(
        {
            ("icon_green_yes", 1.0): object(),
            ("icon_red_no", 1.0): object(),
        }
    )
    pending_task = _build_task(pending_detector)

    assert pending_task._is_pending_reply_by_icons() is True
    assert pending_task._is_already_friend_by_icons() is False
    assert pending_task._is_friend_confirmed_by_icons() is False

    already_detector = FakePageDetector({("icon_green_yes", 0.8): object()})
    already_task = _build_task(already_detector)

    assert already_task._is_pending_reply_by_icons() is False
    assert already_task._is_already_friend_by_icons() is True
    assert already_task._is_friend_confirmed_by_icons() is True

    blocked_detector = FakePageDetector(
        {
            ("icon_green_yes", 0.8): object(),
            ("icon_red_no", 0.8): object(),
        }
    )
    blocked_task = _build_task(blocked_detector)

    assert blocked_task._is_pending_reply_by_icons() is False
    assert blocked_task._is_already_friend_by_icons() is True
    assert blocked_task._is_friend_confirmed_by_icons() is False


def test_add_sending_result_reuses_one_icon_status_batch():
    page_detector = FakePageDetector(
        {
            ("icon_green_yes", 0.8): object(),
        }
    )
    task = _build_task(page_detector)
    task.adb = object()
    task._save_target_nickname = lambda req, ocr_results: None
    task._complete_add_already_friend_request = lambda req: None
    task._refresh_requests = lambda: None
    task._close_modal = lambda wait: ActionResult.ok(wait=wait)
    req = type("Request", (), {"id": 1, "to_account_id": None})()

    result = task._handle_add_sending_result(req, {"ocr_results": []})

    assert result == ActionResult.ok(wait=0.8)
    assert page_detector.find_calls == [
        ("icon_green_yes", 1.0, 0.8),
        ("icon_red_no", 1.0, 0.8),
        ("icon_green_yes", 0.8, 0.8),
        ("icon_red_no", 0.8, 0.8),
    ]


def test_tap_green_yes_prefers_1x_then_falls_back_to_08(monkeypatch):
    page_detector = FakePageDetector()
    task = _build_task(page_detector)
    calls = []

    def fake_tap_template_with_scale(page_detector_arg, template_name, *, scale, threshold, wait):
        calls.append((page_detector_arg, template_name, scale, threshold, wait))
        if scale == 0.8:
            return ActionResult.ok(wait=wait)
        return None

    monkeypatch.setattr(
        manage_friendship, "tap_template_with_scale", fake_tap_template_with_scale
    )

    result = task._tap_green_yes(wait=0.7)

    assert result == ActionResult.ok(wait=0.7)
    assert calls == [
        (page_detector, "icon_green_yes", 1.0, 0.8, 0.7),
        (page_detector, "icon_green_yes", 0.8, 0.8, 0.7),
    ]
