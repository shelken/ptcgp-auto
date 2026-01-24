# -*- coding: utf-8 -*-
"""
多语言支持模块

提供基于配置动态加载语言包的功能。
"""

import importlib
import logging
from typing import List, Dict, Any

from ptcgp_auto_v2.config.settings import get_settings

logger = logging.getLogger(__name__)

# 缓存已加载的语言包
_loaded_locales: Dict[str, Any] = {}


def get_locale_module():
    """获取当前配置的语言模块"""
    settings = get_settings()
    locale_name = settings.locale

    if locale_name in _loaded_locales:
        return _loaded_locales[locale_name]

    try:
        # 动态导入模块，例如 ptcgp_auto_v2.locales.zh_Hant
        module_path = f"ptcgp_auto_v2.locales.{locale_name}"
        module = importlib.import_module(module_path)
        _loaded_locales[locale_name] = module
        logger.debug(f"已加载语言包: {locale_name}")
        return module
    except ImportError:
        logger.error(f"无法加载语言包: {locale_name}，回退到 zh_Hant")
        # 回退机制
        if locale_name != "zh_Hant":
            try:
                fallback_module = importlib.import_module("ptcgp_auto_v2.locales.zh_Hant")
                _loaded_locales["zh_Hant"] = fallback_module
                return fallback_module
            except ImportError:
                logger.critical("无法加载默认语言包 zh_Hant")
                raise
        raise


def get_text_patterns(key: str) -> List[str]:
    """
    获取指定 key 的文本模式列表
    根据当前 settings.locale 动态获取
    """
    module = get_locale_module()

    # 假设语言包模块中定义了 TEXT_PATTERNS 字典
    patterns_dict = getattr(module, "TEXT_PATTERNS", {})

    patterns = patterns_dict.get(key, [])
    if isinstance(patterns, list):
        return patterns
    return []


def get_config_value(key: str) -> Any:
    """
    获取指定 key 的配置值（可能是 list, dict 等）
    不进行类型检查，直接返回原始值
    """
    module = get_locale_module()
    patterns_dict = getattr(module, "TEXT_PATTERNS", {})
    return patterns_dict.get(key)
