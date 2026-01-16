#!/usr/bin/env python3
"""
从 pokemon-tcg-pocket-database 抓取卡包数据

数据来源: https://github.com/flibustier/pokemon-tcg-pocket-database

用法:
    python scripts/fetch_packs.py

数据保存到: data/packs.json
"""

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("需要安装依赖: pip install requests")
    sys.exit(1)


ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_URL = "https://raw.githubusercontent.com/flibustier/pokemon-tcg-pocket-database/main/dist/sets.json"
OUTPUT_FILE = ROOT_DIR / "data" / "packs.json"


def fetch_packs() -> dict:
    """
    从 GitHub 获取卡包数据并转换格式

    Returns:
        {
            "A1": {"name": "Genetic Apex", "boosters": ["Charizard", "Mewtwo", "Pikachu"]},
            ...
        }
    """
    print(f"正在从 {SOURCE_URL} 获取数据...")

    response = requests.get(SOURCE_URL, timeout=30)
    response.raise_for_status()

    source_data = response.json()

    packs = {}

    # 遍历所有系列 (A, B, ...)
    for series_key, series_sets in source_data.items():
        for set_info in series_sets:
            code = set_info.get("code", "")

            # 跳过 PROMO 系列
            if code.startswith("PROMO"):
                continue

            # 获取英文名称
            name_dict = set_info.get("name", {})
            name = name_dict.get("en", "") if isinstance(name_dict, dict) else str(name_dict)

            # 获取子包列表
            boosters = set_info.get("packs", [])

            if code and name:
                packs[code] = {
                    "name": name,
                    "boosters": boosters,
                }

    return packs


def save_packs(packs: dict):
    """保存卡包数据到 JSON 文件"""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 按代码排序
    sorted_packs = dict(sorted(packs.items()))

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted_packs, f, indent=2, ensure_ascii=False)

    print(f"已保存到 {OUTPUT_FILE}")
    print(f"共 {len(packs)} 个扩充包")


def main():
    try:
        packs = fetch_packs()
        if packs:
            save_packs(packs)
            # 显示摘要
            print("\n=== 卡包列表 ===")
            for code, info in sorted(packs.items()):
                boosters = ", ".join(info["boosters"]) if info["boosters"] else "-"
                print(f"  {code}: {info['name']} [{boosters}]")
        else:
            print("未获取到任何卡包数据")
            sys.exit(1)
    except Exception as e:
        print(f"抓取失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
