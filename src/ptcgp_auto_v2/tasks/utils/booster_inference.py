# -*- coding: utf-8 -*-
"""
子包推断工具

提供两阶段子包推断能力：
1. 模板优先：在滑动页通过模板匹配识别子包
2. 卡牌兜底：在结果页通过卡牌反推子包

设计原则：纯工具函数，无状态，可复用。
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

def infer_pack_by_cards(
    *,
    detected_rows: list[dict],
    pack_names_by_set: dict[str, list[str]],
    card_pack_mapping: dict[int, list[str]],
) -> Optional[dict]:
    """通过卡牌反推子包（第二阶段兜底）。

    判定规则（按优先级）：
    1. 统计系列占比，超过 50% 的系列为候选
    2. 如果候选系列只有一个子包，直接判定
    3. 如果候选系列有多个子包，使用唯一归属证据判定：
       - 忽略在多个子包中都出现的卡牌
       - 只考虑仅出现在单个子包中的卡牌作为证据
       - 统计各子包的证据数，最高且唯一则判定
    4. 无法唯一确定时返回 pack_name=None，但 pack_code 可能确定

    Args:
        detected_rows: 检测到的卡牌列表，每项包含 set_code, card_id
        pack_names_by_set: {set_code: [pack_name, ...]} 系列子包映射
        card_pack_mapping: {card_id: [pack_name, ...]} 卡牌子包映射

    Returns:
        推断结果 {"pack_code": str, "booster_name": str|None, "source": "cards"}
        或 None（无法确定系列）
    """
    if not detected_rows:
        return None

    # 1. 统计系列占比
    set_counts = {}
    valid_rows = []

    for row in detected_rows:
        set_code = row.get("set_code")
        card_id = row.get("card_id")

        if not set_code or card_id is None:
            continue

        valid_rows.append(row)
        set_counts[set_code] = set_counts.get(set_code, 0) + 1

    if not valid_rows:
        return None

    total_cards = len(valid_rows)

    # 找出占比超过 50% 的系列
    majority_set = None
    for set_code, count in set_counts.items():
        if count > total_cards / 2:
            majority_set = set_code
            break

    if not majority_set:
        logger.debug(f"[子包推断] 无多数系列: {set_counts}")
        return None

    # 2. 检查该系列的子包情况
    packs = pack_names_by_set.get(majority_set, [])

    if not packs:
        logger.debug(f"[子包推断] 系列 {majority_set} 无子包信息")
        return None

    # 只有一个子包，直接判定
    if len(packs) == 1:
        return {
            "pack_code": majority_set,
            "booster_name": packs[0],
            "source": "cards",
        }

    # 3. 多子包情况：使用唯一归属证据判定
    pack_evidence = {pack: 0 for pack in packs}

    for row in valid_rows:
        if row.get("set_code") != majority_set:
            continue

        card_id = row.get("card_id")
        card_packs = card_pack_mapping.get(card_id, [])

        if not card_packs:
            continue

        # 只考虑该系列的子包
        relevant_packs = [p for p in card_packs if p in packs]

        if len(relevant_packs) == 1:
            # 这张卡只在其中一个子包出现，作为证据
            pack_evidence[relevant_packs[0]] += 1
        # len(relevant_packs) > 1：在多个子包中出现，忽略（无法区分）

    # 找出证据最多的子包
    best_pack = None
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
            "pack_code": majority_set,
            "booster_name": best_pack,
            "source": "cards",
        }
    else:
        # 系列确定但子包不唯一
        return {
            "pack_code": majority_set,
            "booster_name": None,
            "source": "cards",
        }
