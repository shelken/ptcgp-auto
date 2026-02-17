# -*- coding: utf-8 -*-

from pathlib import Path


def test_docs_mentions_exchange_cards_feature():
    """文档应包含交换卡牌能力与管理入口说明。"""
    repo_root = Path(__file__).resolve().parents[4]
    readme_text = (repo_root / "README.md").read_text(encoding="utf-8")
    web_agents_text = (repo_root / "src/ptcgp_auto_v2/web/AGENTS.md").read_text(
        encoding="utf-8"
    )

    assert "exchange_cards" in readme_text
    assert "管理中心 -> 交换记录" in readme_text
    assert "exchange_card.py" in web_agents_text
