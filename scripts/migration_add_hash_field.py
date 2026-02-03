#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库迁移脚本：添加 perceptual_hash 字段并预填充数据
利用 yolo-card-training/data/raw/cards/ 目录下的现有图片（如果存在）
"""

import sys
from pathlib import Path
from sqlalchemy import text
from PIL import Image

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.repositories import CardRepository
from ptcgp_auto_v2.utils.perceptual_hash import (
    pil_to_color_pixels,
    calculate_perceptual_hash,
    encode_hash_to_base64,
)

# 本地卡牌图片目录（yolo-card-training项目中的图片）
LOCAL_CARDS_DIR = Path("yolo-card-training/data/raw/cards")


def add_hash_column():
    """添加 perceptual_hash 字段到 Card 表"""
    engine = get_engine()
    with engine.connect() as conn:
        # 检查字段是否已存在
        result = conn.execute(text("PRAGMA table_info(cards)"))
        columns = [row[1] for row in result.fetchall()]

        if "perceptual_hash" in columns:
            print("✅ perceptual_hash 字段已存在，跳过添加")
            return

        conn.execute(text("ALTER TABLE cards ADD COLUMN perceptual_hash VARCHAR(255)"))
        conn.commit()
    print("✅ 已添加 perceptual_hash 字段")


def fill_hash_from_local_images():
    """利用本地图片预填充 perceptual_hash"""
    repo = CardRepository()

    if not LOCAL_CARDS_DIR.exists():
        print(f"⚠️ 本地卡牌目录不存在: {LOCAL_CARDS_DIR}")
        print("跳过预填充，将在首次扫描时自动下载")
        return 0, 0

    print(f"📂 扫描本地卡牌目录: {LOCAL_CARDS_DIR}")

    total_processed = 0
    total_success = 0

    # 遍历所有系列目录
    set_dirs = [d for d in LOCAL_CARDS_DIR.iterdir() if d.is_dir()]

    for set_dir in sorted(set_dirs):
        set_code = set_dir.name

        # 查找该系列下的所有卡牌图片
        card_files = []
        for ext in [".webp", ".png", ".jpg"]:
            card_files.extend(set_dir.glob(f"*{ext}"))

        set_success = 0
        for card_file in sorted(card_files):
            try:
                # 从文件名提取卡牌编号（如 "001.webp" -> 1）
                card_number = int(card_file.stem)

                # 查找数据库中对应的卡牌
                card = repo.get_card_by_set_and_number(set_code, card_number)
                if not card:
                    continue

                # 如果已有hash，跳过
                if card.perceptual_hash:
                    continue

                # 读取图片并计算hash
                pil_img = Image.open(card_file)
                color_pixels = pil_to_color_pixels(pil_img)
                hash_arr = calculate_perceptual_hash(color_pixels)
                hash_str = encode_hash_to_base64(hash_arr)

                # 更新数据库
                if repo.update_card_hash(card.id, hash_str):
                    set_success += 1
                    total_success += 1

                total_processed += 1

            except Exception as e:
                # 静默跳过错误（文件名不符合格式或计算失败）
                pass

        if set_success > 0:
            print(f"  ✅ {set_code}: 成功填充 {set_success} 张卡牌")

    return total_processed, total_success


def main():
    print("=" * 60)
    print("数据库迁移：添加 perceptual_hash 字段")
    print("=" * 60)

    # 1. 添加字段
    add_hash_column()

    # 2. 预填充数据
    print("\n🔄 开始预填充 perceptual_hash 数据...")
    processed, success = fill_hash_from_local_images()

    print("\n" + "=" * 60)
    print("迁移完成")
    print("=" * 60)
    print(f"  处理卡牌: {processed} 张")
    print(f"  成功填充: {success} 张")
    print(f"\n💡 提示：未填充的卡牌将在首次扫描时自动下载")


if __name__ == "__main__":
    main()
