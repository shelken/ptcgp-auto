# -*- coding: utf-8 -*-

from sqlmodel import Session

from ptcgp_auto_v2.db.models import Account, Card, Notification
from ptcgp_auto_v2.web.services.notification_service import (
    build_notification_card_selector_context,
    build_notifications_context,
    get_task_type_options,
    list_rarity_codes,
    normalize_scene,
)


def test_list_rarity_codes_returns_db_codes(session: Session):
    """稀有度选项应来自数据库代码。"""
    session.add(
        Card(
            id=900001,
            number=1,
            name="测试卡",
            rarity="RR",
            type="Pokemon",
            set_code="A1",
            image_url="https://example.com/1.png",
        )
    )
    session.commit()
    assert "RR" in list_rarity_codes(session)


def test_normalize_scene_returns_empty_for_unknown_scene():
    """未知场景应归一为空字符串。"""
    assert normalize_scene("unknown") == ""
    assert normalize_scene("task_status") == "task_status"


def test_build_notifications_context_contains_accounts_and_configs(session: Session):
    """通知页面上下文应返回账号、配置和分页信息。"""
    account = Account(
        game_id="svc_acc_1", friend_id="1234567890123456", nickname="测试账号"
    )
    session.add(account)
    session.commit()
    session.refresh(account)

    session.add(
        Notification(
            scene="task_status",
            title="失败通知",
            content="任务失败",
            related_account_id=account.id,
            is_read=False,
        )
    )
    session.commit()

    context = build_notifications_context(
        session=session,
        lang="zh_CN",
        scene="task_status",
        account_id=account.id,
        page=0,
        page_size=10,
    )

    assert context["selected_scene"] == "task_status"
    assert context["selected_account_id"] == account.id
    assert context["total"] == 1
    assert len(context["notifications"]) == 1
    assert len(context["configs"]) == 3


def test_build_notification_card_selector_context_uses_code_filter(session: Session):
    """卡牌选择器应按稀有度代码筛选。"""
    session.add_all(
        [
            Card(
                id=900101,
                number=1,
                name="卡1",
                rarity="RR",
                type="Pokemon",
                set_code="A1",
                image_url="https://example.com/1.png",
            ),
            Card(
                id=900102,
                number=2,
                name="卡2",
                rarity="R",
                type="Pokemon",
                set_code="A1",
                image_url="https://example.com/2.png",
            ),
        ]
    )
    session.commit()

    context = build_notification_card_selector_context(
        session=session,
        lang="zh_CN",
        scene="rare_card_obtained",
        selected_card_ids=[900101],
        rarity="RR",
        page=0,
        page_size=24,
    )

    assert len(context["cards"]) == 1
    assert context["cards"][0].id == 900101
    assert context["card_selector_total"] == 1


def test_list_rarity_codes_excludes_r_from_notification_options(session: Session):
    """通知稀有度选项应排除 R。"""
    session.add_all(
        [
            Card(
                id=900201,
                number=1,
                name="卡R",
                rarity="R",
                type="Pokemon",
                set_code="A1",
                image_url="https://example.com/r.png",
            ),
            Card(
                id=900202,
                number=2,
                name="卡RR",
                rarity="RR",
                type="Pokemon",
                set_code="A1",
                image_url="https://example.com/rr.png",
            ),
        ]
    )
    session.commit()

    rarity_codes = list_rarity_codes(session)
    assert "R" not in rarity_codes
    assert "RR" in rarity_codes


def test_get_task_type_options_reads_from_registry(monkeypatch):
    """任务类型选项应从任务注册表动态读取。"""
    monkeypatch.setattr(
        "ptcgp_auto_v2.web.services.notification_service.TaskRegistry.all_types",
        lambda: ["dynamic_task_a", "dynamic_task_b"],
    )

    assert get_task_type_options() == ["dynamic_task_a", "dynamic_task_b"]
