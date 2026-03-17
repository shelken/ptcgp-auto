#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""同步卡牌元数据到数据库（统一复用 FlibustierSyncService）。"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

# 确保项目 src 目录在 sys.path 中
SRC_DIR = Path(__file__).resolve().parent.parent.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ptcgp_auto_v2.db.repositories import CardRepository  # noqa: E402  # 入口脚本需要先调整 sys.path
from ptcgp_auto_v2.services.metadata_sync.flibustier_sync_service import (  # noqa: E402  # 入口脚本需要先调整 sys.path
    FlibustierSyncService,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _format_value(value: Any) -> str:
    """将字段值格式化为日志可读文本。"""
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def _show_preview(plan: dict[str, Any]) -> None:
    """输出同步预览摘要与明细。"""
    summary = plan.get("summary", {})
    operations = plan.get("operations", {})

    logger.info("=" * 50)
    logger.info("本次同步变更预览")
    logger.info("系列写入: %s", summary.get("upsert_sets", 0))
    logger.info("卡包写入: %s", summary.get("upsert_packs", 0))
    logger.info("卡牌更新: %s", summary.get("card_updates", 0))
    logger.info("新增卡包关联: %s", summary.get("card_pack_links_to_add", 0))
    logger.info("删除卡包关联: %s", summary.get("card_pack_links_to_remove", 0))

    set_rows = operations.get("sets", [])
    if set_rows:
        logger.info("系列明细:")
        for row in set_rows:
            logger.info("  - [card_sets] %s %s", row.get("code"), row.get("name"))

    pack_rows = operations.get("packs", [])
    if pack_rows:
        logger.info("卡包明细:")
        for row in pack_rows:
            logger.info(
                "  - [packs] %s (set_code=%s)", row.get("name"), row.get("set_code")
            )

    card_rows = operations.get("cards", [])
    if card_rows:
        logger.info("卡牌明细:")
        for row in card_rows:
            card = row.get("card", {})
            add_packs = row.get("add_pack_names", [])
            logger.info(
                "  - [cards] %s-%03d %s (add_packs=%s)",
                card.get("set_code"),
                int(card.get("number") or 0),
                card.get("name"),
                _format_value(add_packs),
            )
    logger.info("=" * 50)


def _confirm_sync(input_fn: Callable[[str], str] = input) -> bool:
    """确认是否执行写入，只有输入 y 才继续。"""
    print("确认写入数据库吗？输入 y 继续，其他任意输入取消:", flush=True)
    answer = input_fn("> ")
    if answer.strip().lower() != "y":
        logger.info("已取消，未写入数据库")
        return False
    logger.info("确认通过，开始写入数据库")
    return True


def sync_metadata(input_fn: Callable[[str], str] = input) -> bool:
    """同步卡牌元数据，先预览再确认写库。"""
    repo = CardRepository()
    service = FlibustierSyncService(repo)

    sets_data, cards_data, extra_map = service.fetch_remote_metadata()
    plan = service.build_plan(
        mode="force",
        scope_level="all",
        scope_value=None,
        sets_data=sets_data,
        cards_data=cards_data,
        extra_map=extra_map,
    )

    _show_preview(plan)
    if not _confirm_sync(input_fn):
        return False

    result = service.execute_plan(plan.get("operations", {}))
    logger.info("写入完成: %s", json.dumps(result, ensure_ascii=False))
    return True


if __name__ == "__main__":
    if not sync_metadata():
        sys.exit(0)
