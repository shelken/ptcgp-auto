# -*- coding: utf-8 -*-
"""
卡包数据工具模块

提供 set_code 与 boosters 的映射查询功能。
底层使用 CardRepository 从数据库查询。
"""

from typing import List
from ptcgp_auto_v2.db.repositories import CardRepository


def get_boosters(set_code: str) -> List[str]:
    """
    获取指定 set_code 的 boosters 列表

    Args:
        set_code: 系列代码，如 A1, B1, A2a

    Returns:
        boosters 名称列表，如 ["Charizard", "Mewtwo", "Pikachu"]
        如果 set_code 不存在，返回空列表
    """
    repo = CardRepository()
    return repo.get_pack_names_by_set(set_code)


def get_booster_count(set_code: str) -> int:
    """
    获取指定 set_code 的子包数量

    Args:
        set_code: 系列代码，如 A1, B1

    Returns:
        子包数量
    """
    return len(get_boosters(set_code))
