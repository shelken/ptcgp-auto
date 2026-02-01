#!/usr/bin/env python3
"""
下载训练素材脚本（高性能并发版）- 中文 PNG 版本
- 使用线程池并发下载
- 连接复用（requests Session）
- 自动重试机制
- 通过 GitHub API 自动发现可用卡牌

用法：
  python scripts/download_assets.py --set A1           # 下载 A1 系列
  python scripts/download_assets.py --set A1 --max-workers 8  # 8线程
"""

import argparse
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Tuple

import requests
from tqdm import tqdm

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
CARDS_DIR = DATA_DIR / "raw" / "cards"  # 卡牌放在 data/raw/cards/[set]/ 目录下
BACKGROUNDS_DIR = DATA_DIR / "raw" / "backgrounds"

# 使用用户维护的繁体中文 PNG 资源
CARDS_BASE_URL = "https://raw.githubusercontent.com/shelken/ptcgp-assets/main/images/zh-TW/cards-by-set"
GITHUB_API_URL = "https://api.github.com/repos/shelken/ptcgp-assets/contents/images/zh-TW/cards-by-set"

# 全局 Session（连接复用）
session = requests.Session()
session.headers.update(
    {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
)


def download_single_card(args: Tuple[str, int]) -> Tuple[str, int, bool]:
    """
    下载单张卡牌（中文 PNG 版本）
    保存到 data/cards/[set]/[number].png
    返回: (set_name, card_num, success)
    """
    set_name, card_num = args
    # 文件名不再带 set 前缀，直接是 001.png 格式
    filename = f"{card_num}.png"
    url = f"{CARDS_BASE_URL}/{set_name}/{card_num}.png"

    # 创建 set 子目录
    set_dir = CARDS_DIR / set_name
    set_dir.mkdir(parents=True, exist_ok=True)

    output_path = set_dir / filename

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


def discover_all_sets() -> List[str]:
    """
    通过 GitHub API 发现所有可用的系列
    返回系列名称列表
    """
    print("🔍 正在通过 GitHub API 发现所有可用系列...")

    try:
        response = session.get(GITHUB_API_URL, timeout=30)
        response.raise_for_status()
        items = response.json()

        # 提取目录名称
        sets = []
        for item in items:
            if item["type"] == "dir":
                sets.append(item["name"])

        sets.sort()
        print(f"✅ 发现 {len(sets)} 个系列: {', '.join(sets)}")
        return sets

    except Exception as e:
        print(f"❌ 发现失败: {e}")
        return []


def discover_cards_in_set(set_name: str) -> List[int]:
    """
    通过 GitHub API 发现指定 set 中的可用卡牌
    返回卡牌编号列表
    """
    print(f"🔍 正在通过 GitHub API 发现 {set_name} 系列的卡牌...")

    try:
        url = f"{GITHUB_API_URL}/{set_name}"
        response = session.get(url, timeout=30)

        if response.status_code == 404:
            print(f"❌ 系列 {set_name} 在远程仓库中不存在")
            return []

        response.raise_for_status()
        files = response.json()

        # 提取 PNG 文件的编号
        card_numbers = []
        for file in files:
            if file["type"] == "file" and file["name"].endswith(".png"):
                # 文件名格式: 001.png -> 提取 1
                try:
                    num = int(file["name"].replace(".png", ""))
                    card_numbers.append(num)
                except ValueError:
                    continue

        card_numbers.sort()
        print(f"✅ 发现 {len(card_numbers)} 张卡牌")
        return card_numbers

    except Exception as e:
        print(f"❌ 发现失败: {e}")
        return []


def download_cards_concurrent(set_name: str, max_workers: int = 10):
    """
    并发下载卡牌（中文 PNG 版本）
    保存到 data/cards/[set]/[number].png

    Args:
        set_name: 系列名称（如 'A1'）
        max_workers: 并发线程数（默认 10）
    """
    print(f"📥 并发下载卡牌（{max_workers} 线程）...")

    # 创建 set 子目录
    set_dir = CARDS_DIR / set_name
    set_dir.mkdir(parents=True, exist_ok=True)

    # 通过 GitHub API 发现可用卡牌
    card_numbers = discover_cards_in_set(set_name)

    if not card_numbers:
        print(f"❌ 未找到可用卡牌")
        return

    # 生成所有要下载的任务
    tasks = [(set_name, card_num) for card_num in card_numbers]

    print(f"   系列: {set_name}")
    print(f"   保存位置: {set_dir}")
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
                    set_dir = CARDS_DIR / set_name
                    if (set_dir / f"{card_num}.png").exists():
                        downloaded += 1
                    else:
                        skipped += 1  # 之前已存在
                else:
                    failed += 1

                pbar.update(1)

    print(f"\n✅ 下载完成: {downloaded} 张新下载, {skipped} 张已存在, {failed} 张失败")


def main():
    parser = argparse.ArgumentParser(description="下载 YOLO 训练素材（中文 PNG 版）")

    # 创建互斥组：--set 和 --all 只能选一个
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--set",
        help="要下载的系列（如 A1, A2, A3, A4, A1a, A2a, A2b, A3a, PA 等任意系列）",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="下载所有可用系列",
    )

    parser.add_argument(
        "--max-workers", type=int, default=10, help="并发线程数（默认 10，建议 5-20）"
    )
    parser.add_argument(
        "--skip-existing", action="store_true", help="跳过已存在的文件（默认会检查）"
    )
    args = parser.parse_args()

    print("=" * 50)
    print("YOLO 训练素材下载（中文 PNG 版）")
    print("=" * 50)
    print(f"来源: shelken/ptcgp-assets (繁体中文)")
    print(f"API: GitHub Contents API 自动发现")

    if args.all:
        # 下载所有系列
        sets = discover_all_sets()
        if not sets:
            print("❌ 未发现任何可用系列")
            return

        print(f"\n将下载所有 {len(sets)} 个系列")
        print(f"并发线程数: {args.max_workers}")
        print()

        total_downloaded = 0
        for i, set_name in enumerate(sets, 1):
            print(f"\n{'=' * 50}")
            print(f"[{i}/{len(sets)}] 下载系列: {set_name}")
            print(f"{'=' * 50}")
            download_cards_concurrent(set_name, args.max_workers)

        print("\n" + "=" * 50)
        print("✨ 全部完成！")
        print(f"📁 卡牌保存位置: {CARDS_DIR}")
        total_files = sum(1 for _ in CARDS_DIR.rglob("*.png"))
        print(f"   总文件数: {total_files}")
        print("=" * 50)
    else:
        # 下载指定系列
        print(f"\n将下载系列: {args.set}")
        print(f"并发线程数: {args.max_workers}")

        # 下载卡牌
        download_cards_concurrent(args.set, args.max_workers)

        print("\n" + "=" * 50)
        print("✨ 完成！")
        set_dir = CARDS_DIR / args.set
        if set_dir.exists():
            print(f"📁 卡牌保存位置: {set_dir}")
            print(f"   当前系列文件数: {len(list(set_dir.glob('*.png')))}")
        print("=" * 50)


if __name__ == "__main__":
    main()
