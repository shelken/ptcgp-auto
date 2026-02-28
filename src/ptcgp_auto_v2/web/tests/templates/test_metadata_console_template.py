# -*- coding: utf-8 -*-
"""metadata 控制台模板结构测试。"""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def _render_metadata_template(
    *,
    selected_node_type: str = "root",
    selected_node_id: str = "all",
    selected_set_code: str = "",
    selected_pack_name: str = "",
) -> str:
    """渲染 metadata_list 模板。"""
    templates_dir = Path(__file__).resolve().parents[2] / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    template = env.get_template("partials/metadata_list.html")
    available_actions = [
        "update_new_series",
        "update_data_supplement",
        "update_data_force",
        "update_chinese_supplement",
        "update_chinese_force",
    ]
    available_action_cards = [
        {
            "title_key": "metadata_action_update_new_series",
            "title_fallback": "更新新系列",
            "buttons": [
                {
                    "action": "update_new_series",
                    "label_key": "metadata_action_update_new_series",
                    "label_fallback": "更新新系列",
                }
            ],
        },
        {
            "title_key": "metadata_action_update_data",
            "title_fallback": "更新数据",
            "buttons": [
                {
                    "action": "update_data_supplement",
                    "label_key": "metadata_mode_supplement",
                    "label_fallback": "补充",
                },
                {
                    "action": "update_data_force",
                    "label_key": "metadata_mode_force",
                    "label_fallback": "覆盖",
                },
            ],
        },
        {
            "title_key": "metadata_action_update_chinese",
            "title_fallback": "更新中文",
            "buttons": [
                {
                    "action": "update_chinese_supplement",
                    "label_key": "metadata_mode_supplement",
                    "label_fallback": "补充",
                },
                {
                    "action": "update_chinese_force",
                    "label_key": "metadata_mode_force",
                    "label_fallback": "覆盖",
                },
            ],
        },
    ]
    if selected_node_type in {"set", "pack", "card"}:
        available_actions = [
            "update_data_supplement",
            "update_data_force",
            "update_chinese_supplement",
            "update_chinese_force",
        ]
        available_action_cards = available_action_cards[1:]
    return template.render(
        current_lang="zh_CN",
        t={},
        sets=[{"code": "A1", "name": "SetA", "label_dict": {}}],
        packs_by_set={"A1": [{"name": "PackA", "set_code": "A1", "label_dict": {}}]},
        selected_node_type=selected_node_type,
        selected_node_id=selected_node_id,
        selected_set_code=selected_set_code,
        selected_pack_name=selected_pack_name,
        selected_card_key="",
        selected_pack_cards=[],
        available_actions=available_actions,
        current_action=available_actions[0],
        available_action_cards=available_action_cards,
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
    assert "/api/metadata/sync/execute" not in html
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


def test_metadata_console_step1_removes_legacy_buttons() -> None:
    """Step1 不应再显示旧预览/执行文案按钮。"""
    html = _render_metadata_template()
    assert "下一步：查看预览结果" not in html
    assert "直接生成预览" not in html
    assert "强制刷新并生成预览" not in html
    assert "执行（需先预览）" not in html


def test_metadata_console_root_actions_follow_node_rules() -> None:
    """根节点应展示三类动作：新系列/数据/中文。"""
    html = _render_metadata_template(selected_node_type="root", selected_node_id="all")
    assert 'value="update_new_series"' in html
    assert 'value="update_data_supplement"' in html
    assert 'value="update_data_force"' in html
    assert 'value="update_chinese_supplement"' in html
    assert 'value="update_chinese_force"' in html


def test_metadata_console_card_actions_hide_new_series() -> None:
    """卡牌节点不应展示“更新新系列”动作。"""
    html = _render_metadata_template(
        selected_node_type="card",
        selected_node_id="A1-001",
        selected_set_code="A1",
        selected_pack_name="PackA",
    )
    assert 'value="update_new_series"' not in html
    assert 'value="update_data_supplement"' in html
    assert 'value="update_data_force"' in html
    assert 'value="update_chinese_supplement"' in html
    assert 'value="update_chinese_force"' in html
