# -*- coding: utf-8 -*-
from typing import Callable, Dict
import logging

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.utils.gesture import (
    click_confirm,
    click_continue,
    tap_center,
    tap_text,
    tap_template,
    press_back,
)

logger = logging.getLogger(__name__)

Handler = Callable[[dict], ActionResult]


def build_common_handlers(adb, page_detector) -> Dict[str, Handler]:
    """
    基于 common.py 中的配置动态生成通用页面处理器
    """

    # === 处理器工厂方法 ===

    def action_click_confirm(page_conf: dict) -> Handler:
        key = page_conf.get("patterns_key")

        def handler(page_info: dict) -> ActionResult:
            return click_confirm(
                adb,
                page_detector,
                page_info.get("ocr_results", []),
                get_text_patterns(key) if key else [],
            )

        return handler

    def action_click_continue(page_conf: dict) -> Handler:
        key = page_conf.get("patterns_key")

        def handler(page_info: dict) -> ActionResult:
            return click_continue(
                adb,
                page_detector,
                page_info.get("ocr_results", []),
                get_text_patterns(key) if key else [],
            )

        return handler

    def action_tap_text(page_conf: dict) -> Handler:
        key = page_conf.get("patterns_key")

        def handler(page_info: dict) -> ActionResult:
            return tap_text(
                adb,
                page_info.get("ocr_results", []),
                get_text_patterns(key) if key else [],
                wait=1.0,
            ) or ActionResult.ok()

        return handler

    def action_tap_text_or_center(page_conf: dict) -> Handler:
        key = page_conf.get("patterns_key")

        def handler(page_info: dict) -> ActionResult:
            res = tap_text(
                adb,
                page_info.get("ocr_results", []),
                get_text_patterns(key) if key else [],
                wait=1.0,
            )
            return res if res else tap_center(adb, wait=1.0)

        return handler

    def action_tap_text_or_back(page_conf: dict) -> Handler:
        key = page_conf.get("patterns_key")

        def handler(page_info: dict) -> ActionResult:
            res = tap_text(
                adb,
                page_info.get("ocr_results", []),
                get_text_patterns(key) if key else [],
                wait=1.0,
            )
            return res if res else press_back(adb, wait=1.0)

        return handler

    def action_tap_template(page_conf: dict) -> Handler:
        tpl = page_conf.get("template_name")

        def handler(page_info: dict) -> ActionResult:
            return tap_template(adb, page_detector, tpl, wait=1.0) or ActionResult.ok(
                wait=1.0
            )

        return handler

    def action_tap_center(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            return tap_center(adb, wait=1.0)

        return handler

    def action_wait(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            # TODO 后续需要让所有陷入停滞的流程发出通知。
            return ActionResult.ok(wait=3)

        return handler

    # 动作类型映射表
    action_map = {
        "click_confirm": action_click_confirm,
        "click_continue": action_click_continue,
        "tap_text": action_tap_text,
        "tap_text_or_center": action_tap_text_or_center,
        "tap_text_or_back": action_tap_text_or_back,
        "tap_template": action_tap_template,
        "tap_center": action_tap_center,
        "wait": action_wait,
    }

    handlers = {}

    # 遍历配置动态生成 Handler
    for page_conf in COMMON_PAGES:
        name = page_conf["name"]
        action_type = page_conf.get("action")

        if action_type and action_type in action_map:
            factory = action_map[action_type]
            handlers[name] = factory(page_conf)
        else:
            if action_type:
                logger.warning(f"页面 {name} 配置了未知的 action: {action_type}")

    return handlers