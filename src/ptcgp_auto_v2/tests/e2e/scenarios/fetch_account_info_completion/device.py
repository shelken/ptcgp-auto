# -*- coding: utf-8 -*-
"""fetch_account_info 实机 E2E 场景。

这个文件负责验证真实设备执行 `fetch_account_info` 的完成闭环。这个场景覆盖账号资料字段和账号资源字段的数据库回写结果。它依赖 Scheduler、session_scope 与 RepositoryFactory 访问克隆测试库。
"""

from __future__ import annotations

import threading

from ptcgp_auto_v2.core.scheduler import SchedulerConfig
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory


def _clear_account_sync_fields(account_id: int):
    """之前场景没有主动制造缺失字段。现在会先清空目标账号资料和资源字段。这样可以直接证明任务执行后的回写结果来自本次真实链路。"""
    with session_scope() as session:
        repos = RepositoryFactory(session)
        account = repos.accounts().get_by_id(account_id)
        if account is None:
            raise RuntimeError(f"account not found: {account_id}")
        account.friend_id = None
        account.nickname = None
        account.level = None
        if not repos.accounts().update(account):
            raise RuntimeError(f"failed to clear account fields: {account_id}")
        repos.account_stats().upsert(
            account_id=account_id,
            exchange_points=None,
            pack_hourglass_count=None,
        )


def _read_account_sync_fields(account_id: int) -> dict[str, object]:
    """之前场景没有统一读取回写结果。现在会在事务内把账号字段和资源字段收敛成纯数据字典。这样断言时不会把 ORM 实体带出事务边界。"""
    with session_scope() as session:
        repos = RepositoryFactory(session)
        account = repos.accounts().get_by_id(account_id)
        if account is None:
            raise RuntimeError(f"account not found after run: {account_id}")
        stat = repos.account_stats().get_by_account_id_data(account_id)
        return {
            "friend_id": account.friend_id,
            "nickname": account.nickname,
            "level": account.level,
            "exchange_points": None if stat is None else stat.exchange_points,
            "pack_hourglass_count": (
                None if stat is None else stat.pack_hourglass_count
            ),
        }


def run(ctx):
    """之前缺少 fetch_account_info 的实机 E2E。现在会清空克隆库中的目标字段后跑真实任务并校验回写。这样能证明 fetch_account_info 在真实设备链路上完成同步。"""
    ctx.log(ctx.config.description)
    device_config = ctx.require_device_config()
    join_timeout = int(ctx.config.params["join_timeout_seconds"])
    lease_timeout = int(ctx.config.params["lease_timeout_seconds"])
    harness = ctx.harness
    harness.mute_other_accounts(device_config.account_id)
    harness.mute_other_tasks_for_account(device_config.account_id, ctx.config.task_type)
    _clear_account_sync_fields(device_config.account_id)
    harness.ensure_task_pending(device_config.account_id, ctx.config.task_type)

    scheduler = harness.create_scheduler(
        SchedulerConfig(
            poll_interval=0.5,
            max_workers=1,
            task_generation_interval=3600,
            stale_task_check_interval=1,
            stale_task_timeout=lease_timeout,
        )
    )

    result: dict[str, bool] = {}

    def _run_single():
        result["success"] = scheduler.run_single_task(
            device_config.device_address,
            device_config.account_id,
            ctx.config.task_type,
        )

    runner = threading.Thread(target=_run_single, daemon=True)
    runner.start()
    runner.join(timeout=join_timeout)
    if runner.is_alive():
        runner.join(timeout=15)
        raise AssertionError("device fetch_account_info completion timeout")

    assert result.get("success") is True
    snapshot = harness.snapshot_runtime(
        device_config.account_id,
        ctx.config.task_type,
        scheduler=scheduler,
    )
    expected_statuses = {TaskStatus.COMPLETED.value}
    if ctx.config.allow_skipped:
        expected_statuses.add(TaskStatus.SKIPPED.value)
    assert snapshot["task_status"] in expected_statuses
    assert snapshot["active_in_scheduler"] is False

    account_state = _read_account_sync_fields(device_config.account_id)
    assert account_state["friend_id"]
    assert account_state["nickname"]
    assert account_state["level"] is not None
    assert account_state["exchange_points"] is not None
    assert account_state["pack_hourglass_count"] is not None
