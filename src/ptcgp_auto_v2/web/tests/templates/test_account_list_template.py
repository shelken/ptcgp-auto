# -*- coding: utf-8 -*-
"""账号列表模板回归测试。"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def _build_env() -> Environment:
    """构建模板环境。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    return Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
    )


def test_account_list_renders_lazy_target_pack_placeholder_when_no_config() -> None:
    """账号列表无手动配置时应渲染懒加载目标包占位。"""
    template = _build_env().get_template("partials/account_list.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "title_accounts": "账号",
            "col_account": "账号",
            "col_plans": "计划",
            "col_target_pack": "目标卡包",
            "col_actions": "操作",
            "col_account_id": "账号 ID",
            "col_game_id": "游戏 ID",
            "msg_copied": "已复制",
            "btn_edit_plans": "编辑计划",
            "btn_edit_account_title": "编辑账号",
            "btn_pack_config_title": "配置目标卡包",
            "label_loading": "加载中",
        },
        items=[
            {
                "id": 1,
                "nickname": "Alpha",
                "display_name": "Alpha",
                "friend_id": "1234567890123456",
                "game_id": "game-alpha",
                "task_plan_associations": [],
            }
        ],
        pack_configs={},
        auto_pack_map={},
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total=1,
    )

    assert 'id="account-target-pack-1"' in html
    assert "/management/accounts/1/target-pack?lang=zh_CN" in html
    assert 'hx-trigger="load"' in html
    assert "加载中" in html
