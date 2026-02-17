# -*- coding: utf-8 -*-

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _render_template(source: str) -> str:
    """渲染临时模板内容并返回 HTML。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
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
