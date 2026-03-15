# -*- coding: utf-8 -*-
"""records 图片请求回归测试。"""

from pathlib import Path


def test_records_templates_use_400px_images_consistently() -> None:
    """records 概览与详情应统一使用 400 图，避免切换视图改 URL。"""
    html = Path("src/ptcgp_auto_v2/web/templates/partials/record_list.html").read_text(
        encoding="utf-8"
    )

    assert "w=200&output=png" not in html
    assert "w=400&output=png" in html


def test_records_templates_do_not_append_lang_to_internal_requests() -> None:
    """records 内部 HTMX 请求应复用统一语言上下文，不在模板拼 lang 参数。"""
    index_html = Path("src/ptcgp_auto_v2/web/templates/index.html").read_text(
        encoding="utf-8"
    )
    partial_html = Path(
        "src/ptcgp_auto_v2/web/templates/partials/record_list.html"
    ).read_text(encoding="utf-8")

    assert "/api/records?page=0&lang={{ current_lang }}" not in index_html
    assert (
        "/api/records?page={{ page + 1 }}&lang={{ current_lang }}" not in partial_html
    )
    assert (
        "/api/records/batch/{{ item.batch_id }}/pack/{{ pack.batch_index }}?lang="
        not in partial_html
    )
    assert (
        "/api/records/batch/{{ batch_id }}/pack/{{ pack.batch_index }}?lang="
        not in partial_html
    )


def test_auto_refresh_does_not_inject_lang_query_for_records() -> None:
    """自动刷新 URL 不应在前端兜底拼接 lang，避免与请求上下文分叉。"""
    script = Path("src/ptcgp_auto_v2/web/static/js/modules/auto_refresh.js").read_text(
        encoding="utf-8"
    )

    assert "searchParams.has('lang')" not in script
    assert "urlParams.get('lang') || 'en'" not in script
    assert "overrides.lang = lang" not in script


def test_records_batch_switch_uses_local_dom_swap_instead_of_htmx() -> None:
    """十连概览切详情应走本地 DOM 切换，不再为布局切换发 HTMX 请求。"""
    partial_html = Path(
        "src/ptcgp_auto_v2/web/templates/partials/record_list.html"
    ).read_text(encoding="utf-8")
    router_code = Path("src/ptcgp_auto_v2/web/routers/records.py").read_text(
        encoding="utf-8"
    )

    assert 'hx-get="/api/records/batch/' not in partial_html
    assert 'view_mode == "pack_detail"' not in partial_html
    assert 'view_mode == "batch_overview"' not in partial_html
    assert (
        '@router.get("/api/records/batch/{batch_id}/pack/{batch_index}"'
        not in router_code
    )
    assert '@router.get("/api/records/batch/{batch_id}"' not in router_code
