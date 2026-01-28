# -*- coding: utf-8 -*-
from typing import Callable, Dict
import logging

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.locales import get_text_patterns
from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.utils.gesture import (
    tap_center,
    tap_text,
    tap_template,
    press_back,
    tap_box,
    tap_matched_element,
)

logger = logging.getLogger(__name__)

Handler = Callable[[dict], ActionResult]


def build_common_handlers(adb, page_detector) -> Dict[str, Handler]:
    """
    基于 common.py 中的配置动态生成通用页面处理器
    """

    # === 处理器工厂方法 ===

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
            # 优先使用页面检测阶段匹配到的具体模板信息
            matched_template = page_info.get("matched_template")
            if matched_template and matched_template.get("box"):
                logger.debug(f"点击上下文匹配模板: {matched_template['template']}")
                return tap_box(adb, matched_template["box"], wait=1.0)

            # 回退到配置的静态模板名
            return tap_template(adb, page_detector, tpl, wait=1.0) or ActionResult.ok(
                wait=1.0
            )

        return handler

    def action_tap_center(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            return tap_center(adb, wait=1.0)

        return handler

    # 注意 match_all=True 请把 你想点的那个文字放在 `identifiers` 列表的第一
    # 或者使用 tap_text 精确传参
    def action_tap_matched(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            result = tap_matched_element(adb, page_info, wait=1.0)
            if result:
                return result

            logger.warning("配置了 tap_matched 但未找到匹配上下文")
            return ActionResult.ok(wait=1.0)

        return handler

    def action_wait(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            # TODO 后续需要让所有陷入停滞的流程发出通知。
            return ActionResult.ok(wait=3)

        return handler

    def action_restart_game(page_conf: dict) -> Handler:
        def handler(page_info: dict) -> ActionResult:
            settings = get_settings()
            logger.info("执行页面配置的重启操作")
            adb.restart_app(settings.app_package)
            return ActionResult.ok(wait=8.0)
        return handler



    # 动作类型映射表
    action_map = {
        "tap_text": action_tap_text,
        "tap_text_or_center": action_tap_text_or_center,
        "tap_text_or_back": action_tap_text_or_back,
        "tap_template": action_tap_template,
        "tap_center": action_tap_center,
        "tap_matched": action_tap_matched,
        "wait": action_wait,
        "restart_game": action_restart_game,
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
