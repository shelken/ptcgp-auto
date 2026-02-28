# -*- coding: utf-8 -*-
"""metadata 控制台模板结构测试。"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _render_metadata_template() -> str:
    """渲染 metadata_list 模板。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("partials/metadata_list.html")
    return template.render(
        current_lang="zh_CN",
        t={},
        sets=[{"code": "A1", "name": "SetA", "label_dict": {}}],
        packs_by_set={"A1": [{"name": "PackA", "set_code": "A1", "label_dict": {}}]},
        selected_node_type="root",
        selected_node_id="all",
        selected_set_code="",
        selected_pack_name="",
        selected_card_key="",
        selected_pack_cards=[],
        sync_check={"local": {}, "flibustier": {}, "poke52": {}},
        sync_preview={},
        sync_execute_result=None,
        sync_execute_result_json="",
        ui_step=1,
        snapshot_id="",
    )


def test_metadata_console_layout_has_check_preview_execute_sections() -> None:
    """页面应包含检查、预览、执行三大区块。"""
    html = _render_metadata_template()
    assert "metadata-sync-root" in html
    assert 'id="metadata-state-form"' in html
    assert "metadata-hierarchy-tree" in html
    assert "/api/metadata/node/select" in html
    assert "/api/metadata/sync/check" in html
    assert "/api/metadata/sync/preview" in html
    assert "/api/metadata/sync/execute" in html
    assert 'name="source"' not in html
    assert 'name="scope_level"' not in html
    assert 'name="scope_value"' not in html


def test_metadata_console_uses_data_action_for_toggle() -> None:
    """折叠交互应使用 data-action 委托。"""
    html = _render_metadata_template()
    assert 'data-action="toggle-section"' in html
    assert 'name="node_type"' in html
    assert 'name="node_id"' in html
    assert 'name="action"' in html
    assert 'name="selected_node_type"' in html
    assert 'name="selected_node_id"' in html
    assert "onclick=" not in html
