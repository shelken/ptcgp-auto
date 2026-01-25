#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步卡牌元数据到数据库

1. 从 GitHub 获取 sets.json 和 cards.json
2. 更新 card_sets, cards, card_packs 表
3. 生成 data/packs.json 以兼容旧代码
"""

import json
import logging
import sys
from pathlib import Path

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
PACKS_JSON_PATH = ROOT_DIR / "data" / "packs.json"


def sync_metadata():
    repo = CardRepository()

    # 1. Sync Sets
    logger.info(f"Fetching sets from {SETS_URL}...")
    try:
        response = requests.get(SETS_URL, timeout=30)
        response.raise_for_status()
        sets_data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch sets: {e}")
        sys.exit(1)

    # sets_data structure: {"A": [...], "B": [...]}
    total_sets = 0
    for series, sets in sets_data.items():
        for s in sets:
            # s: {code, name: {en: ...}, releaseDate, count, ...}
            code = s.get("code")
            if not code:
                continue

            # Handle name (it's a dict or string)
            name_val = s.get("name", {})
            name = (
                name_val.get("en", str(name_val))
                if isinstance(name_val, dict)
                else str(name_val)
            )

            # 序列化 name_val 到 label_data
            label_data = "{}"
            if isinstance(name_val, dict):
                label_data = json.dumps(name_val, ensure_ascii=False)
            elif isinstance(name_val, str):
                 # 如果只是字符串，尝试构造简单的 JSON
                label_data = json.dumps({"en": name_val}, ensure_ascii=False)

            card_set = CardSet(
                code=code,
                name=name,
                release_date=s.get("releaseDate"),
                total_cards=s.get("count", 0),
                label_data=label_data,
            )
            repo.upsert_set(card_set)
            total_sets += 1

    logger.info(f"Synced {total_sets} sets.")

    # 2. Sync Cards & Collect Packs
    logger.info(f"Fetching cards from {CARDS_URL}...")
    logger.info(f"Fetching extra card data from {CARDS_EXTRA_URL}...")

    try:
        # 同时获取基础数据和额外数据
        resp_cards = requests.get(CARDS_URL, timeout=60)
        resp_cards.raise_for_status()
        cards_data = resp_cards.json()

        resp_extra = requests.get(CARDS_EXTRA_URL, timeout=60)
        resp_extra.raise_for_status()
        extra_data = resp_extra.json()

        # 构建 extra 数据索引 (set_code + number -> data)
        # 兼容处理：extra 中的 set 可能是 key "set"
        extra_map = {}
        for item in extra_data:
            s = item.get("set")
            n = item.get("number")
            if s and n is not None:
                key = f"{s}_{n}"
                extra_map[key] = item

        logger.info(f"Indexed {len(extra_map)} extra card details.")

    except Exception as e:
        logger.error(f"Failed to fetch cards data: {e}")
        sys.exit(1)

    total_cards = 0
    # 收集所有的 packs: (set_code, pack_name) -> image_url (暂无)
    # 我们用一个字典来存储发现的 packs
    detected_packs = {} # key: pack_name, value: set_code

    for i, c in enumerate(cards_data):
        # c: {set, number, name, rarity, image, packs: [], ...}
        set_code = c.get("set")
        number = c.get("number")

        if not set_code or number is None:
            continue

        # 查找额外数据
        extra = extra_map.get(f"{set_code}_{number}", {})

        # 提取新字段，带简单的类型转换
        health = extra.get("health")
        if health is not None:
            try:
                health = int(health)
            except (ValueError, TypeError):
                health = None

        retreat_cost = extra.get("retreatCost")
        if retreat_cost is not None:
            try:
                retreat_cost = int(retreat_cost)
            except (ValueError, TypeError):
                retreat_cost = None

        card = Card(
            set_code=set_code,
            number=number,
            name=c.get("name", ""),
            rarity=c.get("rarity", ""),
            image_url=c.get("image", ""),

            # 新增字段 (优先从 extra 获取，若无则为 None)
            element=str(extra.get("element")) if extra.get("element") else None,
            type=str(extra.get("type")) if extra.get("type") else None,
            stage=str(extra.get("stage")) if extra.get("stage") else None,
            health=health,
            weakness=str(extra.get("weakness")) if extra.get("weakness") else None,
            retreat_cost=retreat_cost,

            data=json.dumps(c, ensure_ascii=False),  # Backup full data
        )

        saved_card = repo.upsert_card(card)

        # 3. Sync Card Packs
        # Clear existing packs first to handle updates
        repo.clear_card_packs(saved_card.id)  # type: ignore

        packs = c.get("packs", [])
        for pack_name in packs:
            repo.add_card_pack(saved_card.id, pack_name)  # type: ignore
            # Record pack for later sync
            if pack_name not in detected_packs:
                detected_packs[pack_name] = set_code # 假设第一个遇到的 set_code 是该 pack 的归属

        total_cards += 1
        if total_cards % 100 == 0:
            print(f"Processed {total_cards} cards...", end="\r")

    logger.info(f"\nSynced {total_cards} cards.")

    # 3.5 Sync Packs Table
    logger.info(f"Syncing {len(detected_packs)} packs metadata...")
    for pack_name, set_code in detected_packs.items():
        # 默认 label_data 包含英文名
        default_label = json.dumps({"en": pack_name}, ensure_ascii=False)
        pack = Pack(
            name=pack_name,
            set_code=set_code,
            label_data=default_label
        )
        repo.upsert_pack_safe(pack)

    # 4. Generate packs.json
    generate_packs_json(repo)

    # 4. Generate packs.json
    generate_packs_json(repo)


def generate_packs_json(repo: CardRepository):
    logger.info("Generating data/packs.json...")

    sets = repo.get_all_sets()
    output = {}

    for s in sets:
        # Get packs for this set
        pack_data = repo.get_packs_by_set(s.code)
        if pack_data:
            output.update(pack_data)

    # Sort
    output = dict(sorted(output.items()))

    # Ensure parent dir exists
    PACKS_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(PACKS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(output)} sets to {PACKS_JSON_PATH}")


if __name__ == "__main__":
    sync_metadata()
