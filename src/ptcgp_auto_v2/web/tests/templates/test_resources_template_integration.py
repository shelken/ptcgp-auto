# -*- coding: utf-8 -*-
"""资源页模板集成回归测试。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ptcgp_auto_v2.web.utils.view_helpers import format_datetime


def _build_env() -> Environment:
    """构建模板环境。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml"), default=True),
    )
    env.filters["datetime"] = format_datetime
    return env


def test_index_template_contains_resources_sidebar_entry() -> None:
    """管理页首页模板应包含 resources 侧栏入口。"""
    template = _build_env().get_template("index.html")
    html = template.render(
        current_lang="zh_CN",
        unread_count=0,
        t={
            "menu_resources": "资源",
            "notification_center": "通知中心",
            "btn_mark_all_read": "全部已读",
            "label_close": "关闭",
            "relative_just_now": "刚刚",
            "relative_soon": "马上",
            "relative_minutes": "分钟",
            "relative_hours": "小时",
            "relative_days": "天",
            "relative_ago": "前",
            "relative_in": "后",
            "themes": {
                "brutalist": "野兽派",
                "organic": "有机自然",
                "luxury": "奢华精致",
                "editorial": "杂志排版",
                "pastel": "柔和粉彩",
                "retro": "复古未来",
                "art_deco": "艺术装饰",
                "playful": "俏皮可爱",
            },
        },
        rarities=[],
        card_types=[],
        card_sets=[],
        packs=[],
        elements=[],
    )

    assert 'data-hash="resources"' in html
    assert "/management/resources?lang=zh_CN" in html
    assert "资源" in html


def test_index_template_owned_cards_account_search_uses_text_input() -> None:
    """拥有卡牌账号搜索应允许输入四字段文本，而不是限制数字键盘。"""
    template = _build_env().get_template("index.html")
    html = template.render(
        current_lang="zh_CN",
        unread_count=0,
        t={
            "menu_resources": "资源",
            "notification_center": "通知中心",
            "btn_mark_all_read": "全部已读",
            "label_close": "关闭",
            "relative_just_now": "刚刚",
            "relative_soon": "马上",
            "relative_minutes": "分钟",
            "relative_hours": "小时",
            "relative_days": "天",
            "relative_ago": "前",
            "relative_in": "后",
            "filter_account_id": "账号搜索",
            "filter_account_id_placeholder": "输入账号 ID / 朋友ID / 昵称 / 游戏ID",
            "themes": {
                "brutalist": "野兽派",
                "organic": "有机自然",
                "luxury": "奢华精致",
                "editorial": "杂志排版",
                "pastel": "柔和粉彩",
                "retro": "复古未来",
                "art_deco": "艺术装饰",
                "playful": "俏皮可爱",
            },
        },
        rarities=[],
        card_types=[],
        card_sets=[],
        packs=[],
        elements=[],
    )

    owned_account_input = html.split('id="owned-account-id"', 1)[1].split(">", 1)[0]
    assert 'type="text"' in owned_account_input
    assert 'inputmode="numeric"' not in owned_account_input
    assert "输入账号 ID / 朋友ID / 昵称 / 游戏ID" in owned_account_input


def test_index_template_resources_sidebar_entry_has_cache_restore_attrs() -> None:
    """资源侧栏入口应声明缓存恢复所需属性。"""
    template = _build_env().get_template("index.html")
    html = template.render(
        current_lang="zh_CN",
        unread_count=0,
        t={
            "menu_resources": "资源",
            "notification_center": "通知中心",
            "btn_mark_all_read": "全部已读",
            "label_close": "关闭",
            "relative_just_now": "刚刚",
            "relative_soon": "马上",
            "relative_minutes": "分钟",
            "relative_hours": "小时",
            "relative_days": "天",
            "relative_ago": "前",
            "relative_in": "后",
            "themes": {
                "brutalist": "野兽派",
                "organic": "有机自然",
                "luxury": "奢华精致",
                "editorial": "杂志排版",
                "pastel": "柔和粉彩",
                "retro": "复古未来",
                "art_deco": "艺术装饰",
                "playful": "俏皮可爱",
            },
        },
        rarities=[],
        card_types=[],
        card_sets=[],
        packs=[],
        elements=[],
    )

    assert 'data-base-url="/management/resources?lang=zh_CN"' in html
    assert 'data-filter-cache-key="ptcgp_filter:resources"' in html
    assert 'data-filter-param-keys="view,q,sort_by,sort_order,page,page_size"' in html


def test_account_list_template_removes_legacy_resources_column() -> None:
    """账号列表模板不应再渲染旧 Resources 列。"""
    template = _build_env().get_template("partials/account_list.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "title_accounts": "账号",
            "col_account": "账号",
            "col_resources": "Resources",
            "col_plans": "计划",
            "col_target_pack": "目标卡包",
            "col_actions": "操作",
        },
        items=[],
        pack_configs={},
        auto_pack_map={},
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total=0,
    )

    assert "Resources" not in html
    assert "account-resources-cell" not in html


def test_management_hash_whitelist_contains_resources() -> None:
    """管理页 hash 白名单应包含 resources。"""
    constants_path = (
        Path(__file__).resolve().parents[2]
        / "static"
        / "js"
        / "modules"
        / "constants.js"
    )
    content = constants_path.read_text(encoding="utf-8")

    assert "'resources'" in content or '"resources"' in content


def test_resource_list_template_contains_state_form_and_view_switch() -> None:
    """资源列表模板应包含状态表单、缓存键与视图切换。"""
    template = _build_env().get_template("partials/resource_list.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "title_resources": "资源总览",
            "label_search": "搜索",
            "btn_refresh": "刷新",
            "tab_resource_stats": "资源统计",
            "tab_resource_pack_points": "包点数",
        },
        view="stats",
        items=[],
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total=0,
        series_list=[],
    )

    assert 'data-auto-refresh="/management/resources?lang=zh_CN"' in html
    assert 'id="resource-state-form"' in html
    assert 'data-filter-cache-key="ptcgp_filter:resources"' in html
    assert 'id="resource-filter-form"' in html
    filter_form_segment = html.split('id="resource-filter-form"', 1)[1].split(">", 1)[0]
    assert 'data-filter-cache-key="ptcgp_filter:resources"' in filter_form_segment
    assert 'name="view" value="stats"' in html
    assert "/management/resources?lang=zh_CN&amp;view=stats" in html
    assert "/management/resources?lang=zh_CN&amp;view=pack-points" in html
    assert "onclick=" not in html


def test_resource_stats_table_uses_relative_time_markup() -> None:
    """资源统计时间列应使用相对时间结构。"""
    template = _build_env().get_template("partials/resource_stats_table.html")
    updated_at = datetime(2026, 3, 7, 12, 34, 56)
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_exchange_points": "交换点数",
            "col_pack_hourglass": "开包沙漏",
            "col_updated_at": "更新时间",
            "col_account_id": "账号 ID",
            "col_friend_id": "朋友id",
        },
        items=[
            {
                "account_id": 1,
                "nickname": "Alpha",
                "friend_id": "1234567890123456",
                "exchange_points": 10,
                "pack_hourglass_count": 20,
                "updated_at": updated_at,
            }
        ],
        q="",
        sort_by="updated_at",
        sort_order="desc",
        page=0,
        page_size=10,
    )

    assert "relative-time" in html
    assert 'data-iso="2026-03-07T12:34:56"' in html
    assert 'data-tooltip="更新时间：2026-03-07 12:34:56"' in html
    assert "创建时间" not in html
    assert "&lt;span" not in html


def test_resource_stats_table_defaults_value_and_time_sorts_to_desc() -> None:
    """资源统计页的数值列和时间列首次点击应默认切到倒序。"""
    template = _build_env().get_template("partials/resource_stats_table.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_exchange_points": "交换点数",
            "col_pack_hourglass": "开包沙漏",
            "col_updated_at": "更新时间",
            "col_account_id": "账号 ID",
            "col_friend_id": "朋友id",
        },
        items=[],
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )

    assert (
        "/management/resources?lang=zh_CN&amp;view=stats&amp;page=0&amp;page_size=10&amp;q=&amp;sort_by=exchange_points&amp;sort_order=desc"
        in html
    )
    assert (
        "/management/resources?lang=zh_CN&amp;view=stats&amp;page=0&amp;page_size=10&amp;q=&amp;sort_by=pack_hourglass_count&amp;sort_order=desc"
        in html
    )
    assert (
        "/management/resources?lang=zh_CN&amp;view=stats&amp;page=0&amp;page_size=10&amp;q=&amp;sort_by=updated_at&amp;sort_order=desc"
        in html
    )


def test_resource_pack_points_table_renders_series_values_cells() -> None:
    """包点数表应输出系列数值单元格，而不是只剩账号列。"""
    template = _build_env().get_template("partials/resource_pack_points_table.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_account_id": "账号 ID",
            "col_friend_id": "朋友id",
        },
        items=[
            {
                "account_id": 1,
                "nickname": "Alpha",
                "friend_id": "1234567890123456",
                "series_points": {"A1": 120, "A2": 45},
            }
        ],
        series_list=["A1", "A2", "A3"],
        q="",
        sort_by="series:A1",
        sort_order="desc",
        page=0,
        page_size=10,
    )

    assert ">120<" in html
    assert ">45<" in html
    assert ">-<" in html


def test_resource_pack_points_table_defaults_first_series_click_to_desc() -> None:
    """包点数表未激活列第一次点击应默认切到倒序。"""
    template = _build_env().get_template("partials/resource_pack_points_table.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_account_id": "账号 ID",
            "col_friend_id": "朋友id",
        },
        items=[],
        series_list=["A1", "A2"],
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )

    assert (
        "/management/resources?lang=zh_CN&amp;view=pack-points&amp;page=0&amp;page_size=10&amp;q=&amp;sort_by=series%3AA1&amp;sort_order=desc"
        in html
    )
