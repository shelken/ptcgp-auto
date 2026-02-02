"""
表单处理工具模块
提供安全的表单数据解析功能
"""

from typing import Any, Optional
import json


def safe_get_string(
    form_data: Any, key: str, default: Optional[str] = None
) -> Optional[str]:
    """安全地从表单数据获取字符串值"""
    value = form_data.get(key)
    if isinstance(value, str):
        return value
    return default


def safe_get_int(form_data: Any, key: str, default: int = 0) -> int:
    """安全地从表单数据获取整数值"""
    value = form_data.get(key)
    try:
        return int(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def parse_json_label(label_data: Optional[str]) -> dict:
    """安全地解析 JSON 标签数据"""
    if not label_data:
        return {}
    try:
        return json.loads(label_data)
    except json.JSONDecodeError:
        return {}


def build_label_dict(existing_labels: dict, lang_key: str, new_value: str) -> str:
    """构建更新的标签字典"""
    labels = existing_labels.copy()
    labels[lang_key] = new_value
    return json.dumps(labels, ensure_ascii=False)
