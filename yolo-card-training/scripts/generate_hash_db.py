#!/usr/bin/env python3
"""
生成 A1 系列卡牌哈希数据库
遍历 data/raw/cards/ 目录，计算所有 A1 卡牌哈希，保存为 JSON
"""

import base64
import json
import sys
import time
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

# 引入 hash 工具（假设在同目录或修改路径）
sys.path.insert(0, str(Path(__file__).parent))
from test_yolo_hash_match import (
    pil_to_color_pixels,
    calculate_perceptual_hash,
)


def encode_hash_to_base64(hash_arr: np.ndarray) -> str:
    """编码为 base64 字符串"""
    raw = hash_arr.astype(np.uint32).tobytes()
    return base64.b64encode(raw).decode("ascii")


def generate_hash_database(
    cards_dir: Path, output_path: Path
) -> Tuple[Dict[str, str], int, int]:
    """
    生成哈希数据库

    Returns:
        (hash_db, success_count, fail_count)
    """
    print("=" * 70)
    print("生成 A1 卡牌哈希数据库")
    print("=" * 70)
    print(f"卡牌目录: {cards_dir}")
    print(f"输出文件: {output_path}")
    print()

    # 查找所有 A1 卡牌
    card_files = []
    for ext in [".webp", ".png", ".jpg"]:
        card_files.extend(cards_dir.glob(f"A1-*{ext}"))

    # 排序（按编号）
    card_files = sorted(card_files, key=lambda x: int(x.stem.split("-")[1]))

    print(f"找到 {len(card_files)} 张 A1 卡牌")
    print()

    hash_db: Dict[str, str] = {}
    success_count = 0
    fail_count = 0

    # 计时
    start_time = time.perf_counter()

    for card_file in tqdm(card_files, desc="计算哈希", unit="张"):
        card_id = card_file.stem  # 如 "A1-183"

        try:
            # 使用 PIL 读取图片（统一预处理流程）
            pil_img = Image.open(card_file)

            # 计算哈希
            color_pixels = pil_to_color_pixels(pil_img)
            hash_arr = calculate_perceptual_hash(color_pixels)

            # 编码为 base64（用于 JSON 存储）
            hash_str = encode_hash_to_base64(hash_arr)

            # 存储：key=hash, value=card_id
            hash_db[hash_str] = card_id
            success_count += 1

        except Exception as e:
            print(f"❌ {card_id}: {e}")
            fail_count += 1

    elapsed = time.perf_counter() - start_time

    # 保存数据库
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hash_db, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print("数据库生成完成")
    print("=" * 70)
    print(f"   成功: {success_count} 张")
    print(f"   失败: {fail_count} 张")
    print(f"   耗时: {elapsed:.1f} 秒")
    print(f"   平均每张: {elapsed / success_count * 1000:.1f} ms")
    print(f"   保存路径: {output_path}")
    print()

    return hash_db, success_count, fail_count


def verify_database(db_path: Path):
    """验证数据库内容"""
    with open(db_path, "r", encoding="utf-8") as f:
        db = json.load(f)

    print("数据库验证:")
    print(f"   总条目: {len(db)}")
    print(f"   示例条目: {list(db.items())[0] if db else 'N/A'}")
    print()


def main():
    # 配置
    cards_dir = Path("data/raw/cards")
    output_path = Path("data/hash_database_a1.json")

    # 检查目录
    if not cards_dir.exists():
        print(f"❌ 卡牌目录不存在: {cards_dir}")
        print("💡 请先运行: python scripts/download_assets.py --sets A1")
        sys.exit(1)

    # 生成数据库
    generate_hash_database(cards_dir, output_path)

    # 验证
    verify_database(output_path)

    print("✅ 完成！现在可以运行大规模匹配测试:")
    print(f"   uv run python scripts/test_massive_matching.py")


if __name__ == "__main__":
    main()
