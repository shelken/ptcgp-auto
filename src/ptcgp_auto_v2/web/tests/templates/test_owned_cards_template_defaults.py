# -*- coding: utf-8 -*-
"""拥有卡牌模板默认行为测试。"""

from pathlib import Path


def test_owned_cards_container_defaults_to_show_counts():
    """拥有卡牌列表容器默认应显示数量。"""
    template = Path("src/ptcgp_auto_v2/web/templates/index.html").read_text(encoding="utf-8")

    assert 'id="owned-cards-container"' in template
    assert 'class="space-y-6 show-counts"' in template
    assert '{{ t.owned_counts_hide }}' in template


def test_owned_card_list_has_bottom_name_overlay():
    """拥有卡牌列表项应包含底部卡名悬浮层。"""
    template = Path("src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html").read_text(encoding="utf-8")

    assert 'class="owned-card brutal-card group"' in template
    assert 'class="absolute bottom-0 left-0 right-0 text-xs py-2 px-2 text-center font-bold translate-y-full group-hover:translate-y-0 transition-transform duration-200 card-name-overlay tooltip-text"' in template
    assert '{{ item.card_display_name or item.card.name }}' in template


def test_owned_card_detail_uses_compact_tag_layout():
    """拥有卡牌详情应使用紧凑标签展示系列、编号和稀有度。"""
    template = Path("src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html").read_text(encoding="utf-8")

    assert '{{ card.set_code }}' in template
    assert '{{ t.label_set_code }}' not in template
    assert '{{ t.label_card_number }}' not in template
    assert '{{ t.label_rarity }}' not in template
    assert '<span class="brutal-tag text-xs">#{{ card.number }}</span>' in template
    assert '<span class="brutal-tag text-xs">{{ card.rarity|rarity_display(current_lang) }}</span>' in template


def test_owned_card_modal_probe_uses_same_compact_account_row():
    """拥有卡牌弹窗 probe 的账号行应与真实表格保持同构，避免 page_size 算偏。"""
    template = Path("src/ptcgp_auto_v2/web/templates/index.html").read_text(encoding="utf-8")

    assert '<div class="space-y-1 account-identity-cell">' in template
    assert '<div class="font-bold text-base leading-tight">#1 {{ t.probe_placeholder or \'PROBE\' }}</div>' in template
    assert '{{ t.account_id or \'Account ID\' }}: #1' not in template
