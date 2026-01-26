# -*- coding: utf-8 -*-
from typing import Callable, Dict
import time

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.utils.gesture import (
    click_confirm,
    click_continue,
    tap_center,
    tap_text,
    tap_template,
    press_back,
)

Handler = Callable[[dict], ActionResult]


def build_common_handlers(
    adb, page_detector
) -> Dict[str, Handler]:
    def h_popup_ok(page_info: dict) -> ActionResult:
        return click_confirm(
            adb,
            page_detector,
            page_info.get("ocr_results", []),
            get_text_patterns("popup_ok"),
        )

    def h_network_error(page_info: dict) -> ActionResult:
        return click_confirm(
            adb,
            page_detector,
            page_info.get("ocr_results", []),
            get_text_patterns("network_error_popup"),
        )

    def h_continue(page_info: dict) -> ActionResult:
        return click_continue(
            adb,
            page_detector,
            page_info.get("ocr_results", []),
            get_text_patterns("continue_button"),
        )

    def h_tap_to_continue(page_info: dict) -> ActionResult:
        """处理"點擊來繼續"类型的页面，点击该文字位置"""
        return tap_text(
            adb,
            page_info.get("ocr_results", []),
            get_text_patterns("tap_to_continue"),
            wait=1.0,
        ) or tap_center(adb, wait=1.0)

    def h_game_open(page_info: dict) -> ActionResult:
        return tap_center(adb, wait=1.0)

    def h_main(page_info: dict) -> ActionResult:
        ocr = page_info.get("ocr_results", [])
        patterns = get_text_patterns("main_page")
        return tap_text(adb, ocr, patterns, wait=1.0) or tap_center(adb, wait=1.0)

    def h_close_app(page_info: dict) -> ActionResult:
        ocr = page_info.get("ocr_results", [])
        patterns = get_text_patterns("close_app_popup")
        return tap_text(adb, ocr, patterns, wait=1.0) or press_back(adb, wait=1.0)

    def h_btn_close(page_info: dict) -> ActionResult:
        """点击游戏内通用关闭按钮"""
        return tap_template(adb, page_detector, "btn_close", wait=1.0) or ActionResult.ok(wait=1.0)

    def h_wait(page_info: dict) -> ActionResult:
        #TODO 后续需要让所有陷入停滞的流程发出通知。
        return ActionResult.ok(wait=3)

    def h_to_home(page_info: dict) -> ActionResult:
        ocr = page_info.get("ocr_results", [])
        patterns = get_text_patterns("text_home")
        return tap_text(adb, ocr, patterns, wait=1.0)

    # 只要是系统页面全部走重启app就行
    def h_restart_app(page_info: dict) -> ActionResult:
        return ActionResult.ok(wait=1)

    return {
        "popup_ok": h_popup_ok,
        "network_error_popup": h_network_error,
        "continue_button": h_continue,
        "tap_to_continue": h_tap_to_continue,
        "game_open_page": h_game_open,
        "btn_close": h_btn_close,
        "auth_again": h_wait,
        "_main_page": h_main,
        "_close_app_popup": h_close_app,
        "_to_home": h_to_home,
    }
