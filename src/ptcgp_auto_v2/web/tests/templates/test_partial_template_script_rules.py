# -*- coding: utf-8 -*-
"""partial 模板脚本规范测试。"""

from pathlib import Path


def test_owned_card_partials_do_not_embed_script_tags():
    """拥有卡牌相关 partial 不应内嵌 script。"""
    targets = [
        Path("src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/record_list.html"),
    ]

    for path in targets:
        html = path.read_text(encoding="utf-8")
        assert "<script" not in html, f"{path} 不应包含内嵌 script"


def test_record_list_partial_does_not_embed_inline_click_handlers():
    """record_list 模板不应再使用内联点击事件，并改用 data-action 本地切换。"""
    html = Path("src/ptcgp_auto_v2/web/templates/partials/record_list.html").read_text(
        encoding="utf-8"
    )

    assert "onclick=" not in html
    assert 'id="batch-content-{{ item.batch_id }}"' in html
    assert 'data-action="show-batch-pack-detail"' in html
    assert 'data-action="show-batch-overview"' in html
