# -*- coding: utf-8 -*-
"""
开包自动选择策略模块

用于在账号未配置开包目标时，自动选择合适的卡包。
"""

from __future__ import annotations

import hashlib
from bisect import bisect_left
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from ptcgp_auto_v2.config.constants import (
    PACK_AUTO_HASH_VIRTUAL_NODES,
    PACK_AUTO_STRATEGIES,
    PACK_SERIES_CODES,
)

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, Pack, CardSet
    from ptcgp_auto_v2.db.repositories import CardRepository, PackRecordRepository


def select_pack_for_account(
    account: "Account",
    strategy: str,
    card_repo: "CardRepository",
    record_repo: "PackRecordRepository",
    exclude_set_codes: list[str],
) -> Optional[dict]:
    """根据策略返回选中的卡包信息。"""
    candidates = _build_candidates(card_repo, exclude_set_codes)
    if not candidates:
        return None

    if strategy not in PACK_AUTO_STRATEGIES:
        strategy = "latest"

    account_key = _build_account_key(account)
    if strategy == "least_used":
        pack = _select_least_used(account_key, candidates, record_repo)
    elif strategy == "hash_balance":
        pack = _select_by_consistent_hash(account_key, candidates)
    else:
        pack = _select_latest_pack(candidates, card_repo)

    if not pack:
        return None

    return {
        "pack_code": pack.set_code,
        "booster_name": pack.name,
        "strategy": strategy,
        "candidate_count": len(candidates),
    }


def _build_candidates(
    card_repo: "CardRepository", exclude_set_codes: list[str]
) -> list["Pack"]:
    """构建可用的卡包候选列表。"""
    candidates = card_repo.get_packs_by_set_prefixes(
        prefixes=PACK_SERIES_CODES,
        exclude_set_codes=exclude_set_codes,
    )
    candidates.sort(key=lambda item: (item.set_code, item.name))
    return candidates


def _build_account_key(account: "Account") -> str:
    """构建账号的稳定哈希 Key。"""
    if getattr(account, "id", None) is not None:
        return f"id:{account.id}"
    game_id = getattr(account, "game_id", None)
    if game_id:
        return f"gid:{game_id}"
    display_name = getattr(account, "display_name", None)
    if display_name:
        return f"name:{display_name}"
    nickname = getattr(account, "nickname", None)
    return f"name:{nickname or 'unknown'}"


def _select_latest_pack(
    candidates: list["Pack"], card_repo: "CardRepository"
) -> Optional["Pack"]:
    """选择最新系列的一个卡包。"""
    set_codes = {pack.set_code for pack in candidates if pack.set_code}
    if not set_codes:
        return candidates[0] if candidates else None

    latest_code = None
    latest_date: Optional[datetime] = None
    for card_set in card_repo.get_all_sets():
        if card_set.code not in set_codes:
            continue
        parsed_date = _parse_release_date(card_set)
        if parsed_date is None:
            continue
        if latest_date is None or parsed_date > latest_date:
            latest_date = parsed_date
            latest_code = card_set.code

    if not latest_code:
        return candidates[0] if candidates else None

    latest_candidates = [pack for pack in candidates if pack.set_code == latest_code]
    if not latest_candidates:
        return candidates[0] if candidates else None

    latest_candidates.sort(key=lambda item: item.name)
    return latest_candidates[0]


def _parse_release_date(card_set: "CardSet") -> Optional[datetime]:
    """解析系列发布日期。"""
    if not card_set.release_date:
        return None
    try:
        return datetime.strptime(card_set.release_date, "%Y-%m-%d")
    except ValueError:
        return None


def _select_by_consistent_hash(
    account_key: str,
    candidates: list["Pack"],
    virtual_nodes: int = PACK_AUTO_HASH_VIRTUAL_NODES,
) -> Optional["Pack"]:
    """使用一致性哈希选择卡包。"""
    if not candidates:
        return None

    ring: list[tuple[int, "Pack"]] = []
    for pack in candidates:
        base_key = f"{pack.set_code}/{pack.name}"
        for index in range(virtual_nodes):
            key = f"{base_key}#{index}"
            ring.append((_hash_to_int(key), pack))

    ring.sort(key=lambda item: item[0])
    ring_keys = [item[0] for item in ring]
    account_hash = _hash_to_int(account_key)
    pos = bisect_left(ring_keys, account_hash)
    if pos >= len(ring):
        pos = 0
    return ring[pos][1]


def _select_least_used(
    account_key: str,
    candidates: list["Pack"],
    record_repo: "PackRecordRepository",
) -> Optional["Pack"]:
    """选择使用次数最少的卡包。"""
    if not candidates:
        return None

    pack_keys = [(pack.set_code, pack.name) for pack in candidates]
    usage_counts = record_repo.get_pack_usage_counts(pack_keys)
    if not usage_counts:
        return _select_by_consistent_hash(account_key, candidates)

    min_count = min(usage_counts.get(key, 0) for key in pack_keys)
    least_candidates = [
        pack
        for pack in candidates
        if usage_counts.get((pack.set_code, pack.name), 0) == min_count
    ]
    if not least_candidates:
        return _select_by_consistent_hash(account_key, candidates)

    return _select_by_consistent_hash(account_key, least_candidates)


def _hash_to_int(value: str) -> int:
    """稳定哈希到整数。"""
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()
    return int(digest, 16)
