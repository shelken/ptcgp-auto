# -*- coding: utf-8 -*-
"""Tooltip 模板约束测试。"""

from pathlib import Path


def test_templates_use_unified_tooltip_markup_instead_of_native_title() -> None:
    """已接入统一 tooltip 的模板不应再使用原生 title 提示。"""
    template_paths = [
        Path("src/ptcgp_auto_v2/web/templates/partials/account_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/macros/forms.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/edit_plan.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/record_list.html"),
    ]

    offenders = []
    for path in template_paths:
        content = path.read_text(encoding="utf-8")
        if 'title="' in content:
            offenders.append(str(path))

    assert not offenders, "以下模板仍残留原生 title tooltip: " + ", ".join(offenders)


def test_templates_keep_unified_tooltip_data_attributes() -> None:
    """统一 tooltip 入口应保留 data-tooltip 标记。"""
    owned_cards_template = Path("src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html").read_text(encoding="utf-8")
    account_list_template = Path("src/ptcgp_auto_v2/web/templates/partials/account_list.html").read_text(encoding="utf-8")
    edit_plan_template = Path("src/ptcgp_auto_v2/web/templates/partials/modals/edit_plan.html").read_text(encoding="utf-8")
    forms_template = Path("src/ptcgp_auto_v2/web/templates/partials/macros/forms.html").read_text(encoding="utf-8")

    assert 'class="owned-card-count tooltip-text"' in owned_cards_template
    assert 'data-tooltip="{{ item.owned_accounts_count }} {{ t.owned_accounts_label }}"' in owned_cards_template
    assert 'class="brutal-tag text-xs cursor-help tooltip-text"' in account_list_template
    assert 'class="brutal-btn text-xs p-2 tooltip-text"' in account_list_template
    assert 'data-tooltip="{{ t.desc_drag_reorder or \'Drag to reorder\' }}"' in edit_plan_template
    assert '{% if item.title %} tooltip-text{% endif %}' in forms_template
    assert '{% if item.title %}data-tooltip="{{ item.title }}"{% endif %}' in forms_template
