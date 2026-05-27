# -*- coding: utf-8 -*-
"""任务失败日志持久化测试。"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

from loguru import logger

from ptcgp_auto_v2.infra.task_failure_logs import (
    TaskFailureLogContext,
    cleanup_old_task_failure_logs,
)
from ptcgp_auto_v2.utils.logger import clear_context, set_context


def test_failed_task_log_only_contains_current_capture(tmp_path: Path):
    """失败日志只保存捕获区间内的任务日志。"""
    log_dir = tmp_path / "logs"

    logger.info("任务开始前日志")
    set_context(device="auto-1", nickname="skn12", task="claim_rewards")
    with TaskFailureLogContext(
        log_dir=log_dir,
        started_at=datetime(2026, 5, 2, 23, 10, 0),
        account_id=12,
        account_name="skn12",
        task_type="claim_rewards",
        task_instance_id=345,
    ) as capture:
        logger.info("执行任务: claim_rewards")
        logger.trace("OCR 原始细节")
        logger.warning("任务页面卡住")
        other_thread = threading.Thread(
            target=lambda: logger.error("其他任务日志"),
            daemon=True,
        )
        other_thread.start()
        other_thread.join()
        saved_path = capture.persist_failure("超过最大迭代次数 150")
    logger.error("任务结束后日志")

    assert saved_path == log_dir / "20260502-231000_account-12-skn12_task-claim_rewards_instance-345_failed.jsonl"
    events = [
        json.loads(line)
        for line in saved_path.read_text(encoding="utf-8").splitlines()
    ]
    assert events[0] == {
        "event": "task_failure_summary",
        "task_started_at": "2026-05-02T23:10:00",
        "account_id": 12,
        "account_name": "skn12",
        "task_type": "claim_rewards",
        "task_instance_id": 345,
        "failure_reason": "超过最大迭代次数 150",
    }
    messages = [event.get("message") for event in events]
    assert "执行任务: claim_rewards" in messages
    assert "任务页面卡住" in messages
    assert "OCR 原始细节" in messages
    assert "任务开始前日志" not in messages
    assert "任务结束后日志" not in messages
    assert "其他任务日志" not in messages
    trace_event = next(event for event in events if event.get("message") == "OCR 原始细节")
    assert trace_event["level"] == "TRACE"
    assert trace_event["device"] == "auto-1"
    assert trace_event["account"] == "skn12"
    assert trace_event["task"] == "claim_rewards"
    clear_context()


def test_successful_task_capture_does_not_create_file(tmp_path: Path):
    """成功任务不落盘。"""
    with TaskFailureLogContext(
        log_dir=tmp_path / "logs",
        started_at=datetime(2026, 5, 2, 23, 10, 0),
        account_id=12,
        account_name="skn12",
        task_type="open_pack",
        task_instance_id=345,
    ):
        logger.info("执行任务: open_pack")

    assert not list((tmp_path / "logs").glob("*.jsonl"))


def test_cleanup_old_task_failure_logs_keeps_recent_3_days(tmp_path: Path):
    """清理只删除 3 天前的失败日志。"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    old_file = log_dir / "old.jsonl"
    recent_file = log_dir / "recent.jsonl"
    old_file.write_text("old", encoding="utf-8")
    recent_file.write_text("recent", encoding="utf-8")

    now = datetime(2026, 5, 2, 12, 0, 0)
    old_ts = (now - timedelta(days=4)).timestamp()
    recent_ts = (now - timedelta(days=2)).timestamp()
    os.utime(old_file, (old_ts, old_ts))
    os.utime(recent_file, (recent_ts, recent_ts))

    cleanup_old_task_failure_logs(log_dir=log_dir, now=now)

    assert not old_file.exists()
    assert recent_file.exists()
