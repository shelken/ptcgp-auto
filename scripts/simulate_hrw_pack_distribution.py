#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HRW 分配结果查看脚本（复用正式选包逻辑）。"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保可导入 src 下项目模块
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ptcgp_auto_v2.config.constants import (  # noqa: E402
    PACK_AUTO_EXCLUDE_SET_CODES,
    PACK_AUTO_HRW_LOAD_EPSILON,
    PACK_AUTO_HRW_PROGRESS_BETA,
    PACK_AUTO_HRW_SEED,
    PACK_AUTO_HRW_SEED_SCAN_COUNT,
    PACK_AUTO_HRW_TARGET_RARITIES,
    PACK_AUTO_HRW_WEIGHT_MAX,
    PACK_AUTO_HRW_WEIGHT_MIN,
    PACK_SERIES_CODES,
)
from ptcgp_auto_v2.db.repositories import CardRepository  # noqa: E402
from ptcgp_auto_v2.utils.pack_auto_selector import (  # noqa: E402
    get_hrw_distribution_snapshot,
)


def run_simulation() -> None:
    """运行并输出当前正式 HRW 分配快照。"""
    card_repo = CardRepository()
    snapshot = get_hrw_distribution_snapshot(
        card_repo=card_repo,
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
        f"参数: beta={PACK_AUTO_HRW_PROGRESS_BETA}, epsilon={PACK_AUTO_HRW_LOAD_EPSILON}, "
        f"weight=[{PACK_AUTO_HRW_WEIGHT_MIN}, {PACK_AUTO_HRW_WEIGHT_MAX}], "
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
