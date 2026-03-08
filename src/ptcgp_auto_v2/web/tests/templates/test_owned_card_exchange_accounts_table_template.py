# -*- coding: utf-8 -*-
"""拥有卡牌交换账号表格模板回归测试。"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _build_env() -> Environment:
    """构建模板环境。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
    )


def test_owned_card_exchange_accounts_table_renders_account_identity_and_disabled_reason() -> None:
    """账号列应复用账号管理展示，并为禁用按钮输出原因提示。"""
    template = _build_env().get_template(
        "partials/modals/owned_card_exchange_accounts_table.html"
    )
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_account_id": "账号 ID",
            "col_game_id": "游戏 ID",
            "col_count": "数量",
            "col_exchange_points": "交换点数",
            "col_actions": "操作",
            "msg_copied": "已复制",
        },
        card=SimpleNamespace(id=7),
        accounts=[
            {
                "account_id": 1,
                "game_id": "game-alpha",
                "friend_id": "1234567890123456",
                "nickname": "Alpha",
                "count": 2,
                "exchange_points": 5000,
                "exchange_action": {
                    "enabled": False,
                    "button_text": "交换卡牌",
                    "tooltip": "该账号有进行中的交换请求",
                },
            }
        ],
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total_items=1,
        q="",
        sort_by="account_id",
        sort_order="asc",
    )

    assert "Alpha" in html
    assert "账号 ID: #1" in html
    assert "1234-5678-9012-3456" in html
    assert 'data-action="copy-text"' in html
    assert "游戏 ID: game-alpha" in html
    assert "交换点数" in html
    assert ">5000<" in html
    assert 'data-tooltip="该账号有进行中的交换请求"' in html
    assert "tooltip-text--left" in html
    assert "owned-card-exchange-table-frame" in html
    assert "disabled" in html
    assert 'data-action="show-exchange-form"' not in html


def test_owned_card_exchange_accounts_table_renders_enabled_button() -> None:
    """可交换账号应输出正常的触发表单按钮。"""
    template = _build_env().get_template(
        "partials/modals/owned_card_exchange_accounts_table.html"
    )
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_account_id": "账号 ID",
            "col_game_id": "游戏 ID",
            "col_count": "数量",
            "col_exchange_points": "交换点数",
            "col_actions": "操作",
        },
        card=SimpleNamespace(id=8),
        accounts=[
            {
                "account_id": 2,
                "game_id": "game-bravo",
                "friend_id": None,
                "nickname": "Bravo",
                "count": 1,
                "exchange_points": None,
                "exchange_action": {
                    "enabled": True,
                    "button_text": "交换卡牌",
                    "tooltip": None,
                },
            }
        ],
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total_items=1,
        q="",
        sort_by="count",
        sort_order="desc",
    )

    assert 'data-action="show-exchange-form"' in html
    assert 'data-account-id="2"' in html
    assert ">-<" in html
