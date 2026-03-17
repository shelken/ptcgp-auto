#!/usr/bin/env python3
"""
生成卡牌哈希数据库
遍历 data/raw/cards/ 目录下的所有 set 子目录，为每个 set 生成哈希数据库
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

# 引入 hash 工具
sys.path.insert(0, str(Path(__file__).parent))
from test_yolo_hash_match import (
    pil_to_color_pixels,
    calculate_perceptual_hash,
)

BASE_DIR = Path(__file__).parent.parent
CARDS_DIR = BASE_DIR / "data" / "raw" / "cards"


def encode_hash_to_base64(hash_arr: np.ndarray) -> str:
    """编码为 base64 字符串"""
    raw = hash_arr.astype(np.uint32).tobytes()
    return base64.b64encode(raw).decode("ascii")


def generate_hash_database(
    set_dir: Path, output_path: Path
) -> Tuple[Dict[str, str], int, int]:
    """
    为单个 set 生成哈希数据库

    Args:
        set_dir: set 目录路径 (如 data/raw/cards/A1/)
        output_path: 输出文件路径 (如 data/raw/cards/A1/hash_database.json)

    Returns:
        (hash_db, success_count, fail_count)
    """
    set_name = set_dir.name

    print("=" * 70)
    print(f"生成 {set_name} 卡牌哈希数据库")
    print("=" * 70)
    print(f"卡牌目录: {set_dir}")
    print(f"输出文件: {output_path}")
    print()

    # 查找该 set 下的所有卡牌
    card_files = []
    for ext in [".webp", ".png", ".jpg"]:
        card_files.extend(set_dir.glob(f"*{ext}"))

    # 排序（按编号）
    card_files = sorted(card_files, key=lambda x: int(x.stem))

    print(f"找到 {len(card_files)} 张 {set_name} 卡牌")
    print()

    hash_db: Dict[str, str] = {}
    success_count = 0
    fail_count = 0

    # 计时
    start_time = time.perf_counter()

    for card_file in tqdm(card_files, desc="计算哈希", unit="张"):
        # 卡牌 ID 为文件名（不带扩展名），如 "001"
        card_id = card_file.stem

        try:
            # 使用 PIL 读取图片
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

    # 保存数据库到 set 目录
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(hash_db, f, ensure_ascii=False, indent=2)

    print()
    print("=" * 70)
    print(f"{set_name} 数据库生成完成")
    print("=" * 70)
    print(f"   成功: {success_count} 张")
    print(f"   失败: {fail_count} 张")
    print(f"   耗时: {elapsed:.1f} 秒")
    if success_count > 0:
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
    if db:
        sample_key = list(db.keys())[0]
        sample_value = db[sample_key]
        print(f"   示例条目: {sample_value}")
    print()


def discover_sets(cards_dir: Path) -> List[str]:
    """发现所有可用的 set 目录"""
    if not cards_dir.exists():
        return []

    sets = []
    for item in cards_dir.iterdir():
        if item.is_dir() and any(item.glob("*.png")):
            sets.append(item.name)

    return sorted(sets)


def generate_all_databases(specific_set: Optional[str] = None):
    """
    生成所有或指定 set 的数据库

    Args:
        specific_set: 指定 set 名称，为 None 则处理所有 set
    """
    if not CARDS_DIR.exists():
        print(f"❌ 卡牌目录不存在: {CARDS_DIR}")
        print("💡 请先运行: python scripts/download_assets.py --set <set_name>")
        sys.exit(1)

    if specific_set:
        # 处理指定 set
        set_dir = CARDS_DIR / specific_set
        if not set_dir.exists():
            print(f"❌ Set 目录不存在: {set_dir}")
            sys.exit(1)

        output_path = set_dir / "hash_database.json"
        generate_hash_database(set_dir, output_path)
        verify_database(output_path)
    else:
        # 处理所有 set
        sets = discover_sets(CARDS_DIR)

        if not sets:
            print(f"❌ 在 {CARDS_DIR} 下未发现任何 set 目录")
            sys.exit(1)

        print(f"发现 {len(sets)} 个 set: {', '.join(sets)}")
        print()

        for set_name in sets:
            set_dir = CARDS_DIR / set_name
            output_path = set_dir / "hash_database.json"
            generate_hash_database(set_dir, output_path)
            verify_database(output_path)
            print()


def main():
    parser = argparse.ArgumentParser(description="生成卡牌哈希数据库")
    parser.add_argument(
        "--set",
        help="指定要处理的 set（如 A1, A2 等），不指定则处理所有 set",
    )
    args = parser.parse_args()

    generate_all_databases(args.set)

    print("✅ 完成！现在可以运行大规模匹配测试:")
    print("   uv run python scripts/test_massive_matching.py --set <set_name>")


if __name__ == "__main__":
    main()
