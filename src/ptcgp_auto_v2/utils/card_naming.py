# -*- coding: utf-8 -*-
"""
卡牌命名工具
用于处理卡牌文件名标准化、解析等逻辑，避免 Repository 和 ImageManager 之间的循环依赖。
"""

import re
from typing import Optional
from ptcgp_auto_v2.db.models import Card

def normalize_name_str(name: str) -> str:
    """统一的文件名标准化逻辑：过滤特殊字符 + 空格转下划线"""
    # 保留字母数字、横杠、下划线、空格
    safe_name = "".join([c for c in name if c.isalnum() or c in " -_"])
    # 将空格替换为下划线
    return safe_name.replace(" ", "_")

def get_card_filename(card: Card) -> str:
    """
    生成标准化的卡牌文件名 (空格替换为下划线)
    Format: {number:03d}_{name}.png
    """
    safe_name = normalize_name_str(card.name)
    return f"{card.number:03d}_{safe_name}.png"

def parse_card_number_from_filename(filename: str) -> Optional[int]:
    """
    从文件名或模板名解析卡牌编号
    e.g. '001_Bulbasaur.png' -> 1
         '025' -> 25
    """
    # 匹配开头的数字，支持带扩展名或不带
    match = re.match(r"^(\d+)(?:_|$)", filename)
    if match:
        return int(match.group(1))
    return None
