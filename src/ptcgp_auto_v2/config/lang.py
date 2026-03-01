# -*- coding: utf-8 -*-
"""
语言与本地化配置统一入口

提供任务、Web、通知等全模块统一的语言配置与映射。
单一真相来源：所有语言相关配置应从此模块导入。
"""

import json
from typing import Any


# ========== Web 界面语言配置 ==========
# 只保留标准 Web 语言键；不提供任何别名/归一化。
DEFAULT_LANG_KEY: str = "zh_CN"


# ========== 核心语言配置（任务/OCR 层） ==========
# 注意：这里所有值都必须是确定常量，不允许通过推断/派生生成。

# 任务层默认 locale（对应 locales/*.py 文件名）
DEFAULT_LOCALE: str = "zh_Hant"

# OCR 默认语言列表（Apple Vision Framework 语言代码）
DEFAULT_OCR_LANGUAGES: list[str] = ["zh-Hant", "en-US"]


# 单一映射：标准 web_lang -> 数据库 label key 优先级
WEB_LANG_TO_DB_LABEL_KEYS: dict[str, list[str]] = {
    "zh_CN": ["zh", "en"],
    "en": ["en", "zh"],
}

TASK_LOCALE_TO_WEB_LANG: dict[str, str] = {"zh_Hant": "zh_CN", "en_US": "en"}


# ========== 语言映射工具函数 ==========
def get_label_candidates(web_lang: str) -> list[str]:
    """获取指定 Web 语言的标签候选列表（按优先级）。"""
    return WEB_LANG_TO_DB_LABEL_KEYS.get(
        web_lang, WEB_LANG_TO_DB_LABEL_KEYS[DEFAULT_LANG_KEY]
    )


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
