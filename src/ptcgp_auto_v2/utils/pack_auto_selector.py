# -*- coding: utf-8 -*-
"""
开包自动选择策略模块

用于在账号未配置开包目标时，自动选择合适的卡包。
"""

from __future__ import annotations

import hashlib
import math
import threading
from bisect import bisect_left
from datetime import datetime
from typing import TYPE_CHECKING, Optional, cast

from ptcgp_auto_v2.config.constants import (
    PACK_AUTO_HASH_VIRTUAL_NODES,
    PACK_AUTO_HRW_AGGRESSIVENESS,
    PACK_AUTO_HRW_EFFECTIVE_EPSILON_MAX,
    PACK_AUTO_HRW_EFFECTIVE_SCALE_MAX,
    PACK_AUTO_HRW_SEED,
    PACK_AUTO_HRW_SEED_SCAN_COUNT,
    PACK_AUTO_HRW_TARGET_RARITIES,
    PACK_AUTO_STRATEGIES,
    PACK_SERIES_CODES,
)
from ptcgp_auto_v2.utils.game_time import get_game_biz_date_str

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account, CardSet, Pack
    from ptcgp_auto_v2.db.repositories import CardRepository, PackRecordRepository


_HRW_WEEKLY_CACHE: dict[str, dict] = {}
_HRW_WEEKLY_CACHE_LOCK = threading.RLock()


def select_pack_for_account(
    account: "Account",
    strategy: str,
    card_repo: "CardRepository",
    record_repo: "PackRecordRepository",
    exclude_set_codes: list[str],
) -> Optional[dict]:
    """根据策略返回选中的卡包信息。"""
    if strategy not in PACK_AUTO_STRATEGIES:
        strategy = "latest"

    account_key = _build_account_key(account)
    candidate_count = 0
    if strategy in ("hrw_progress_balance", "hash_balance"):
        pack, candidate_count = _select_by_weighted_hrw(
            account_key,
            card_repo,
            exclude_set_codes,
        )
    else:
        candidates = _build_candidates(card_repo, exclude_set_codes)
        if not candidates:
            return None
        candidate_count = len(candidates)
        if strategy == "least_used":
            pack = _select_least_used(account_key, candidates, record_repo)
        else:
            pack = _select_latest_pack(candidates, card_repo)

    if not pack:
        return None

    return {
        "set_code": pack.set_code,
        "booster_name": pack.name,
        "strategy": strategy,
        "candidate_count": candidate_count,
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


def _select_by_weighted_hrw(
    account_key: str,
    card_repo: "CardRepository",
    exclude_set_codes: list[str],
) -> tuple[Optional["Pack"], int]:
    """按全局进度权重使用 HRW 选择卡包。"""
    cache_key = _build_weekly_cache_key(exclude_set_codes)
    snapshot = _get_or_build_weekly_snapshot(
        cache_key=cache_key,
        card_repo=card_repo,
        exclude_set_codes=exclude_set_codes,
        current_account_key=account_key,
    )
    if not snapshot:
        return None, 0

    selected_pack_key = snapshot["assignment_map"].get(account_key)
    if not selected_pack_key:
        snapshot = _get_or_build_weekly_snapshot(
            cache_key=cache_key,
            card_repo=card_repo,
            exclude_set_codes=exclude_set_codes,
            current_account_key=account_key,
            force_rebuild=True,
        )
        if not snapshot:
            return None, 0
        selected_pack_key = snapshot["assignment_map"].get(account_key)

    if not selected_pack_key:
        return None, int(snapshot["candidate_count"])
    return snapshot["pack_map"].get(selected_pack_key), int(snapshot["candidate_count"])


def _build_weekly_cache_key(exclude_set_codes: list[str]) -> str:
    """构建日级快照缓存键（seed 仍按周）。"""
    biz_date = get_game_biz_date_str()
    week_key = _build_week_seed_suffix(biz_date)
    excludes = ",".join(sorted(code for code in exclude_set_codes if code))
    effective_scale, effective_weight_max, effective_epsilon = (
        _build_hrw_effective_params()
    )
    return (
        f"{biz_date}|{week_key}|{excludes}|{PACK_AUTO_HRW_AGGRESSIVENESS}|"
        f"{effective_scale}|{effective_weight_max}|{effective_epsilon}|"
        f"{PACK_AUTO_HRW_SEED_SCAN_COUNT}|{PACK_AUTO_HRW_SEED}"
    )


def _get_or_build_weekly_snapshot(
    cache_key: str,
    card_repo: "CardRepository",
    exclude_set_codes: list[str],
    current_account_key: str,
    force_rebuild: bool = False,
) -> Optional[dict]:
    """获取或构建周级分配快照。"""
    with _HRW_WEEKLY_CACHE_LOCK:
        _prune_old_weekly_cache(cache_key)
        if not force_rebuild and cache_key in _HRW_WEEKLY_CACHE:
            return _HRW_WEEKLY_CACHE[cache_key]

    snapshot = _build_weekly_snapshot(
        card_repo=card_repo,
        exclude_set_codes=exclude_set_codes,
        current_account_key=current_account_key,
    )
    if not snapshot:
        return None

    with _HRW_WEEKLY_CACHE_LOCK:
        _HRW_WEEKLY_CACHE[cache_key] = snapshot
    return snapshot


def _prune_old_weekly_cache(cache_key: str) -> None:
    """清理非当日缓存，避免无限增长。"""
    day_prefix = cache_key.split("|", 1)[0]
    stale_keys = [item for item in _HRW_WEEKLY_CACHE if not item.startswith(day_prefix)]
    for item in stale_keys:
        _HRW_WEEKLY_CACHE.pop(item, None)


def _build_weekly_snapshot(
    card_repo: "CardRepository",
    exclude_set_codes: list[str],
    current_account_key: str,
) -> Optional[dict]:
    """构建周级分配快照。"""
    candidates = _build_candidates(card_repo, exclude_set_codes)
    if not candidates:
        return None

    effective_scale, effective_weight_max, effective_epsilon = (
        _build_hrw_effective_params()
    )
    pack_weights, progress_stats, progress_map = _build_pack_weights(
        candidates,
        card_repo,
        effective_scale=effective_scale,
    )
    if not pack_weights:
        return None

    pack_map = {f"{pack.set_code}/{pack.name}": pack for pack in candidates}
    pack_keys = list(pack_map.keys())
    account_keys = _load_all_account_keys(current_account_key)
    if not account_keys:
        account_keys = [current_account_key]

    selected_seed, assignment_map, best_metrics = _select_best_seed_distribution(
        account_keys=account_keys,
        pack_keys=pack_keys,
        pack_weights=pack_weights,
        epsilon=effective_epsilon,
        seed_candidates=_build_seed_candidates(),
    )
    return {
        "selected_seed": selected_seed,
        "best_metrics": best_metrics,
        "pack_map": pack_map,
        "assignment_map": assignment_map,
        "pack_weights": pack_weights,
        "progress_stats": progress_stats,
        "progress_ratio_map": progress_map,
        "account_count": len(account_keys),
        "candidate_count": len(candidates),
        "aggressiveness": PACK_AUTO_HRW_AGGRESSIVENESS,
        "effective_scale": effective_scale,
        "effective_weight_max": effective_weight_max,
        "effective_epsilon": effective_epsilon,
    }


def _build_pack_weights(
    candidates: list["Pack"],
    card_repo: "CardRepository",
    effective_scale: float,
) -> tuple[dict[str, float], dict[str, dict[str, int]], dict[str, float]]:
    """构建候选子包权重映射。"""
    pack_names = [pack.name for pack in candidates]
    progress_stats = card_repo.get_pack_target_rarity_progress(
        pack_names=pack_names,
        target_rarities=PACK_AUTO_HRW_TARGET_RARITIES,
    )

    pack_weights: dict[str, float] = {}
    progress_map: dict[str, float] = {}
    for pack in candidates:
        pack_key = f"{pack.set_code}/{pack.name}"
        stat = progress_stats.get(pack.name, {"total_target": 0, "owned_target": 0})
        total_target = int(stat.get("total_target", 0) or 0)
        owned_target = int(stat.get("owned_target", 0) or 0)
        progress_ratio = 1.0 if total_target <= 0 else owned_target / total_target
        gap = 1.0 - progress_ratio
        # 使用指数权重放大高缺口包差距，使 1.0 激进度具备明显集中效果。
        pack_weights[pack_key] = math.exp(effective_scale * gap)
        progress_map[pack_key] = progress_ratio
    return pack_weights, progress_stats, progress_map


def _build_hrw_effective_params() -> tuple[float, float, float]:
    """根据公开激进度参数派生 HRW 内部参数。"""
    aggressiveness = PACK_AUTO_HRW_AGGRESSIVENESS
    if aggressiveness < 0.0 or aggressiveness > 1.0:
        raise ValueError("PACK_AUTO_HRW_AGGRESSIVENESS 必须位于 0.0 到 1.0 之间")

    squared = aggressiveness * aggressiveness
    effective_scale = PACK_AUTO_HRW_EFFECTIVE_SCALE_MAX * squared
    effective_weight_max = math.exp(effective_scale)
    effective_epsilon = PACK_AUTO_HRW_EFFECTIVE_EPSILON_MAX * squared
    return effective_scale, effective_weight_max, effective_epsilon


def _build_hrw_seed() -> str:
    """构建按游戏业务周滚动的 HRW seed。"""
    biz_date = get_game_biz_date_str()
    return f"{PACK_AUTO_HRW_SEED}|{_build_week_seed_suffix(biz_date)}"


def _build_week_seed_suffix(biz_date: str) -> str:
    """根据业务日生成 ISO 周标识。"""
    parsed = datetime.strptime(biz_date, "%Y-%m-%d")
    iso = parsed.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _build_seed_candidates() -> list[str]:
    """构建候选 seed 列表。"""
    base_seed = _build_hrw_seed()
    seeds = [base_seed]
    seeds.extend(
        [
            f"rarity-gap-auto-{index}|{base_seed.split('|', 1)[1]}"
            for index in range(1, PACK_AUTO_HRW_SEED_SCAN_COUNT + 1)
        ]
    )
    return list(dict.fromkeys(seeds))


def _load_all_account_keys(current_account_key: str) -> list[str]:
    """加载用于全局分配的账号 key 列表。"""
    try:
        from ptcgp_auto_v2.db.repositories import AccountRepository

        accounts = AccountRepository().get_all()
        keys = [_build_account_key(item) for item in accounts]
    except Exception:
        keys = []

    if current_account_key and current_account_key not in keys:
        keys.append(current_account_key)
    return list(dict.fromkeys(keys))


def _assign_accounts_by_hrw(
    account_keys: list[str],
    pack_keys: list[str],
    pack_weights: dict[str, float],
    epsilon: float,
    seed: str,
) -> tuple[dict[str, int], dict[str, str]]:
    """按 HRW + cap 批量分配账号到子包。"""
    counts = {pack_key: 0 for pack_key in pack_keys}
    assignment: dict[str, str] = {}
    if not account_keys or not pack_keys:
        return counts, assignment

    cap = math.ceil((1.0 + epsilon) * len(account_keys) / len(pack_keys))
    for account_key in account_keys:
        scored: list[tuple[float, str]] = []
        for pack_key in pack_keys:
            weight = pack_weights.get(pack_key, 1.0)
            unit = _hash_to_unit(f"{account_key}|{pack_key}|{seed}")
            score = -math.log(unit) / weight
            scored.append((score, pack_key))
        scored.sort(key=lambda item: (item[0], item[1]))

        selected_pack_key = None
        for _, pack_key in scored:
            if counts[pack_key] < cap:
                selected_pack_key = pack_key
                break
        if not selected_pack_key:
            selected_pack_key = min(
                counts.items(), key=lambda item: (item[1], item[0])
            )[0]

        counts[selected_pack_key] += 1
        assignment[account_key] = selected_pack_key
    return counts, assignment


def _compute_distribution_metrics(
    counts: dict[str, int],
    expected: float,
) -> tuple[float, int]:
    """计算标准差与极差。"""
    values = list(counts.values())
    if not values:
        return 0.0, 0
    diffs = [value - expected for value in values]
    std = (sum(item * item for item in diffs) / len(diffs)) ** 0.5
    spread = max(values) - min(values)
    return std, spread


def _compute_weighted_rmse(
    counts: dict[str, int],
    pack_weights: dict[str, float],
    total_accounts: int,
) -> float:
    """计算按权重目标的 RMSE。"""
    if not counts:
        return 0.0
    weight_sum = sum(pack_weights.get(pack_key, 0.0) for pack_key in counts)
    if weight_sum <= 0:
        return 0.0

    errors = []
    for pack_key, assigned in counts.items():
        target = total_accounts * pack_weights.get(pack_key, 0.0) / weight_sum
        errors.append((assigned - target) ** 2)
    return (sum(errors) / len(errors)) ** 0.5


def _select_best_seed_distribution(
    account_keys: list[str],
    pack_keys: list[str],
    pack_weights: dict[str, float],
    epsilon: float,
    seed_candidates: list[str],
) -> tuple[str, dict[str, str], dict[str, float | int]]:
    """评估候选 seed 并返回最佳分配。"""
    if not seed_candidates:
        raise ValueError("seed_candidates 不能为空")

    expected = len(account_keys) / len(pack_keys) if pack_keys else 0.0
    best_seed = ""
    best_assignment: dict[str, str] = {}
    best_metrics: dict[str, float | int] = {
        "weighted_rmse": 0.0,
        "std": 0.0,
        "spread": 0,
    }
    best_tuple: tuple[float, float, int, str] | None = None
    for seed in seed_candidates:
        counts, assignment = _assign_accounts_by_hrw(
            account_keys=account_keys,
            pack_keys=pack_keys,
            pack_weights=pack_weights,
            epsilon=epsilon,
            seed=seed,
        )
        weighted_rmse = _compute_weighted_rmse(
            counts=counts,
            pack_weights=pack_weights,
            total_accounts=len(account_keys),
        )
        std, spread = _compute_distribution_metrics(counts=counts, expected=expected)
        current_tuple = (weighted_rmse, std, spread, seed)
        if best_tuple is None or current_tuple < best_tuple:
            best_tuple = current_tuple
            best_seed = seed
            best_assignment = assignment
            best_metrics = {
                "weighted_rmse": weighted_rmse,
                "std": std,
                "spread": spread,
            }

    return best_seed, cast(dict[str, str], best_assignment), best_metrics


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


def _hash_to_unit(value: str) -> float:
    """稳定哈希到 (0, 1] 浮点数。"""
    hashed = _hash_to_int(value)
    return (hashed + 1) / ((1 << 128) + 1)
