# -*- coding: utf-8 -*-
"""
语言与本地化配置统一入口

提供任务、Web、通知等全模块统一的语言配置与映射。
单一真相来源：所有语言相关配置应从此模块导入。
"""

import json
from typing import Any

# ========== 核心语言配置（任务/OCR 层） ==========
# locale 文件名 <-> OCR 语言代码映射
LOCALE_TO_OCR_LANGUAGE = {
    "zh_Hant": "zh-Hant",
    "en_US": "en-US",
}

DEFAULT_LOCALE = "zh_Hant"
SUPPORTED_LOCALES = list(LOCALE_TO_OCR_LANGUAGE.keys())
OCR_LANGUAGE_TO_LOCALE = {v: k for k, v in LOCALE_TO_OCR_LANGUAGE.items()}
DEFAULT_OCR_LANGUAGES = list(LOCALE_TO_OCR_LANGUAGE.values())

# 运行时校验
if DEFAULT_LOCALE not in SUPPORTED_LOCALES:
    raise ValueError(f"DEFAULT_LOCALE={DEFAULT_LOCALE} 不在 SUPPORTED_LOCALES 中")


# ========== Web 界面语言配置 ==========
# Web 支持的语言文件（与 web/locales/ 目录下的文件对应）
WEB_SUPPORTED_LANGS = ["en", "zh_CN"]

# Web 语言键
WEB_LANG_ZH = "zh_CN"
WEB_LANG_EN = "en"

# 数据库标签键（label_data 中使用的 key）
DB_LABEL_KEY_ZH = "zh"
DB_LABEL_KEY_EN = "en"

# Web 语言到数据库标签键的映射（优先级列表，第一个是首选）
WEB_LANG_TO_DB_LABEL_KEYS = {
    WEB_LANG_ZH: [DB_LABEL_KEY_ZH, DB_LABEL_KEY_EN],
    WEB_LANG_EN: [DB_LABEL_KEY_EN, DB_LABEL_KEY_ZH],
}

# 默认语言键（Web 层默认）
DEFAULT_LANG_KEY = "zh_CN"


# ========== 语言映射工具函数 ==========
def get_label_candidates(web_lang: str) -> list[str]:
    """
    获取指定 Web 语言的标签候选列表（按优先级）

    Args:
        web_lang: Web 层语言键（如 "zh_CN", "en"）

    Returns:
        标签键优先级列表
    """
    return WEB_LANG_TO_DB_LABEL_KEYS.get(
        web_lang, WEB_LANG_TO_DB_LABEL_KEYS[DEFAULT_LANG_KEY]
    )


def web_lang_to_locale(web_lang: str) -> str:
    """
    将 Web 语言键转换为任务层 locale

    Args:
        web_lang: Web 层语言键（如 "zh_CN", "en"）

    Returns:
        任务层 locale（如 "zh_Hant", "en_US"）
    """
    mapping = {
        "zh_CN": "zh_Hant",
        "zh_TW": "zh_Hant",
        "zh_HK": "zh_Hant",
        "zh": "zh_Hant",
        "en": "en_US",
    }
    return mapping.get(web_lang, DEFAULT_LOCALE)


def locale_to_web_lang(locale: str) -> str:
    """
    将任务层 locale 转换为 Web 语言键

    Args:
        locale: 任务层 locale（如 "zh_Hant", "en_US"）

    Returns:
        Web 层语言键
    """
    mapping = {
        "zh_Hant": "zh_CN",
        "en_US": "en",
    }
    return mapping.get(locale, DEFAULT_LANG_KEY)


def _parse_json_object(raw: str | dict[str, Any] | None) -> dict[str, Any]:
    """解析 JSON 文本/字典为对象字典，失败返回空字典。"""
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_localized_text(
    raw_data: str | dict[str, Any] | None,
    web_lang: str,
    fallback: str = "",
    localized_field: str | None = None,
) -> str:
    """
    统一解析本地化文本（唯一开放接口）。

    Args:
        raw_data: 原始数据（dict 或 JSON 字符串）
        web_lang: Web 语言键（如 zh_CN / en）
        fallback: 兜底文本
        localized_field: 可选字段名（如 localized_name），优先读取该字段
    """
    payload = _parse_json_object(raw_data)
    if not payload:
        return fallback

    label_candidates = get_label_candidates(web_lang)

    if localized_field:
        localized_value = payload.get(localized_field)
        if isinstance(localized_value, str) and localized_value.strip():
            return localized_value.strip()
        if isinstance(localized_value, dict):
            for key in label_candidates:
                value = localized_value.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    for key in label_candidates:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return fallback
