# -*- coding: utf-8 -*-
"""
公共页面规则
"""

from ptcgp_auto_v2.locales.zh_Hant import TEXT_PATTERNS


def _get_patterns(text_patterns: dict, key: str) -> list[str]:
    patterns = text_patterns.get(key, [])
    return patterns if isinstance(patterns, list) else []


# 下划线开头与游戏无关，系统相关
# 新增 action 字段用于声明式生成 Handler
# action 类型参考 common_handlers.py 中的工厂方法
COMMON_PAGES = [
    # TODO `清除快取 重新下載`
    # （这种情况一般游戏有问题，不要点ok，重启过，没用，一般应该需要重启整个模拟器）
    {
        "name": "popup_clean_and_download",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_clean_and_download"),
        "match_all": True,
        "priority": 140,
        "action": "restart_emulator",
    },
    {
        "name": "popup_error_code_103_011_05400",
        "identifiers": _get_patterns(TEXT_PATTERNS, "error_code_103_011_05400"),
        "match_all": True,
        "priority": 145,
        "action": "restart_emulator",
    },
    {
        "name": "popup_ok",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_ok"),
        "priority": 150,
        "exact_match": True,
        "action": "tap_matched",
    },
    # 点再试一次
    {
        "name": "popup_network_error",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_network_error"),
        "priority": 150,
        "exact_match": True,
        "action": "tap_matched",
    },
    # 点继续
    {
        "name": "continue_button",
        "identifiers": _get_patterns(TEXT_PATTERNS, "continue_button"),
        "priority": 150,
        "exact_match": True,
        "action": "tap_matched",
    },
    # 点 点击来继续
    {
        "name": "tap_to_continue",
        "identifiers": _get_patterns(TEXT_PATTERNS, "tap_to_continue"),
        "priority": 150,
        "action": "tap_matched",
    },
    # 点 點擊畫面開始遊戲
    {
        "name": "game_open_page",
        "identifiers": _get_patterns(TEXT_PATTERNS, "game_open_page"),
        "priority": 150,
        "action": "tap_matched",
    },
    {
        # 匹配各种手指图标并点击（模板匹配）
        # 目前可以看出，只要出现了这些按钮必定，优先点击
        "name": "icon_hand_tap",
        "templates": ["hand_up_left", "hand_up_right"],
        "priority": 10,
        "action": "tap_matched",
    },
    {
        # 目前可以看出，只要出现了这些按钮必定，优先点击
        "name": "icon_hand_tap",
        "templates": ["hand_up"],
        "priority": 160,
        "action": "tap_matched",
    },
    {
        # 返回按钮（模板匹配）
        "name": "btn_back",
        "templates": ["btn_back"],
        "priority": 500,
        "action": "tap_matched",
    },
    {
        # 游戏内通用关闭按钮（模板匹配）
        "name": "btn_close",
        "templates": ["btn_close"],
        "priority": 500,
        "action": "tap_matched",
    },
    # TODO 执行重新认证（需要通知重新登录账号）
    {
        "name": "popup_auth_again",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_auth_again"),
        "priority": 500,
        "action": "wait",
    },
    # 游戏启动失败，尝试重启
    {
        "name": "popup_game_launch_fail",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_game_launch_fail"),
        "priority": 500,
        "action": "tap_text",
        "patterns_key": "text_x",
    },
    # 回到標題畫面
    {
        "name": "popup_return_to_title_screen",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_return_to_title_screen"),
        "priority": 500,
        "action": "tap_matched",
    },
    # 確定要關閉應用程式嗎？
    {
        "name": "popup_close_game",
        "identifiers": _get_patterns(TEXT_PATTERNS, "popup_close_game"),
        "priority": 500,
        "action": "tap_text",
        "patterns_key": "text_cancel",
    },
    # 打开模拟器弹出页面
    {
        "name": "_to_home",
        "identifiers": _get_patterns(TEXT_PATTERNS, "_to_home"),
        "match_all": True,
        "priority": 900,
        "action": "tap_text",
        "patterns_key": "text_home",
    },
    {
        "name": "_scene_restart_game",
        "identifiers": _get_patterns(TEXT_PATTERNS, "_scene_restart_game"),
        "priority": 900,
        "action": "restart_game",
    },
    {
        "name": "_close_app_popup",
        "identifiers": _get_patterns(TEXT_PATTERNS, "close_app_popup"),
        "match_all": True,
        "priority": 900,
        "action": "tap_text_or_back",
        "patterns_key": "close_app_popup",
    },
    {
        "name": "_main_page",
        "identifiers": _get_patterns(TEXT_PATTERNS, "main_page"),
        "match_all": True,
        "exclude_identifiers": _get_patterns(TEXT_PATTERNS, "close_app_popup"),
        "priority": 900,
        "action": "tap_matched",
    },
]

__all__ = ["COMMON_PAGES"]
