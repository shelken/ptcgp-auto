import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from ptcgp_auto_v2.config.settings import Settings
from ptcgp_auto_v2.core.scheduler import Scheduler
from ptcgp_auto_v2.core.task_base import ResetType
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.models import Account, TaskPlan, TaskInstance, AccountTaskPlan


@pytest.fixture
def mock_scheduler():
    scheduler = Scheduler(device_addresses=[])
    scheduler._task_instance_repo = MagicMock()
    scheduler._account_repo = MagicMock()
    return scheduler


def test_should_reset_interval_task(mock_scheduler):
    # Setup
    now = datetime.now()
    last_completed = now - timedelta(minutes=61)  # 61 分钟前完成

    instance = TaskInstance(
        id=1,
        account_id=1,
        task_type="open_pack",
        status=TaskStatus.COMPLETED.value,
        last_completed_at=last_completed,
        reset_type=ResetType.INTERVAL.value,
    )

    config = {
        "reset_type": "interval",
        "interval_seconds": 3600,  # 1小时
    }

    # Test: Should reset because 61 min > 60 min
    should_reset = mock_scheduler._should_reset_task(
        instance, ResetType.INTERVAL, config
    )
    assert should_reset is True


def test_should_not_reset_interval_task_too_soon(mock_scheduler):
    # Setup
    now = datetime.now()
    last_completed = now - timedelta(minutes=30)  # 30 分钟前完成

    instance = TaskInstance(
        id=1,
        account_id=1,
        task_type="open_pack",
        status=TaskStatus.COMPLETED.value,
        last_completed_at=last_completed,
        reset_type=ResetType.INTERVAL.value,
    )

    config = {"reset_type": "interval", "interval_seconds": 3600}

    # Test: Should NOT reset because 30 min < 60 min
    should_reset = mock_scheduler._should_reset_task(
        instance, ResetType.INTERVAL, config
    )
    assert should_reset is False


def test_aggregation_logic(mock_scheduler):
    # 模拟一个账号有两个 Plan
    account = Account(id=1, nickname="TestUser")

    # Plan 1: Daily (默认)
    plan1 = TaskPlan(id=1, name="daily", configuration="{}", task_types='["open_pack"]')

    # Plan 2: Hourly (High Priority)
    plan2 = TaskPlan(
        id=2,
        name="hourly",
        configuration='{"open_pack": {"reset_type": "interval", "interval_seconds": 3600}}',
        task_types='["open_pack"]',
    )

    # 关联
    # 模拟 account.task_plan_associations (新关联)
    assoc1 = AccountTaskPlan(account_id=1, task_plan_id=1, is_active=True, priority=0)
    assoc1.task_plan = plan1

    assoc2 = AccountTaskPlan(account_id=1, task_plan_id=2, is_active=True, priority=10)
    assoc2.task_plan = plan2

    account.task_plan_associations = [assoc1, assoc2]

    # 执行聚合
    aggregated = mock_scheduler._aggregate_account_plans(account)

    # 验证
    assert "open_pack" in aggregated
    config = aggregated["open_pack"]
    # 应该被 Plan 2 覆盖 (因为它 priority 高，且在列表后面处理? wait, check logic)
    # logic: sorted by priority. low -> high. later overrides earlier.
    # priority 10 should come after priority 0 (implied for base plan).
    # actually base plan is processed first, then associations sorted by priority.

    assert config["reset_type"] == "interval"
    assert config["interval_seconds"] == 3600


def test_settings_auto_scale_defaults():
    settings = Settings()
    assert settings.auto_scale_emulators is False
    assert settings.auto_scale_instance_prefix == "auto-"
    assert settings.auto_scale_min_idle_devices == 1
    assert settings.auto_scale_max_devices == 2
    assert settings.auto_scale_pending_step == 10
    assert settings.auto_scale_eval_interval_seconds == 60
    assert settings.auto_scale_idle_seconds == 180
