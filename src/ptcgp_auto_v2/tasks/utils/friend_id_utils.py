# -*- coding: utf-8 -*-
"""
好友ID提取工具。
"""

import re
from typing import Optional


FRIEND_ID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{4}")


def extract_friend_id_from_text(text: str) -> Optional[str]:
    """从文本中提取标准 friend_id（16位数字）。"""
    match = FRIEND_ID_PATTERN.search(text)
    if not match:
        return None
    return match.group().replace("-", "")
