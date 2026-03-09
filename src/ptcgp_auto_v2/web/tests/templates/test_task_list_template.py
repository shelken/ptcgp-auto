# -*- coding: utf-8 -*-
"""task_list 模板回归测试。"""

from __future__ import annotations

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


def test_task_list_renders_lazy_target_pack_placeholder_for_open_pack() -> None:
    """open_pack 行无目标包标签时应渲染懒加载占位。"""
    template = _build_env().get_template("partials/task_list.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "col_account": "账号",
            "col_task": "任务",
            "col_status": "状态",
            "col_dispatch_priority": "调度优先级",
            "col_last_completed": "上次完成",
            "col_last_duration": "上次耗时",
            "col_next_run": "下次执行",
            "col_reset_type": "重置类型",
            "col_plan": "计划",
            "task_open_pack": "开包",
            "status_pending": "待执行",
            "reset_daily": "每日",
            "label_loading": "加载中",
            "empty_tasks": "无任务",
            "btn_prev_page": "上一页",
            "btn_next_page": "下一页",
            "label_total_records": "总记录",
        },
        items=[
            {
                "id": 8,
                "account_id": 10,
                "account_name": "Alpha",
                "task_type": "open_pack",
                "status": "pending",
                "reset_type": "daily",
                "last_completed_at": None,
                "last_completed_at_iso": None,
                "last_duration_seconds": None,
                "updated_at": None,
                "error_message": None,
                "next_run_at": None,
                "next_run_at_iso": None,
                "next_run_at_is_past": False,
                "interval_seconds": None,
                "plan_name": None,
                "plan_priority": None,
                "target_pack_label": None,
                "target_pack_auto": False,
            }
        ],
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total=1,
        prev_page_url="/api/tasks?page=0",
        next_page_url="/api/tasks?page=1",
        selected_status=[],
        selected_task_type=[],
        selected_account_id=None,
        selected_sort_by="dispatch_priority",
        selected_sort_order="asc",
        status_options=["pending"],
        task_types=["open_pack"],
        accounts=[],
        table_only=True,
    )

    assert 'id="task-target-pack-8"' in html
    assert "/management/tasks/8/target-pack?lang=zh_CN" in html
    assert 'hx-trigger="load"' in html
    assert "加载中" in html
    assert "#10 Alpha" in html


def test_task_list_renders_remote_account_search_controls() -> None:
    """任务页账号筛选应渲染远程搜索控件而不是全量 select。"""
    template = _build_env().get_template("partials/task_list.html")
    html = template.render(
        current_lang="zh_CN",
        t={
            "title_tasks": "任务",
            "filter_status": "状态",
            "filter_task": "任务",
            "filter_account": "账号",
            "filter_account_search_placeholder": "搜索账号",
            "label_all": "全部",
            "btn_refresh": "刷新",
            "btn_reset_completed": "重置完成",
            "col_account": "账号",
            "col_task": "任务",
            "col_status": "状态",
            "col_dispatch_priority": "调度优先级",
            "col_last_completed": "上次完成",
            "col_last_duration": "上次耗时",
            "col_next_run": "下次执行",
            "col_reset_type": "重置类型",
            "col_plan": "计划",
            "empty_tasks": "无任务",
            "btn_prev_page": "上一页",
            "btn_next_page": "下一页",
            "label_total_records": "总记录",
        },
        items=[],
        page=0,
        page_size=10,
        has_prev=False,
        has_next=False,
        total=0,
        prev_page_url="/api/tasks?page=0",
        next_page_url="/api/tasks?page=1",
        selected_status=[],
        selected_task_type=[],
        selected_account_id=None,
        selected_account_query="",
        selected_sort_by="dispatch_priority",
        selected_sort_order="asc",
        status_options=["pending"],
        task_types=["open_pack"],
        accounts=[],
        table_only=False,
    )

    assert 'name="account_q"' in html
    assert 'name="account_id"' in html
    assert "/api/tasks/account-options?lang=zh_CN" in html
    assert "task-filter-account-options" in html
    assert '<select id="task-filter-account"' not in html
