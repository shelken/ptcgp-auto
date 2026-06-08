# -*- coding: utf-8 -*-
"""公共页面处理器测试。"""

from ptcgp_auto_v2.utils.common_handlers import build_common_handlers


class _Adb:
    def __init__(self):
        self.tapped_boxes: list[tuple[int, int, int, int]] = []
        self.restarted_apps: list[str] = []
        self.address = "127.0.0.1:5555"

    def tap_center(self, box):
        self.tapped_boxes.append(box)

    def restart_app(self, package_name: str):
        self.restarted_apps.append(package_name)


class _PageDetector:
    pass


def test_privacy_policy_handler_taps_accept_button_before_ok():
    """隐私政策同意页必须先点同意按钮，不能继续点 OK。"""
    adb = _Adb()
    handlers = build_common_handlers(adb, _PageDetector())
    agree_box = (200, 820, 480, 880)
    ok_box = (320, 1120, 400, 1180)

    result = handlers["popup_privacy_policy_accept"](
        {
            "ocr_results": [
                {"text": "隱私權政策", "box": (260, 280, 460, 330)},
                {"text": "同意隱私權政策", "box": agree_box},
                {"text": "OK", "box": ok_box},
            ]
        }
    )

    assert result.success is True
    assert adb.tapped_boxes == [agree_box]


def test_android_anr_handler_taps_close_app_button():
    """Android ANR 优先点击系统弹窗的关闭应用，避免重启模拟器。"""
    adb = _Adb()
    close_box = (180, 640, 380, 700)
    wait_box = (180, 740, 380, 800)
    handlers = build_common_handlers(adb, _PageDetector())

    result = handlers["android_app_not_responding"](
        {
            "ocr_results": [
                {"text": "Home没有响应", "box": (200, 540, 460, 590)},
                {"text": "关闭应用", "box": close_box},
                {"text": "等待", "box": wait_box},
            ]
        }
    )

    assert result.success is True
    assert result.should_wait == 0.5
    assert adb.tapped_boxes == [close_box]
    assert adb.restarted_apps == []
