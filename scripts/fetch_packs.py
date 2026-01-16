#!/usr/bin/env python3
"""
从 game8.co 抓取 Pokemon TCG Pocket 卡包数据

用法:
    python scripts/fetch_packs.py

数据保存到: data/packs.json
"""

import json
import re
import sys
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("需要安装依赖: pip install requests beautifulsoup4")
    sys.exit(1)


GAME8_URL = "https://game8.co/games/Pokemon-TCG-Pocket/archives/477754"
OUTPUT_FILE = ROOT_DIR / "data" / "packs.json"


def fetch_packs() -> dict:
    """
    从 game8 抓取卡包数据

    Returns:
        {
            "A1": {"name": "Genetic Apex", "boosters": ["Pikachu", "Charizard", "Mewtwo"]},
            ...
        }
    """
    print(f"正在从 {GAME8_URL} 获取数据...")

    response = requests.get(GAME8_URL, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    packs = {}

    # 查找卡包列表
    # game8 的结构可能变化，这里尝试解析
    for row in soup.select("table tr"):
        cells = row.select("td")
        if len(cells) < 2:
            continue

        # 尝试提取卡包信息
        first_cell = cells[0]
        link = first_cell.select_one("a")
        if not link:
            continue

        pack_name = link.get_text(strip=True)

        # 尝试从第二列获取代码
        code_cell = cells[1] if len(cells) > 1 else None
        code = code_cell.get_text(strip=True) if code_cell else None

        # 解析代码 (如 A1, B1a)
        if code and re.match(r"^[AB]\d+[a-z]?$", code):
            packs[code] = {
                "name": pack_name,
                "boosters": [],  # 需要进一步抓取子页面获取
            }

    return packs


def save_packs(packs: dict):
    """保存卡包数据到 JSON 文件"""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(packs, f, indent=2, ensure_ascii=False)

    print(f"已保存到 {OUTPUT_FILE}")
    print(f"共 {len(packs)} 个扩充包")


def main():
    try:
        packs = fetch_packs()
        if packs:
            save_packs(packs)
        else:
            print("未获取到任何卡包数据，可能网页结构已变化")
            print("请手动更新 data/packs.json")
    except Exception as e:
        print(f"抓取失败: {e}")
        print("请手动更新 data/packs.json")
        sys.exit(1)


if __name__ == "__main__":
    main()
