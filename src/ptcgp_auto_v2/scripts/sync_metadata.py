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

from ptcgp_auto_v2.db.models import Card, CardSet
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

            card_set = CardSet(
                code=code,
                name=name,
                release_date=s.get("releaseDate"),
                total_cards=s.get("count", 0),
            )
            repo.upsert_set(card_set)
            total_sets += 1

    logger.info(f"Synced {total_sets} sets.")

    # 2. Sync Cards
    logger.info(f"Fetching cards from {CARDS_URL}...")
    try:
        response = requests.get(CARDS_URL, timeout=60)
        response.raise_for_status()
        cards_data = response.json()
    except Exception as e:
        logger.error(f"Failed to fetch cards: {e}")
        sys.exit(1)

    total_cards = 0
    for i, c in enumerate(cards_data):
        # c: {set, number, name, rarity, image, packs: [], ...}
        set_code = c.get("set")
        number = c.get("number")

        if not set_code or number is None:
            continue

        card = Card(
            set_code=set_code,
            number=number,
            name=c.get("name", ""),
            rarity=c.get("rarity", ""),
            image_url=c.get("image", ""),
            data=json.dumps(c, ensure_ascii=False),  # Backup full data
        )

        saved_card = repo.upsert_card(card)

        # 3. Sync Card Packs
        # Clear existing packs first to handle updates
        repo.clear_card_packs(saved_card.id)  # type: ignore

        packs = c.get("packs", [])
        for pack_name in packs:
            repo.add_card_pack(saved_card.id, pack_name)  # type: ignore

        total_cards += 1
        if total_cards % 100 == 0:
            print(f"Processed {total_cards} cards...", end="\r")

    logger.info(f"\nSynced {total_cards} cards.")

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
