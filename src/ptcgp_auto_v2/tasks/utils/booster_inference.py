# -*- coding: utf-8 -*-
"""
子包推断工具

提供两阶段子包推断能力：
1. 模板优先：在滑动页通过模板匹配识别子包
2. 卡牌兜底：在结果页通过卡牌反推子包

设计原则：纯工具函数，无状态，可复用。
"""

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Card

logger = logging.getLogger(__name__)


def _is_promo_pack(pack_name: str) -> bool:
    """判断是否为 PROMO 子包"""
    return pack_name.upper().startswith("PROMO")


def _get_card_pack_names(card: "Card") -> list[str]:
    """获取卡牌所属的非 PROMO 子包名称列表"""
    return [
        cp.pack_name
        for cp in card.packs
        if cp.pack_name and not _is_promo_pack(cp.pack_name)
    ]


def infer_pack_by_cards(cards: list["Card"]) -> Optional[dict]:
    """通过卡牌反推子包（第二阶段兜底）。

    判定规则（按优先级）：
    1. 统计系列占比，超过 50% 的系列为候选
    2. 如果候选系列只有一个子包，直接判定
    3. 如果候选系列有多个子包，使用唯一归属证据判定：
       - 忽略在多个子包中都出现的卡牌
       - 只考虑仅出现在单个子包中的卡牌作为证据
       - 统计各子包的证据数，最高且唯一则判定
    4. 无法唯一确定时返回 pack_name=None，但 set_code 可能确定

    Args:
        cards: Card 对象列表（需要已加载 packs 关系）

    Returns:
        推断结果 {"set_code": str, "booster_name": str|None, "source": "cards"}
        或 None（无法确定系列）
    """
    if not cards:
        return None

    # 1. 统计系列占比，同时收集该系列的所有子包
    set_counts: dict[str, int] = {}
    valid_cards: list["Card"] = []
    # 按系列收集子包（排除 PROMO）
    packs_by_set: dict[str, set[str]] = {}
    # 每张卡牌对应的子包列表
    card_packs_map: dict[int, list[str]] = {}

    for card in cards:
        if not card.id or not card.set_code:
            continue

        pack_names = _get_card_pack_names(card)
        if not pack_names:
            continue

        valid_cards.append(card)
        set_counts[card.set_code] = set_counts.get(card.set_code, 0) + 1
        card_packs_map[card.id] = pack_names

        # 收集该系列的所有子包
        if card.set_code not in packs_by_set:
            packs_by_set[card.set_code] = set()
        packs_by_set[card.set_code].update(pack_names)

    if not valid_cards:
        return None

    total_cards = len(valid_cards)

    # 找出占比超过 50% 的系列
    majority_set: Optional[str] = None
    for set_code, count in set_counts.items():
        if count > total_cards / 2:
            majority_set = set_code
            break

    if not majority_set:
        logger.debug(f"[子包推断] 无多数系列: {set_counts}")
        return None

    # 2. 检查该系列的子包情况
    packs = sorted(packs_by_set.get(majority_set) or [])

    if not packs:
        logger.debug(f"[子包推断] 系列 {majority_set} 无子包信息")
        return None

    # 只有一个子包，直接判定
    if len(packs) == 1:
        return {
            "set_code": majority_set,
            "booster_name": packs[0],
            "source": "cards",
        }

    # 3. 多子包情况：使用唯一归属证据判定
    pack_evidence: dict[str, int] = {pack: 0 for pack in packs}

    for card in valid_cards:
        if card.set_code != majority_set:
            continue

        card_id = card.id
        if card_id is None:
            continue
        card_packs = card_packs_map.get(card_id) or []
        if not card_packs:
            continue

        # 只考虑该系列的子包
        relevant_packs = [p for p in card_packs if p in packs]

        if len(relevant_packs) == 1:
            # 这张卡只在其中一个子包出现，作为证据
            pack_evidence[relevant_packs[0]] += 1
        # len(relevant_packs) > 1：在多个子包中出现，忽略（无法区分）

    # 找出证据最多的子包
    best_pack: Optional[str] = None
    best_evidence = 0
    tie = False

    for pack, evidence in pack_evidence.items():
        if evidence > best_evidence:
            best_evidence = evidence
            best_pack = pack
            tie = False
        elif evidence == best_evidence and evidence > 0:
            tie = True

    # 有唯一证据则判定，否则 pack_name=None
    if best_pack and not tie and best_evidence > 0:
        return {
            "set_code": majority_set,
            "booster_name": best_pack,
            "source": "cards",
        }
    else:
        # 系列确定但子包不唯一
        return {
            "set_code": majority_set,
            "booster_name": None,
            "source": "cards",
        }
