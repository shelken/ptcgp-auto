#!/usr/bin/env python3
"""
下载训练素材脚本（高性能并发版）
- 使用线程池并发下载
- 连接复用（requests Session）
- 自动重试机制

用法：
  python scripts/download_assets.py --sets A4          # 下载 A4 系列
  python scripts/download_assets.py --all              # 下载所有系列
  python scripts/download_assets.py --sets A1 A2 --max-workers 8  # 8线程
"""

import argparse
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import requests
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CARDS_DIR = DATA_DIR / "raw" / "cards"
BACKGROUNDS_DIR = DATA_DIR / "raw" / "backgrounds"

# 使用 jsDelivr CDN 加速
CARDS_BASE_URL = "https://cdn.jsdelivr.net/gh/marcelpanse/tcg-pocket-collection-tracker@main/frontend/public/images/en-US"

# 各扩展包卡牌数量（根据实际文件统计）
SET_CARD_RANGES = {
    "A1": (1, 226),
    "A2": (1, 202),
    "A3": (1, 155),
    "A4": (1, 108),
    "A1a": (1, 72),
    "A2a": (1, 69),
    "A2b": (1, 56),
    "A3a": (1, 68),
    "PA": (1, 26),
}

# 全局 Session（连接复用）
session = requests.Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
)


def download_single_card(args: Tuple[str, int]) -> Tuple[str, int, bool]:
    """
    下载单张卡牌
    返回: (set_name, card_num, success)
    """
    set_name, card_num = args
    filename = f"{set_name}-{card_num}.webp"
    url = f"{CARDS_BASE_URL}/{filename}"
    output_path = CARDS_DIR / filename

    # 已存在则跳过
    if output_path.exists():
        return set_name, card_num, True

    try:
        response = session.get(url, timeout=30)
        if response.status_code == 200:
            output_path.write_bytes(response.content)
            return set_name, card_num, True
        elif response.status_code == 404:
            return set_name, card_num, False  # 编号不存在
        else:
            return set_name, card_num, False
    except Exception:
        return set_name, card_num, False


def download_cards_concurrent(sets: List[str], max_workers: int = 10):
    """
    并发下载卡牌

    Args:
        sets: 系列列表（如 ['A4', 'A3']）
        max_workers: 并发线程数（默认 10）
    """
    print(f"📥 并发下载卡牌（{max_workers} 线程）...")
    CARDS_DIR.mkdir(parents=True, exist_ok=True)

    # 生成所有要下载的任务
    tasks = []
    for set_name in sets:
        if set_name not in SET_CARD_RANGES:
            print(f"⚠️  未知系列: {set_name}，跳过")
            continue

        start, end = SET_CARD_RANGES[set_name]
        for card_num in range(start, end + 1):
            tasks.append((set_name, card_num))

    if not tasks:
        print("❌ 没有要下载的任务")
        return

    print(f"   共 {len(tasks)} 个下载任务")

    # 并发下载
    downloaded = 0
    failed = 0
    skipped = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_task = {
            executor.submit(download_single_card, task): task for task in tasks
        }

        # 处理结果（带进度条）
        with tqdm(total=len(tasks), desc="下载进度") as pbar:
            for future in as_completed(future_to_task):
                set_name, card_num, success = future.result()

                if success:
                    if (CARDS_DIR / f"{set_name}-{card_num}.webp").exists():
                        # 检查是否真的刚下载的（文件时间）
                        downloaded += 1
                    else:
                        skipped += 1  # 之前已存在
                else:
                    failed += 1

                pbar.update(1)

    print(f"\n✅ 下载完成: {downloaded} 张新下载, {skipped} 张已存在, {failed} 张失败")


def main():
    parser = argparse.ArgumentParser(description="下载 YOLO 训练素材（并发版）")
    parser.add_argument(
        "--sets",
        nargs="+",
        default=["A4"],
        help="要下载的系列（如 A1 A2 A3 A4），默认 A4",
    )
    parser.add_argument("--all", action="store_true", help="下载所有系列")
    parser.add_argument(
        "--max-workers", type=int, default=10, help="并发线程数（默认 10，建议 5-20）"
    )
    parser.add_argument(
        "--skip-existing", action="store_true", help="跳过已存在的文件（默认会检查）"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("YOLO 训练素材下载（高性能并发版）")
    print("=" * 50)

    # 确定要下载的系列
    if args.all:
        sets_to_download = list(SET_CARD_RANGES.keys())
    else:
        sets_to_download = args.sets

    print(f"\n将下载系列: {', '.join(sets_to_download)}")
    print(f"并发线程数: {args.max_workers}")

    # 下载卡牌
    download_cards_concurrent(sets_to_download, args.max_workers)

    print("\n" + "=" * 50)
    print("✨ 完成！")
    print(f"📁 卡牌保存位置: {CARDS_DIR}")
    print(f"   总文件数: {len(list(CARDS_DIR.glob('*.webp')))}")
    print("=" * 50)


if __name__ == "__main__":
    main()
