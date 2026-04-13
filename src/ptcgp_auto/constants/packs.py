# -*- coding: utf-8 -*-
"""
卡包常量定义

从数据库加载数据 (CardRepository)
"""

from ptcgp_auto_v2.db.repositories import CardRepository


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
