# -*- coding: utf-8 -*-
"""
Notifier 单元测试
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from sqlmodel import SQLModel, Session, create_engine, select

# 避免循环导入，先设置 PYTHONPATH
sys.path.insert(0, "src")


@pytest.fixture(name="engine")
def engine_fixture():
    from ptcgp_auto_v2.db.models import Notification, NotificationConfig

    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


class TestNotifierNotify:
    """基础通知测试"""

    def test_build_webhook_payload_without_image_uses_markdown(self):
        """无图片时应使用 markdown_v2 消息格式。"""
        from ptcgp_auto_v2.infra.notifier import Notifier

        payload = Notifier._build_webhook_payload(title="标题", content="内容")

        assert payload["msgtype"] == "markdown_v2"
        assert payload["markdown_v2"]["content"].startswith("## 标题")

    def test_build_webhook_payload_with_image_uses_markdown_v2(self):
        """Webhook 载荷构造不处理图片注入，保持内容原样。"""
        from ptcgp_auto_v2.infra.notifier import Notifier

        payload = Notifier._build_webhook_payload(title="标题", content="内容")

        assert payload["msgtype"] == "markdown_v2"
        assert payload["markdown_v2"]["content"] == "## 标题\n\n内容"

    def test_notify_creates_notification_when_enabled(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.models import NotificationConfig

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            notifier = Notifier()
            result = notifier.notify(
                scene="task_status",
                title="测试通知",
                content="测试内容",
            )

            assert result is True

    def test_notify_skips_when_disabled(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("task_status")
            config_repo.update(scene="task_status", enabled=False)

            notifier = Notifier()
            result = notifier.notify(
                scene="task_status",
                title="测试通知",
                content="测试内容",
            )

            assert result is False

    def test_notify_sends_webhook_when_enabled(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
            patch("ptcgp_auto_v2.infra.notifier.requests.post") as mock_post,
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("task_status")
            config_repo.update(scene="task_status", enabled=True, enabled_webhook=True)

            mock_post.return_value.status_code = 200

            notifier = Notifier(webhook_url="https://test.webhook.url")
            notifier.notify(
                scene="task_status",
                title="测试通知",
                content="测试内容",
            )

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://test.webhook.url"
            assert call_args[1]["json"]["msgtype"] == "markdown_v2"

    def test_notify_uses_markdown_v2_when_image_url_provided(self, engine):
        """传入图片 URL 时仍走 markdown_v2，正文由调用方决定。"""
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
            patch("ptcgp_auto_v2.infra.notifier.requests.post") as mock_post,
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("task_status")
            config_repo.update(scene="task_status", enabled=True, enabled_webhook=True)

            mock_post.return_value.status_code = 200

            notifier = Notifier(webhook_url="https://test.webhook.url")
            notifier.notify(
                scene="task_status",
                title="测试通知",
                content="测试内容",
                image_url="https://example.com/card.png",
            )

            assert mock_post.call_count == 1
            payload = mock_post.call_args.kwargs["json"]
            assert payload["msgtype"] == "markdown_v2"
            assert payload["markdown_v2"]["content"] == "## 测试通知\n\n测试内容"

    def test_notifier_supports_notify_key_env(self, engine, monkeypatch):
        """仅提供 NOTIFY_KEY 时应自动拼接企微 webhook URL。"""
        from ptcgp_auto_v2.infra.notifier import Notifier

        monkeypatch.delenv("PTCGP_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("PTCGP_NOTIFY_KEY", raising=False)
        monkeypatch.setenv("NOTIFY_KEY", "abc-key-123")

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            notifier = Notifier()
            assert (
                notifier.webhook_url
                == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc-key-123"
            )

    def test_notifier_prefers_webhook_url_over_notify_key(self, engine, monkeypatch):
        """同时存在 URL 与 KEY 时，应优先使用完整 URL。"""
        from ptcgp_auto_v2.infra.notifier import Notifier

        monkeypatch.setenv("PTCGP_WEBHOOK_URL", "https://example.test/full-url")
        monkeypatch.delenv("PTCGP_NOTIFY_KEY", raising=False)
        monkeypatch.setenv("NOTIFY_KEY", "abc-key-123")

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            notifier = Notifier()
            assert notifier.webhook_url == "https://example.test/full-url"

    def test_notifier_loads_notify_key_from_dotenv(self, engine, monkeypatch, tmp_path):
        """当环境变量缺失时，应支持从 .env 的 NOTIFY_KEY 读取。"""
        from ptcgp_auto_v2.config import settings as settings_module
        from ptcgp_auto_v2.infra.notifier import Notifier

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("NOTIFY_KEY=dotenv-key-xyz\n")
        monkeypatch.delenv("PTCGP_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("PTCGP_NOTIFY_KEY", raising=False)
        monkeypatch.delenv("NOTIFY_KEY", raising=False)
        monkeypatch.setattr(settings_module, "_dotenv_loaded", False)

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            notifier = Notifier()
            assert (
                notifier.webhook_url
                == "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=dotenv-key-xyz"
            )


class TestNotifierRareCard:
    """稀有卡牌通知测试"""

    def test_notify_rare_card_by_rarity(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            mock_card = MagicMock()
            mock_card.id = 1
            mock_card.name = "皮卡丘 ex"
            mock_card.rarity = "RR"

            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"

            notifier = Notifier()
            result = notifier.notify_rare_card(
                account=mock_account,
                card=mock_card,
                rarity="RR",
                image_url="https://example.com/card.png",
            )

            assert result is True

            from ptcgp_auto_v2.db.models import Notification

            with Session(engine) as session:
                row = session.exec(select(Notification)).first()
                assert row is not None
                assert "RR (4钻)" in row.content
                assert "**" not in row.content

    def test_notify_rare_card_by_card_id(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("rare_card_obtained")
            config_repo.update(
                scene="rare_card_obtained",
                extra_config={
                    "notify_by_rarity": [],
                    "notify_card_ids": [123],
                },
            )

            mock_card = MagicMock()
            mock_card.id = 123
            mock_card.name = "特殊卡牌"
            mock_card.rarity = "C"

            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"

            notifier = Notifier()
            result = notifier.notify_rare_card(
                account=mock_account,
                card=mock_card,
                rarity="C",
            )

            assert result is True

    def test_notify_rare_card_uses_caller_event_message(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            mock_card = MagicMock()
            mock_card.id = 1
            mock_card.name = "皮卡丘 ex"
            mock_card.rarity = "RR"

            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"

            notifier = Notifier()
            result = notifier.notify_rare_card(
                account=mock_account,
                card=mock_card,
                rarity="RR",
                message="得卡挑战获得稀有卡牌",
            )

            assert result is True

            from ptcgp_auto_v2.db.models import Notification

            with Session(engine) as session:
                row = session.exec(select(Notification)).first()
                assert row is not None
                assert "事件: 得卡挑战获得稀有卡牌" in row.content

    def test_notify_rare_card_skips_when_not_matching(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("rare_card_obtained")
            config_repo.update(
                scene="rare_card_obtained",
                extra_config={
                    "notify_by_rarity": ["RR", "UR"],
                    "notify_card_ids": [],
                },
            )

            mock_card = MagicMock()
            mock_card.id = 1
            mock_card.name = "普通卡牌"
            mock_card.rarity = "C"

            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"

            notifier = Notifier()
            result = notifier.notify_rare_card(
                account=mock_account,
                card=mock_card,
                rarity="C",
            )

            assert result is False

    def test_notify_rare_card_webhook_image_uses_set_code_and_number(self, engine):
        """稀有卡牌通知的图片地址应按 set_code/number 生成，与 Web 展示一致。"""
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
            patch("ptcgp_auto_v2.infra.notifier.requests.post") as mock_post,
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("rare_card_obtained")
            config_repo.update(
                scene="rare_card_obtained",
                enabled=True,
                enabled_webhook=True,
                extra_config={"notify_by_rarity": ["SR"], "notify_card_ids": []},
            )

            mock_post.return_value.status_code = 200

            mock_card = MagicMock()
            mock_card.id = 260
            mock_card.name = "Zapdos ex"
            mock_card.rarity = "SR"
            mock_card.set_code = "A1"
            mock_card.number = 260

            mock_account = MagicMock()
            mock_account.id = 159
            mock_account.nickname = "skn159"

            notifier = Notifier(webhook_url="https://example.test/webhook")
            result = notifier.notify_rare_card(
                account=mock_account,
                card=mock_card,
                rarity="SR",
                image_url="cPK_20_001040_00_THUNDERex_SR.webp",
            )

            assert result is True
            assert mock_post.call_count == 1
            markdown_payload = mock_post.call_args.kwargs["json"]
            assert markdown_payload["msgtype"] == "markdown_v2"
            assert (
                "![Zapdos ex](https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh-TW/cards-by-set/A1/260.png)"
                in markdown_payload["markdown_v2"]["content"]
            )


class TestNotifierTaskStatus:
    """任务状态通知测试"""

    def test_notify_task_status_account_name_appends_id(self, engine):
        """账号显示应在昵称后追加账号 ID。"""
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"
            mock_account.display_name = None

            mock_task = MagicMock()
            mock_task.id = 100
            mock_task.task_type = "open_pack"
            mock_task.account = mock_account

            notifier = Notifier()
            result = notifier.notify_task_status(
                task_instance=mock_task,
                status="failed",
                message="认证过期",
            )

            assert result is True

            from ptcgp_auto_v2.db.models import Notification

            with Session(engine) as session:
                row = session.exec(select(Notification)).first()
                assert row is not None
                assert "账号: 测试账号 (1)" in row.content

    def test_notify_task_status_failed(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            mock_account = MagicMock()
            mock_account.id = 1
            mock_account.nickname = "测试账号"

            mock_task = MagicMock()
            mock_task.id = 100
            mock_task.task_type = "open_pack"
            mock_task.account = mock_account

            notifier = Notifier()
            result = notifier.notify_task_status(
                task_instance=mock_task,
                status="failed",
                message="认证过期",
            )

            assert result is True

            from ptcgp_auto_v2.db.models import Notification

            with Session(engine) as session:
                row = session.exec(select(Notification)).first()
                assert row is not None
                assert "状态: 失败" in row.content
                assert "**" not in row.content

    def test_notify_task_status_filters_by_task_type(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier
        from ptcgp_auto_v2.db.repositories.notification_config_repository import (
            NotificationConfigRepository,
        )

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            config_repo = NotificationConfigRepository()
            config_repo.get_or_create("task_status")
            config_repo.update(
                scene="task_status",
                extra_config={
                    "notify_task_types": ["open_pack"],
                    "notify_on": ["failed"],
                },
            )

            mock_account = MagicMock()
            mock_account.id = 1

            mock_task = MagicMock()
            mock_task.id = 100
            mock_task.task_type = "send_card_daily"
            mock_task.account = mock_account

            notifier = Notifier()
            result = notifier.notify_task_status(
                task_instance=mock_task,
                status="failed",
                message="测试错误",
            )

            assert result is False

    def test_notify_task_status_filters_by_status(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            mock_account = MagicMock()
            mock_account.id = 1

            mock_task = MagicMock()
            mock_task.id = 100
            mock_task.task_type = "open_pack"
            mock_task.account = mock_account

            notifier = Notifier()
            # success 默认不在通知列表
            result = notifier.notify_task_status(
                task_instance=mock_task,
                status="success",
                message="完成",
            )

            assert result is False


class TestNotifierSystemWarning:
    """系统警告通知测试"""

    def test_notify_system_warning(self, engine):
        from ptcgp_auto_v2.infra.notifier import Notifier

        with (
            patch(
                "ptcgp_auto_v2.db.repositories.notification_config_repository.get_engine",
                return_value=engine,
            ),
            patch(
                "ptcgp_auto_v2.db.repositories.notification_repository.get_engine",
                return_value=engine,
            ),
        ):
            notifier = Notifier()
            result = notifier.notify_system_warning(
                title="设备异常",
                message="设备 5555 连接失败",
            )

            assert result is True

            from ptcgp_auto_v2.db.models import Notification

            with Session(engine) as session:
                row = session.exec(select(Notification)).first()
                assert row is not None
                assert "时间:" in row.content
                assert "**" not in row.content


class TestGetNotifier:
    """全局实例测试"""

    def test_get_notifier_returns_singleton(self):
        from ptcgp_auto_v2.infra.notifier import get_notifier
        import ptcgp_auto_v2.infra.notifier as module

        # 清除现有实例
        module._notifier_instance = None

        notifier1 = get_notifier()
        notifier2 = get_notifier()

        assert notifier1 is notifier2
