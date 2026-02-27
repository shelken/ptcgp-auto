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
    """预览阶段统计出的增删改清单。"""

    new_set_count: int
    new_set_codes: list[str]
    new_card_count: int
    new_pack_count: int
    new_pack_rows: list[tuple[str, str]]
    new_card_pack_link_count: int
    update_rows: list["UpdateRow"]
    delete_rows: list["DeleteRow"]


@dataclass
class FieldChange:
    """字段变更项。"""

    field: str
    old_value: Any
    new_value: Any


@dataclass
class UpdateRow:
    """更新明细行。"""

    table: str
    key: str
    changes: list[FieldChange]


@dataclass
class DeleteRow:
    """删除明细行。"""

    table: str
    key: str
    reason: str


@dataclass
class SyncPayload:
    """写入阶段所需的完整数据载荷。"""

    sets_to_upsert: list[CardSet]
    card_sync_items: list["CardSyncItem"]
    packs_to_upsert: list[Pack]
    preview: SyncPreview


@dataclass
class CardSyncItem:
    """单张卡牌的精确同步计划。"""

    card: Card
    existing_card_id: int | None
    added_pack_names: list[str]
    removed_pack_names: list[str]
    needs_card_upsert: bool


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


def _merge_set_label_data(existing_label_data: str | None, name_val: Any) -> str:
    """合并系列多语言标签，保留本地已有语言并用远端值更新同名语言。"""
    existing_labels: dict[str, Any] = {}
    if existing_label_data:
        try:
            parsed_existing = json.loads(existing_label_data)
            if isinstance(parsed_existing, dict):
                existing_labels = parsed_existing
        except (TypeError, ValueError):
            existing_labels = {}

    incoming_labels: dict[str, Any] = {}
    if isinstance(name_val, dict):
        incoming_labels = name_val
    elif isinstance(name_val, str):
        incoming_labels = {"en": name_val}

    merged_labels = dict(existing_labels)
    merged_labels.update(incoming_labels)
    return json.dumps(merged_labels, ensure_ascii=False)


def _normalize_json_text(raw_text: str | None) -> str:
    """规范化 JSON 文本，用于字段值比较。"""
    if not raw_text:
        return ""
    try:
        return json.dumps(json.loads(raw_text), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return raw_text


def _is_set_changed(existing_set: Any, incoming_set: CardSet) -> bool:
    """判断系列字段是否发生变化。"""
    if existing_set is None:
        return True
    return any(
        [
            existing_set.name != incoming_set.name,
            existing_set.release_date != incoming_set.release_date,
            int(existing_set.total_cards or 0) != int(incoming_set.total_cards or 0),
            _normalize_json_text(existing_set.label_data)
            != _normalize_json_text(incoming_set.label_data),
        ]
    )


def _is_card_changed(existing_card: Any, incoming_card: Card) -> bool:
    """判断卡牌字段是否发生变化。"""
    if existing_card is None:
        return True

    fields = [
        "name",
        "rarity",
        "image_url",
        "element",
        "type",
        "stage",
        "health",
        "weakness",
        "retreat_cost",
    ]
    for field_name in fields:
        if getattr(existing_card, field_name) != getattr(incoming_card, field_name):
            return True

    return _normalize_json_text(existing_card.data) != _normalize_json_text(
        incoming_card.data
    )


def _collect_set_changes(existing_set: Any, incoming_set: CardSet) -> list[FieldChange]:
    """收集系列字段变更明细。"""
    if existing_set is None:
        return []

    changes: list[FieldChange] = []
    if existing_set.name != incoming_set.name:
        changes.append(FieldChange("name", existing_set.name, incoming_set.name))
    if existing_set.release_date != incoming_set.release_date:
        changes.append(
            FieldChange(
                "release_date", existing_set.release_date, incoming_set.release_date
            )
        )
    if int(existing_set.total_cards or 0) != int(incoming_set.total_cards or 0):
        changes.append(
            FieldChange(
                "total_cards",
                int(existing_set.total_cards or 0),
                int(incoming_set.total_cards or 0),
            )
        )
    existing_label = _normalize_json_text(existing_set.label_data)
    incoming_label = _normalize_json_text(incoming_set.label_data)
    if existing_label != incoming_label:
        changes.append(FieldChange("label_data", existing_label, incoming_label))
    return changes


def _collect_card_changes(existing_card: Any, incoming_card: Card) -> list[FieldChange]:
    """收集卡牌字段变更明细。"""
    if existing_card is None:
        return []

    changes: list[FieldChange] = []
    fields = [
        "name",
        "rarity",
        "image_url",
        "element",
        "type",
        "stage",
        "health",
        "weakness",
        "retreat_cost",
    ]
    for field_name in fields:
        old_value = getattr(existing_card, field_name)
        new_value = getattr(incoming_card, field_name)
        if old_value != new_value:
            changes.append(FieldChange(field_name, old_value, new_value))

    old_data = _normalize_json_text(existing_card.data)
    new_data = _normalize_json_text(incoming_card.data)
    if old_data != new_data:
        changes.append(FieldChange("data", old_data, new_data))

    return changes


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
    card_sync_items: list[CardSyncItem] = []
    detected_packs: dict[str, str] = {}

    new_set_codes: list[str] = []
    new_cards: list[tuple[str, int]] = []
    new_pack_names: list[str] = []
    new_card_pack_link_count = 0
    update_rows: list[UpdateRow] = []
    delete_rows: list[DeleteRow] = []

    for sets in sets_data.values():
        for set_item in sets:
            code = set_item.get("code")
            if not code:
                continue

            code_str = str(code)

            name_val = set_item.get("name", {})
            name = (
                name_val.get("en", str(name_val))
                if isinstance(name_val, dict)
                else str(name_val)
            )

            existing_set = repo.get_set_by_code(code_str)
            if existing_set is None:
                new_set_codes.append(code_str)

            label_data = _merge_set_label_data(
                existing_set.label_data if existing_set else None,
                name_val,
            )

            incoming_set = CardSet(
                code=code_str,
                name=name,
                release_date=set_item.get("releaseDate"),
                total_cards=set_item.get("count", 0),
                label_data=label_data,
            )
            if _is_set_changed(existing_set, incoming_set):
                sets_to_upsert.append(incoming_set)
                set_changes = _collect_set_changes(existing_set, incoming_set)
                if set_changes:
                    update_rows.append(
                        UpdateRow(
                            table="card_sets",
                            key=code_str,
                            changes=set_changes,
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

        existing_card = repo.get_card_by_set_and_number(set_code_str, number)
        if existing_card is None:
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
        packs = [str(pack_name) for pack_name in card_item.get("packs", [])]
        existing_pack_names: list[str] = []
        if existing_card and existing_card.id is not None:
            existing_pack_names = repo.get_card_pack_names(existing_card.id)

        needs_card_upsert = _is_card_changed(existing_card, card)
        card_changes = _collect_card_changes(existing_card, card)
        if card_changes:
            update_rows.append(
                UpdateRow(
                    table="cards",
                    key=f"{set_code_str}-{number:03d}",
                    changes=card_changes,
                )
            )

        existing_pack_set = set(existing_pack_names)
        incoming_pack_set = set(packs)
        added_pack_names = sorted(incoming_pack_set - existing_pack_set)
        removed_pack_names = sorted(existing_pack_set - incoming_pack_set)
        if added_pack_names:
            new_card_pack_link_count += len(added_pack_names)
        for pack_name in removed_pack_names:
            delete_rows.append(
                DeleteRow(
                    table="card_packs",
                    key=f"{set_code_str}-{number:03d}",
                    reason=f"删除关联 pack_name={pack_name}",
                )
            )
        needs_pack_sync = bool(added_pack_names or removed_pack_names)

        if needs_card_upsert or needs_pack_sync:
            card_sync_items.append(
                CardSyncItem(
                    card=card,
                    existing_card_id=existing_card.id if existing_card else None,
                    added_pack_names=added_pack_names,
                    removed_pack_names=removed_pack_names,
                    needs_card_upsert=needs_card_upsert,
                )
            )

        for pack_name in packs:
            if pack_name not in detected_packs:
                detected_packs[pack_name] = set_code_str

    packs_to_upsert: list[Pack] = []
    for pack_name, set_code in detected_packs.items():
        existing_pack = repo.get_pack_by_name(pack_name)
        if existing_pack is None:
            new_pack_names.append(pack_name)
            new_card_pack_link_count += 0
        incoming_pack = Pack(
            name=pack_name,
            set_code=set_code,
            label_data=json.dumps({"en": pack_name}, ensure_ascii=False),
        )
        if existing_pack is None or existing_pack.set_code != incoming_pack.set_code:
            if (
                existing_pack is not None
                and existing_pack.set_code != incoming_pack.set_code
            ):
                update_rows.append(
                    UpdateRow(
                        table="packs",
                        key=pack_name,
                        changes=[
                            FieldChange(
                                "set_code",
                                existing_pack.set_code,
                                incoming_pack.set_code,
                            )
                        ],
                    )
                )
            packs_to_upsert.append(
                Pack(
                    name=pack_name,
                    set_code=set_code,
                    label_data=json.dumps({"en": pack_name}, ensure_ascii=False),
                )
            )

    return SyncPayload(
        sets_to_upsert=sets_to_upsert,
        card_sync_items=card_sync_items,
        packs_to_upsert=packs_to_upsert,
        preview=SyncPreview(
            new_set_count=len(new_set_codes),
            new_set_codes=sorted(new_set_codes),
            new_card_count=len(new_cards),
            new_pack_count=len(new_pack_names),
            new_pack_rows=sorted(
                (name, detected_packs[name]) for name in new_pack_names
            ),
            new_card_pack_link_count=new_card_pack_link_count,
            update_rows=update_rows,
            delete_rows=delete_rows,
        ),
    )


def _format_value(value: Any) -> str:
    """将字段值格式化为日志可读文本。"""
    if isinstance(value, str):
        return value
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def show_preview(preview: SyncPreview) -> None:
    """输出本次将写入数据库的增删改清单。"""
    logger.info("=" * 50)
    logger.info("本次同步变更预览")
    logger.info("新增系列: %s", preview.new_set_count)
    if preview.new_set_codes:
        for set_code in preview.new_set_codes:
            logger.info("  - [card_sets] %s", set_code)
    logger.info("新增卡牌: %s", preview.new_card_count)
    logger.info("新增卡包: %s", preview.new_pack_count)
    if preview.new_pack_rows:
        for pack_name, set_code in preview.new_pack_rows:
            logger.info("  - [packs] %s (set_code=%s)", pack_name, set_code)
    logger.info("新增卡包关联: %s", preview.new_card_pack_link_count)

    logger.info("更新明细: %s", len(preview.update_rows))
    if not preview.update_rows:
        logger.info("  - 无")
    else:
        for row in preview.update_rows:
            for change in row.changes:
                logger.info(
                    "  - [%s] %s 字段 %s: %s -> %s",
                    row.table,
                    row.key,
                    change.field,
                    _format_value(change.old_value),
                    _format_value(change.new_value),
                )

    logger.info("删除明细: %s", len(preview.delete_rows))
    if not preview.delete_rows:
        logger.info("  - 无")
    else:
        for row in preview.delete_rows:
            logger.info("  - [%s] %s (%s)", row.table, row.key, row.reason)
    logger.info("=" * 50)


def confirm_sync(input_fn: Callable[[str], str] = input) -> bool:
    """确认是否执行写入，只有输入 y 才继续。"""
    print("确认写入数据库吗？输入 y 继续，其他任意输入取消:", flush=True)
    answer = input_fn("> ")
    if answer.strip().lower() != "y":
        logger.info("已取消，未写入数据库")
        return False
    logger.info("确认通过，开始写入数据库")
    return True


def execute_sync(repo: CardRepository, payload: SyncPayload) -> None:
    """执行数据库写入阶段。"""
    for card_set in payload.sets_to_upsert:
        repo.upsert_set(card_set)

    for index, item in enumerate(payload.card_sync_items, start=1):
        card_id: int | None = item.existing_card_id
        if item.needs_card_upsert:
            saved_card = repo.upsert_card(item.card)
            card_id = saved_card.id  # type: ignore[assignment]

        if card_id is not None:
            for pack_name in item.removed_pack_names:
                repo.remove_card_pack(card_id, pack_name)
            for pack_name in item.added_pack_names:
                repo.add_card_pack(card_id, pack_name)

        if index % 100 == 0:
            print(f"Processed {index} cards...", end="\r")

    for pack in payload.packs_to_upsert:
        repo.upsert_pack_safe(pack)

    logger.info(
        "写入完成：sets=%s cards=%s packs=%s",
        len(payload.sets_to_upsert),
        len(payload.card_sync_items),
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
