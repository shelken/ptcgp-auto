"""
卡包常量定义

从 data/packs.json 加载数据
可通过 scripts/fetch_packs.py 更新数据
"""

import json
from pathlib import Path

# 数据文件路径
DATA_FILE = Path(__file__).resolve().parent.parent.parent.parent / "data" / "packs.json"


def _load_packs() -> dict:
    """从 JSON 文件加载卡包数据"""
    if not DATA_FILE.exists():
        return {}

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# 加载卡包数据
PACKS = _load_packs()


def get_pack_choices() -> list[tuple[str, str]]:
    """
    获取扩充包选择列表

    Returns:
        [(code, display_name), ...]
    """
    choices = []
    for code, info in PACKS.items():
        display = f"{code}: {info['name']}"
        choices.append((code, display))
    return choices


def get_booster_choices(pack_code: str) -> list[tuple[str, str]]:
    """
    获取指定扩充包的子包选择列表

    Args:
        pack_code: 扩充包代码

    Returns:
        [(booster_name, display_name), ...]
        如果没有子包，返回扩充包名称作为唯一选项
    """
    pack = PACKS.get(pack_code)
    if not pack:
        return []

    boosters = pack.get("boosters", [])
    if not boosters:
        # 无子包时，使用扩充包名称
        name = pack["name"].replace(" ", "_")
        return [(name, pack["name"])]

    return [(b.replace(" ", "_"), b) for b in boosters]


def get_template_path(pack_code: str, booster_name: str) -> str:
    """
    获取模板保存路径

    Args:
        pack_code: 扩充包代码 (如 A1, B1a)
        booster_name: 子包名称 (如 Pikachu, Mega_Blaziken_ex)

    Returns:
        相对于 templates 目录的路径 (如 packs/A1/Pikachu.png)
    """
    return f"packs/{pack_code}/{booster_name}.png"
