# -*- coding: utf-8 -*-
"""
卡包数据工具模块

提供 pack_code 与 boosters 的映射查询功能。
"""

import json
from pathlib import Path
from typing import List, Optional

PACKS_DATA_PATH = Path(__file__).parent.parent.parent.parent / "data" / "packs.json"
_packs_cache: Optional[dict] = None


def _load_packs_data() -> dict:
    """加载 packs.json 数据（带缓存）"""
    global _packs_cache
    if _packs_cache is None:
        if not PACKS_DATA_PATH.exists():
            _packs_cache = {}
        else:
            with open(PACKS_DATA_PATH, "r", encoding="utf-8") as f:
                _packs_cache = json.load(f)
    return _packs_cache


def get_boosters(pack_code: str) -> List[str]:
    """
    获取指定 pack_code 的 boosters 列表

    Args:
        pack_code: 扩充包代码，如 A1, B1, A2a

    Returns:
        boosters 名称列表，如 ["Charizard", "Mewtwo", "Pikachu"]
        如果 pack_code 不存在，返回空列表
    """
    data = _load_packs_data()
    pack_info = data.get(pack_code, {})
    return pack_info.get("boosters", [])


def get_booster_count(pack_code: str) -> int:
    """
    获取指定 pack_code 的子包数量

    Args:
        pack_code: 扩充包代码，如 A1, B1

    Returns:
        子包数量
    """
    return len(get_boosters(pack_code))
