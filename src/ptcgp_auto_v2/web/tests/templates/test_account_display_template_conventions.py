# -*- coding: utf-8 -*-
"""账号展示模板约束测试。"""

from pathlib import Path


LEGACY_PATTERNS = [
    "{{ t.col_account_id or 'Account ID' }}: #{{",
    "{{ t.account_id }} #{{",
    "~ ' #' ~ account.id",
    "· #{{ row.to_account_id }}",
    "· #{{ row.target_account_id }}",
    "· #{{ row.friend_account_id }}",
    "· #{{ item.right_account_id }}",
]


def test_account_display_templates_do_not_use_legacy_id_layout():
    """账号展示模板不应再使用旧的账号 ID 分行或尾随写法。"""
    template_paths = [
        Path("src/ptcgp_auto_v2/web/templates/index.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/account_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/exchange_card_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/friendship_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/notification_page.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/record_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/resource_pack_points_table.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/resource_stats_table.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/task_account_options.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/task_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/edit_account_plans.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html"),
    ]

    offenders = []
    for path in template_paths:
        content = path.read_text(encoding="utf-8")
        for pattern in LEGACY_PATTERNS:
            if pattern in content:
                offenders.append(f"{path}: {pattern}")

    assert not offenders, "以下模板仍残留旧账号展示写法: " + ", ".join(offenders)
