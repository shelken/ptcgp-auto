# -*- coding: utf-8 -*-

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _render_template(source: str) -> str:
    """渲染临时模板内容并返回 HTML。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    env.filters["datetime"] = lambda value: str(value)
    env.filters["rarity_display"] = lambda value, _lang=None: value
    template = env.from_string(source)
    return template.render()


def test_toolbar_layout_supports_left_right_order_and_wrap_tokens():
    """工具栏应支持左右分区、顺序控制和自动换行 token。"""
    html = _render_template(
        """
        {% from "partials/macros/data_table.html" import data_table_toolbar_layout %}
        {% set layout = {
            'left_items': [
                {'key': 'search', 'order': 20, 'label': 'Search', 'span': 3, 'min_width': '14rem'},
                {'key': 'status', 'order': 10, 'label': 'Status', 'span': 2, 'min_width': '10rem'}
            ],
            'right_items': [
                {'key': 'refresh', 'order': 30, 'label': '', 'span': 1, 'min_width': '8rem'}
            ]
        } %}
        {% call(item, zone) data_table_toolbar_layout(layout, 'normal') %}
            <span data-key="{{ item.key }}" data-zone="{{ zone }}">{{ item.key }}</span>
        {% endcall %}
        """
    )

    assert "table-toolbar-layout" in html
    assert "table-toolbar-zone--left" in html
    assert "table-toolbar-zone--right" in html
    assert "--table-item-span" in html
    assert "--table-item-min-width" in html

    status_index = html.find('data-key="status"')
    search_index = html.find('data-key="search"')
    refresh_index = html.find('data-key="refresh"')
    assert status_index != -1
    assert search_index != -1
    assert refresh_index != -1
    assert status_index < search_index


def test_notification_task_status_notify_on_empty_should_not_fallback_defaults():
    """task_status 的 notify_on 为空数组时，回显不应退回默认勾选。"""
    html = _render_template(
        """
        {% set extra = {'notify_on': []} %}
        {% set task_status_options = ['failed', 'blocked', 'timeout', 'success'] %}
        {% set notify_on_values = extra.notify_on if extra.notify_on is defined else ['failed', 'blocked', 'timeout'] %}
        {% for status in task_status_options %}
        <input type="checkbox" name="notify_on" value="{{ status }}" {% if status in notify_on_values %}checked{% endif %}>
        {% endfor %}
        """
    )

    assert 'name="notify_on" value="failed" checked' not in html
    assert 'name="notify_on" value="blocked" checked' not in html
    assert 'name="notify_on" value="timeout" checked' not in html


def test_notification_task_status_notify_on_undefined_should_use_defaults():
    """task_status 的 notify_on 未配置时，回显应使用默认失败/阻塞/超时。"""
    html = _render_template(
        """
        {% set extra = {} %}
        {% set task_status_options = ['failed', 'blocked', 'timeout', 'success'] %}
        {% set notify_on_values = extra.notify_on if extra.notify_on is defined else ['failed', 'blocked', 'timeout'] %}
        {% for status in task_status_options %}
        <input type="checkbox" name="notify_on" value="{{ status }}" {% if status in notify_on_values %}checked{% endif %}>
        {% endfor %}
        """
    )

    assert 'name="notify_on" value="failed" checked' in html
    assert 'name="notify_on" value="blocked" checked' in html
    assert 'name="notify_on" value="timeout" checked' in html
