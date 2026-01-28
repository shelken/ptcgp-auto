# -*- coding: utf-8 -*-
"""
卡包常量定义

从数据库加载数据 (CardRepository)
"""

from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.card_naming import normalize_name_str


def _load_packs() -> dict:
    """从数据库加载卡包数据"""
    try:
        repo = CardRepository()
        sets = repo.get_all_sets()
        
        packs_data = {}
        for card_set in sets:
            set_packs = repo.get_packs_by_set(card_set.code)
            packs_data.update(set_packs)
            
        return packs_data
    except Exception:
        # 数据库可能未初始化（如CI环境或首次安装），容错处理
        return {}


# 加载卡包数据
PACKS = _load_packs()


def get_pack_choices() -> list[tuple[str, str]]:
    """
    获取扩充包选择列表

    Returns:
        [(code, display_name), ...]
    """
    choices = []
    for code, info in PACKS.items():
        display = f"{code}: {info['name']}"
        choices.append((code, display))
    return choices


def get_booster_choices(pack_code: str) -> list[tuple[str, str]]:
    """
    获取指定扩充包的子包选择列表

    Args:
        pack_code: 扩充包代码

    Returns:
        [(booster_name, display_name), ...]
        如果没有子包，返回扩充包名称作为唯一选项
    """
    pack = PACKS.get(pack_code)
    if not pack:
        return []

    boosters = pack.get("boosters", [])
    if not boosters:
        # 无子包时，使用扩充包名称
        name = normalize_name_str(pack["name"])
        return [(name, pack["name"])]

    return [(normalize_name_str(b), b) for b in boosters]


def get_template_path(pack_code: str, booster_name: str) -> str:
    """
    获取模板保存路径

    Args:
        pack_code: 扩充包代码 (如 A1, B1a)
        booster_name: 子包名称 (如 Pikachu, Mega_Blaziken_ex)

    Returns:
        相对于 templates 目录的路径 (如 packs/A1/Pikachu.png)
    """
    return f"packs/{pack_code}/{booster_name}.png"