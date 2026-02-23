#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步卡牌元数据到数据库

1. 从 GitHub 获取 sets.json 和 cards.json
2. 更新 card_sets, cards, card_packs 表
"""

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests

# 确保项目 src 目录在 sys.path 中
SRC_DIR = Path(__file__).resolve().parent.parent.parent
ROOT_DIR = SRC_DIR.parent
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ptcgp_auto_v2.db.models import Card, CardSet, Pack
from ptcgp_auto_v2.db.repositories import CardRepository

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = (
    "https://raw.githubusercontent.com/flibustier/pokemon-tcg-pocket-database/main/dist"
)
SETS_URL = f"{BASE_URL}/sets.json"
CARDS_URL = f"{BASE_URL}/cards.json"
CARDS_EXTRA_URL = f"{BASE_URL}/cards.extra.json"


@dataclass
class SyncPreview:
    """预览阶段统计出的新增数据清单。"""

    new_set_codes: list[str]
    new_cards: list[tuple[str, int]]
    new_pack_names: list[str]


@dataclass
class SyncPayload:
    """写入阶段所需的完整数据载荷。"""

    sets_to_upsert: list[CardSet]
    cards_to_upsert: list[Card]
    card_packs_map: dict[tuple[str, int], list[str]]
    packs_to_upsert: list[Pack]
    preview: SyncPreview


def _normalize_number(value: Any) -> int | None:
    """将卡牌编号规范化为 int，不可解析时返回 None。"""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _build_extra_map(
    extra_data: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, Any]]:
    """构建额外元数据索引，键为(set_code, number)。"""
    extra_map: dict[tuple[str, int], dict[str, Any]] = {}
    for item in extra_data:
        set_code = item.get("set")
        number = _normalize_number(item.get("number"))
        if set_code and number is not None:
            extra_map[(str(set_code), number)] = item
    return extra_map


def fetch_remote_metadata() -> tuple[
    dict[str, list[dict[str, Any]]],
    list[dict[str, Any]],
    dict[tuple[str, int], dict[str, Any]],
]:
    """拉取远端 metadata，并返回 sets/cards/extra 索引。"""
    logger.info(f"Fetching sets from {SETS_URL}...")
    try:
        response = requests.get(SETS_URL, timeout=30)
        response.raise_for_status()
        sets_data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch sets: {e}")
        sys.exit(1)

    logger.info(f"Fetching cards from {CARDS_URL}...")
    logger.info(f"Fetching extra card data from {CARDS_EXTRA_URL}...")
    try:
        resp_cards = requests.get(CARDS_URL, timeout=60)
        resp_cards.raise_for_status()
        cards_data = resp_cards.json()

        resp_extra = requests.get(CARDS_EXTRA_URL, timeout=60)
        resp_extra.raise_for_status()
        extra_data = resp_extra.json()
    except Exception as e:
        logger.error(f"Failed to fetch cards data: {e}")
        sys.exit(1)

    extra_map = _build_extra_map(extra_data)
    logger.info(f"Indexed {len(extra_map)} extra card details.")
    return sets_data, cards_data, extra_map


def build_sync_payload(
    repo: CardRepository,
    sets_data: dict[str, list[dict[str, Any]]],
    cards_data: list[dict[str, Any]],
    extra_map: dict[tuple[str, int], dict[str, Any]],
) -> SyncPayload:
    """仅构建预览与写入载荷，不触发任何数据库写入。"""
    sets_to_upsert: list[CardSet] = []
    cards_to_upsert: list[Card] = []
    card_packs_map: dict[tuple[str, int], list[str]] = {}
    detected_packs: dict[str, str] = {}

    new_set_codes: list[str] = []
    new_cards: list[tuple[str, int]] = []
    new_pack_names: list[str] = []

    for sets in sets_data.values():
        for set_item in sets:
            code = set_item.get("code")
            if not code:
                continue

            name_val = set_item.get("name", {})
            name = (
                name_val.get("en", str(name_val))
                if isinstance(name_val, dict)
                else str(name_val)
            )

            label_data = "{}"
            if isinstance(name_val, dict):
                label_data = json.dumps(name_val, ensure_ascii=False)
            elif isinstance(name_val, str):
                label_data = json.dumps({"en": name_val}, ensure_ascii=False)

            if repo.get_set_by_code(str(code)) is None:
                new_set_codes.append(str(code))

            sets_to_upsert.append(
                CardSet(
                    code=str(code),
                    name=name,
                    release_date=set_item.get("releaseDate"),
                    total_cards=set_item.get("count", 0),
                    label_data=label_data,
                )
            )

    for card_item in cards_data:
        set_code = card_item.get("set")
        number = _normalize_number(card_item.get("number"))
        if not set_code or number is None:
            continue

        set_code_str = str(set_code)
        extra = extra_map.get((set_code_str, number), {})

        health = _normalize_number(extra.get("health"))
        retreat_cost = _normalize_number(extra.get("retreatCost"))

        if repo.get_card_by_set_and_number(set_code_str, number) is None:
            new_cards.append((set_code_str, number))

        card = Card(
            set_code=set_code_str,
            number=number,
            name=card_item.get("name", ""),
            rarity=card_item.get("rarity", ""),
            image_url=card_item.get("image", ""),
            element=str(extra.get("element")) if extra.get("element") else None,
            type=str(extra.get("type")) if extra.get("type") else None,
            stage=str(extra.get("stage")) if extra.get("stage") else None,
            health=health,
            weakness=str(extra.get("weakness")) if extra.get("weakness") else None,
            retreat_cost=retreat_cost,
            data=json.dumps(card_item, ensure_ascii=False),
        )
        cards_to_upsert.append(card)

        packs = [str(pack_name) for pack_name in card_item.get("packs", [])]
        card_packs_map[(set_code_str, number)] = packs

        for pack_name in packs:
            if pack_name not in detected_packs:
                detected_packs[pack_name] = set_code_str

    packs_to_upsert: list[Pack] = []
    for pack_name, set_code in detected_packs.items():
        if repo.get_pack_by_name(pack_name) is None:
            new_pack_names.append(pack_name)

        packs_to_upsert.append(
            Pack(
                name=pack_name,
                set_code=set_code,
                label_data=json.dumps({"en": pack_name}, ensure_ascii=False),
            )
        )

    return SyncPayload(
        sets_to_upsert=sets_to_upsert,
        cards_to_upsert=cards_to_upsert,
        card_packs_map=card_packs_map,
        packs_to_upsert=packs_to_upsert,
        preview=SyncPreview(
            new_set_codes=sorted(new_set_codes),
            new_cards=sorted(new_cards),
            new_pack_names=sorted(new_pack_names),
        ),
    )


def _log_preview_items(title: str, items: list[str], max_preview: int = 8) -> None:
    """打印新增清单，避免输出过长。"""
    logger.info(f"{title}: {len(items)}")
    if not items:
        logger.info("  - 无")
        return

    preview_items = items[:max_preview]
    for item in preview_items:
        logger.info(f"  - {item}")
    remain = len(items) - len(preview_items)
    if remain > 0:
        logger.info(f"  ... 另有 {remain} 条")


def show_preview(preview: SyncPreview) -> None:
    """输出本次将新增写入数据库的数据清单。"""
    logger.info("=" * 50)
    logger.info("本次同步新增预览（仅展示将新增写入的记录）")
    _log_preview_items("新增系列", preview.new_set_codes)
    _log_preview_items(
        "新增卡牌",
        [f"{set_code}-{number:03d}" for set_code, number in preview.new_cards],
    )
    _log_preview_items("新增卡包", preview.new_pack_names)
    logger.info("=" * 50)


def confirm_sync(input_fn: Callable[[str], str] = input) -> bool:
    """确认是否执行写入，只有输入 y 才继续。"""
    answer = input_fn("确认写入数据库吗？输入 y 继续，其他任意输入取消: ")
    if answer.strip().lower() != "y":
        logger.info("已取消，未写入数据库")
        return False
    return True


def execute_sync(repo: CardRepository, payload: SyncPayload) -> None:
    """执行数据库写入阶段。"""
    for card_set in payload.sets_to_upsert:
        repo.upsert_set(card_set)

    for index, card in enumerate(payload.cards_to_upsert, start=1):
        saved_card = repo.upsert_card(card)
        repo.clear_card_packs(saved_card.id)  # type: ignore[arg-type]
        for pack_name in payload.card_packs_map.get((card.set_code, card.number), []):
            repo.add_card_pack(saved_card.id, pack_name)  # type: ignore[arg-type]

        if index % 100 == 0:
            print(f"Processed {index} cards...", end="\r")

    for pack in payload.packs_to_upsert:
        repo.upsert_pack_safe(pack)

    logger.info(
        "写入完成：sets=%s cards=%s packs=%s",
        len(payload.sets_to_upsert),
        len(payload.cards_to_upsert),
        len(payload.packs_to_upsert),
    )


def sync_metadata(input_fn: Callable[[str], str] = input) -> bool:
    """同步卡牌元数据，先预览新增，再确认写入。"""
    repo = CardRepository()
    sets_data, cards_data, extra_map = fetch_remote_metadata()
    payload = build_sync_payload(repo, sets_data, cards_data, extra_map)

    show_preview(payload.preview)
    if not confirm_sync(input_fn):
        return False

    execute_sync(repo, payload)
    return True


if __name__ == "__main__":
    if not sync_metadata():
        sys.exit(0)
