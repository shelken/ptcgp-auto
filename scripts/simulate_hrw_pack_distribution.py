#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HRW 分配结果查看脚本（复用正式选包逻辑）。"""

from __future__ import annotations

from ptcgp_auto_v2.config.constants import (
    PACK_AUTO_EXCLUDE_SET_CODES,
    PACK_AUTO_HRW_AGGRESSIVENESS,
    PACK_AUTO_HRW_SEED,
    PACK_AUTO_HRW_SEED_SCAN_COUNT,
    PACK_AUTO_HRW_TARGET_RARITIES,
    PACK_SERIES_CODES,
)
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.pack_auto_selector import (
    get_hrw_distribution_snapshot,
)


def run_simulation() -> None:
    """运行并输出当前正式 HRW 分配快照。"""
    with session_scope() as session:
        snapshot = get_hrw_distribution_snapshot(
            card_repo=CardRepository(session),
            exclude_set_codes=PACK_AUTO_EXCLUDE_SET_CODES,
            force_rebuild=True,
        )
    if not snapshot:
        raise RuntimeError("未构建出 HRW 分配快照，请检查候选包与数据库数据")

    pack_map = snapshot["pack_map"]
    assignment_map = snapshot["assignment_map"]
    progress_stats = snapshot["progress_stats"]
    progress_ratio_map = snapshot["progress_ratio_map"]
    pack_weights = snapshot["pack_weights"]
    account_count = int(snapshot["account_count"])
    candidate_count = int(snapshot["candidate_count"])
    selected_seed = str(snapshot["selected_seed"])
    best_metrics = snapshot["best_metrics"]
    effective_scale = float(snapshot["effective_scale"])
    effective_weight_max = float(snapshot["effective_weight_max"])
    effective_epsilon = float(snapshot["effective_epsilon"])

    assigned_counts: dict[str, int] = {pack_key: 0 for pack_key in pack_map}
    for pack_key in assignment_map.values():
        if pack_key in assigned_counts:
            assigned_counts[pack_key] += 1

    expected = account_count / candidate_count if candidate_count else 0.0
    rows = []
    for pack_key, pack in sorted(
        pack_map.items(), key=lambda item: (item[1].set_code, item[1].name)
    ):
        stat = progress_stats.get(pack.name, {"owned_target": 0, "total_target": 0})
        owned_target = int(stat.get("owned_target", 0) or 0)
        total_target = int(stat.get("total_target", 0) or 0)
        assigned = int(assigned_counts.get(pack_key, 0))
        rows.append(
            {
                "set_code": pack.set_code,
                "pack_name": pack.name,
                "assigned": assigned,
                "owned_target": owned_target,
                "total_target": total_target,
                "ratio": float(progress_ratio_map.get(pack_key, 1.0)),
                "weight": float(pack_weights.get(pack_key, 1.0)),
                "dev": assigned - expected,
            }
        )

    print("=" * 100)
    print("HRW 加权分配模拟（复用正式策略逻辑）")
    print("=" * 100)
    print(
        f"候选系列前缀: {PACK_SERIES_CODES}\n"
        f"排除系列: {PACK_AUTO_EXCLUDE_SET_CODES}\n"
        f"目标稀有度: {PACK_AUTO_HRW_TARGET_RARITIES}\n"
        f"参数: aggressiveness={PACK_AUTO_HRW_AGGRESSIVENESS}, "
        f"scale={effective_scale:.3f}, epsilon={effective_epsilon:.3f}, "
        f"weight_max={effective_weight_max:.3f}, "
        f"seed_base={PACK_AUTO_HRW_SEED}, seed_scan_count={PACK_AUTO_HRW_SEED_SCAN_COUNT}"
    )
    print(
        f"账号数={account_count}, 子包数={candidate_count}, 期望均值={expected:.2f}, "
        f"weighted_rmse={float(best_metrics['weighted_rmse']):.3f}, "
        f"std={float(best_metrics['std']):.3f}, spread={int(best_metrics['spread'])}"
    )
    print("-" * 100)
    print("最终使用seed（单一）")
    print(
        f"seed={selected_seed} weighted_rmse={float(best_metrics['weighted_rmse']):.3f} "
        f"std={float(best_metrics['std']):.3f} spread={int(best_metrics['spread'])}"
    )
    print("-" * 100)
    print(
        f"{'set':<6} {'pack':<22} {'assigned':>9} {'progress':>14} "
        f"{'ratio':>7} {'weight':>7} {'dev':>8}"
    )
    print("-" * 100)
    for row in rows:
        print(
            f"{row['set_code']:<6} "
            f"{row['pack_name'][:22]:<22} "
            f"{row['assigned']:>9} "
            f"{row['owned_target']:>4}/{row['total_target']:<9} "
            f"{row['ratio']:>7.4f} "
            f"{row['weight']:>7.3f} "
            f"{row['dev']:>+8.2f}"
        )
    print("=" * 100)


if __name__ == "__main__":
    run_simulation()
