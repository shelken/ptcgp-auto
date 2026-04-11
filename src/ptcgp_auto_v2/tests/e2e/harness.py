# -*- coding: utf-8 -*-
"""E2E 运行时测试公共工具。"""

from __future__ import annotations

import os
import time
import logging
import json
import re
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from sqlmodel import update

from ptcgp_auto_v2.config.settings import Settings, set_settings
from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig
from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.models import Account, AccountStat, TaskInstance
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory

E2E_DB_PATH_ENV = "PTCGP_E2E_DB_PATH"
E2E_DEVICE_ENV = "PTCGP_E2E_DEVICE"
E2E_TRACE_FILE_ENV = "PTCGP_E2E_TRACE_FILE"
E2E_TRACE_SNAPSHOT_MODE_ENV = "PTCGP_E2E_TRACE_SNAPSHOT_MODE"
E2E_APP_LOG_LEVEL_ENV = "PTCGP_E2E_APP_LOG_LEVEL"
E2E_CONSOLE_LOG_LEVEL_ENV = "PTCGP_E2E_CONSOLE_LOG_LEVEL"
E2E_RAW_LOG_FILE_ENV = "PTCGP_E2E_RAW_LOG_FILE"
APP_LOG_FILE_ENV = "PTCGP_LOG_FILE"
APP_LOG_FILE_LEVEL_ENV = "PTCGP_LOG_FILE_LEVEL"
logger = logging.getLogger(__name__)


def _parse_vmmap_mb(label: str, raw: str) -> float | None:
    pattern = rf"{re.escape(label)}:\s+([0-9]+(?:\.[0-9]+)?)M"
    match = re.search(pattern, raw)
    if match is None:
        return None
    return float(match.group(1))


def _parse_vmmap_resident_mb(section_name: str, raw: str) -> float | None:
    pattern = (
        rf"{re.escape(section_name)}: .*resident=([0-9]+(?:\.[0-9]+)?)M"
    )
    match = re.search(pattern, raw)
    if match is None:
        return None
    return float(match.group(1))


def parse_vmmap_summary(raw: str) -> dict[str, float | None]:
    """解析 vmmap -summary 输出中的关键指标。"""
    return {
        "physical_footprint_mb": _parse_vmmap_mb("Physical footprint", raw),
        "readonly_libraries_resident_mb": _parse_vmmap_resident_mb(
            "ReadOnly portion of Libraries",
            raw,
        ),
        "writable_regions_resident_mb": _parse_vmmap_resident_mb(
            "Writable regions",
            raw,
        ),
    }


def extract_loaded_library_matches(raw: str, patterns: list[str]) -> list[str]:
    """从 lsof 输出中过滤命中的动态库路径。"""
    if not patterns:
        return []
    lowered_patterns = [pattern.lower() for pattern in patterns]
    matched: list[str] = []
    seen: set[str] = set()
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lowered = stripped.lower()
        if not any(pattern in lowered for pattern in lowered_patterns):
            continue
        if stripped in seen:
            continue
        seen.add(stripped)
        matched.append(stripped)
    return matched


def reset_db_singletons():
    """重置全局数据库单例，确保测试间隔离。"""
    from ptcgp_auto_v2.db import connection as connection_module
    from ptcgp_auto_v2.db import engine as engine_module

    db_instance = getattr(connection_module, "_db_instance", None)
    if db_instance is not None:
        db_instance.close()
    connection_module._db_instance = None
    engine_module._engine = None


def rebind_test_runtime(db_path: Path, device_addresses: list[str]):
    """将当前进程绑定到测试数据库与测试设备。"""
    reset_db_singletons()
    file_log_level = os.getenv(E2E_APP_LOG_LEVEL_ENV, "TRACE").strip().upper()
    console_log_level = os.getenv(E2E_CONSOLE_LOG_LEVEL_ENV, "ERROR").strip().upper()
    raw_log_file = os.getenv(E2E_RAW_LOG_FILE_ENV, "").strip()
    if raw_log_file:
        raw_log_path = Path(raw_log_file)
        raw_log_path.parent.mkdir(parents=True, exist_ok=True)
        os.environ[APP_LOG_FILE_ENV] = str(raw_log_path)
        os.environ[APP_LOG_FILE_LEVEL_ENV] = file_log_level
    else:
        os.environ.pop(APP_LOG_FILE_ENV, None)
        os.environ.pop(APP_LOG_FILE_LEVEL_ENV, None)
    settings = Settings(
        device_addresses=device_addresses,
        data_dir=db_path.parent,
        db_name=db_path.name,
        debug=(console_log_level in {"DEBUG", "TRACE"}),
        log_level=console_log_level,
    )
    settings.auto_scale_emulators = False
    set_settings(settings)
    settings.configure_logging()
    get_database(db_path)


def configure_runtime_from_env(default_device: str = "127.0.0.1:29999") -> Path:
    """从环境变量恢复测试运行时配置（供子进程使用）。"""
    raw_db_path = os.getenv(E2E_DB_PATH_ENV)
    if not raw_db_path:
        raise RuntimeError(f"missing env: {E2E_DB_PATH_ENV}")
    db_path = Path(raw_db_path)
    device = os.getenv(E2E_DEVICE_ENV, default_device)
    rebind_test_runtime(db_path, [device])
    return db_path


def get_task_reset_type(task_type: str) -> str:
    """读取任务类型对应的 reset_type。"""
    task_class = TaskRegistry.get(task_type)
    return task_class.reset_type.value


def create_seed_account_with_task(
    task_type: str,
    *,
    reset_type: Optional[str] = None,
) -> tuple[int, int]:
    """创建最小可调度账号和一条任务。"""
    effective_reset_type = reset_type or get_task_reset_type(task_type)
    suffix = str(int(time.time() * 1_000_000))

    with session_scope() as session:
        account = Account(
            game_id=f"e2e_game_{suffix}",
            friend_id="1234567890123456",
            nickname=f"e2e_{suffix[-6:]}",
            xml_content=b"e2e",
            country="SG",
        )
        session.add(account)
        session.flush()
        if account.id is None:
            raise RuntimeError("seed account id is None")

        session.add(
            AccountStat(
                account_id=account.id,
                exchange_points=1,
                pack_hourglass_count=1,
            )
        )

        task = TaskInstance(
            account_id=account.id,
            task_type=task_type,
            status="pending",
            reset_type=effective_reset_type,
        )
        session.add(task)
        session.flush()
        if task.id is None:
            raise RuntimeError("seed task id is None")
        return account.id, task.id


class SchedulerHarness:
    """E2E 调度测试框架。"""

    def __init__(self, *, db_path: Path, device_addresses: list[str]):
        self.db_path = db_path
        self.device_addresses = device_addresses
        self._scheduler: Optional[Scheduler] = None
        self._trace_file = os.getenv(E2E_TRACE_FILE_ENV, "").strip()
        self._trace_snapshot_mode = os.getenv(
            E2E_TRACE_SNAPSHOT_MODE_ENV,
            "changes",
        ).strip().lower()
        self._snapshot_signatures: dict[tuple[int, str], tuple] = {}
        self._trace_lock = threading.Lock()

    def _trace_event(self, event: str, **payload):
        if not self._trace_file:
            return
        record = {
            "event": event,
            "ts": datetime.now().isoformat(),
            **payload,
        }
        line = json.dumps(record, ensure_ascii=False)
        path = Path(self._trace_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._trace_lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def create_scheduler(self, config: SchedulerConfig) -> Scheduler:
        """创建调度器（不启动主循环）。"""
        logger.info(
            "create_scheduler db=%s devices=%s poll=%.2f max_workers=%s",
            self.db_path,
            self.device_addresses,
            config.poll_interval,
            config.max_workers,
        )
        self._trace_event(
            "create_scheduler",
            db_path=str(self.db_path),
            device_addresses=self.device_addresses,
            poll_interval=config.poll_interval,
            max_workers=config.max_workers,
        )
        rebind_test_runtime(self.db_path, self.device_addresses)
        return Scheduler(device_addresses=self.device_addresses, config=config)

    def start_scheduler(self, config: SchedulerConfig) -> Scheduler:
        """启动调度器后台主循环。"""
        scheduler = self.create_scheduler(config)
        scheduler.start()
        self._scheduler = scheduler
        logger.info("start_scheduler ok")
        self._trace_event("start_scheduler")
        return scheduler

    def stop_scheduler(self):
        """停止当前调度器。"""
        if self._scheduler is None:
            return
        logger.info("stop_scheduler start")
        self._trace_event("stop_scheduler_start")
        self._scheduler.stop(wait=True)
        self._scheduler = None
        logger.info("stop_scheduler done")
        self._trace_event("stop_scheduler_done")

    def override_scheduler_lease_timeout(self, scheduler: Scheduler, timeout_seconds: int):
        """覆盖调度器卡死检测超时时间（兼容旧方法名）。"""
        scheduler.config.stale_task_timeout = int(timeout_seconds)
        scheduler.config.stale_task_check_interval = min(
            scheduler.config.stale_task_check_interval,
            1,
        )
        runtime_supervisor = getattr(scheduler, "_runtime_supervisor", None)
        if runtime_supervisor is not None:
            runtime_supervisor.lease_timeout_seconds = int(timeout_seconds)
        logger.info("override stale timeout to %ss", timeout_seconds)
        self._trace_event("override_stale_timeout", timeout_seconds=timeout_seconds)

    def wait_until(
        self,
        predicate: Callable[[], object],
        *,
        timeout_s: float,
        interval_s: float = 0.2,
        failure_message: str = "condition not met before timeout",
    ) -> object:
        """轮询等待条件成立。"""
        logger.info(
            "wait_until start timeout=%.1fs interval=%.1fs msg=%s",
            timeout_s,
            interval_s,
            failure_message,
        )
        self._trace_event(
            "wait_until_start",
            timeout_s=timeout_s,
            interval_s=interval_s,
            failure_message=failure_message,
        )
        deadline = time.time() + timeout_s
        attempts = 0
        while time.time() < deadline:
            attempts += 1
            result = predicate()
            if result:
                logger.info("wait_until success attempts=%s", attempts)
                self._trace_event("wait_until_success", attempts=attempts)
                return result
            if attempts % 10 == 0:
                logger.debug("wait_until retry attempts=%s", attempts)
            time.sleep(interval_s)
        logger.error("wait_until timeout attempts=%s msg=%s", attempts, failure_message)
        self._trace_event(
            "wait_until_timeout",
            attempts=attempts,
            failure_message=failure_message,
        )
        raise AssertionError(failure_message)

    def ensure_task_pending(self, account_id: int, task_type: str):
        """将指定任务收敛为 pending。"""
        with session_scope() as session:
            repos = RepositoryFactory(session)
            repos.task_instances().ensure_pending(
                account_id=account_id,
                task_type=task_type,
                reset_type=get_task_reset_type(task_type),
            )

    def mute_other_accounts(self, account_id: int):
        """将其他账号任务静默为 completed，避免干扰目标场景。"""
        now = datetime.now()
        statement = (
            update(TaskInstance)
            .where(TaskInstance.account_id != account_id)
            .values(
                status="completed",
                error_message=None,
                last_completed_at=now,
                schedule_anchor_at=now,
                next_run_at=now + timedelta(days=1),
                status_changed_at=now,
                updated_at=now,
            )
        )
        with session_scope() as session:
            session.exec(statement)

    def mute_other_tasks_for_account(self, account_id: int, keep_task_type: str):
        """将目标账号除 keep_task_type 外的任务静默为 completed。"""
        now = datetime.now()
        statement = (
            update(TaskInstance)
            .where(TaskInstance.account_id == account_id)
            .where(TaskInstance.task_type != keep_task_type)
            .values(
                status="completed",
                error_message=None,
                last_completed_at=now,
                schedule_anchor_at=now,
                next_run_at=now + timedelta(days=1),
                status_changed_at=now,
                updated_at=now,
            )
        )
        with session_scope() as session:
            session.exec(statement)

    def signal_worker(self, worker_pid: int, sig: int) -> bool:
        """向 worker 发送信号。"""
        if worker_pid <= 0:
            logger.error("signal_worker invalid pid=%s sig=%s", worker_pid, sig)
            self._trace_event("signal_worker_invalid_pid", worker_pid=worker_pid, sig=sig)
            return False
        try:
            os.kill(worker_pid, sig)
        except ProcessLookupError:
            logger.debug("signal_worker pid not found pid=%s sig=%s", worker_pid, sig)
            self._trace_event(
                "signal_worker_pid_not_found",
                worker_pid=worker_pid,
                sig=sig,
            )
            return False
        except PermissionError:
            logger.error("signal_worker permission denied pid=%s sig=%s", worker_pid, sig)
            self._trace_event(
                "signal_worker_permission_denied",
                worker_pid=worker_pid,
                sig=sig,
            )
            return False
        logger.info("signal_worker ok pid=%s sig=%s", worker_pid, sig)
        self._trace_event("signal_worker_ok", worker_pid=worker_pid, sig=sig)
        return True

    def collect_process_runtime_state(
        self,
        pid: int,
        *,
        patterns: Optional[list[str]] = None,
    ) -> dict[str, object]:
        """采集单个进程的内存摘要和命中库。"""
        if pid <= 0:
            raise RuntimeError(f"invalid pid: {pid}")
        vmmap_result = subprocess.run(
            ["vmmap", "-summary", str(pid)],
            check=True,
            capture_output=True,
            text=True,
        )
        lsof_result = subprocess.run(
            ["lsof", "-p", str(pid)],
            check=True,
            capture_output=True,
            text=True,
        )
        metrics = parse_vmmap_summary(vmmap_result.stdout)
        matched_libraries = extract_loaded_library_matches(
            lsof_result.stdout,
            patterns or [],
        )
        payload = {
            "pid": pid,
            **metrics,
            "matched_libraries": matched_libraries,
        }
        self._trace_event("process_runtime_state", **payload)
        return payload

    def collect_runtime_process_metrics(
        self,
        *,
        scheduler: Scheduler,
        worker_pid: int,
        patterns: Optional[list[str]] = None,
    ) -> dict[str, object]:
        """采集当前测试进程和设备 worker 进程的指标。"""
        payload = {
            "controller": self.collect_process_runtime_state(
                os.getpid(),
                patterns=patterns,
            ),
            "worker": self.collect_process_runtime_state(
                worker_pid,
                patterns=patterns,
            ),
            "recognition": None,
        }
        self._trace_event("runtime_process_metrics", **payload)
        return payload

    def snapshot_runtime(
        self,
        account_id: int,
        task_type: str,
        *,
        scheduler: Optional[Scheduler] = None,
    ) -> dict:
        """之前快照仍依赖已删除的 run lease 仓库。现在只读取当前调度模型真实存在的任务和设备状态。这样实机场景不会再因为 archive 残留接口直接失败。"""
        with session_scope() as session:
            repos = RepositoryFactory(session)
            task = repos.task_instances().get_by_account_and_type(account_id, task_type)
            task_payload = {
                "task_id": task.id if task else None,
                "task_status": task.status if task else None,
                "task_owner_run_id": getattr(task, "owner_run_id", None)
                if task
                else None,
                "task_error_message": task.error_message if task else None,
                "active_lease_status": None,
                "latest_lease_status": None,
                "active_worker_pid": None,
                "latest_lease_run_id": None,
            }

        if scheduler is not None:
            device_summary = scheduler.device_pool.get_status_summary()
            runtime_supervisor = getattr(scheduler, "runtime_supervisor", None)
            if runtime_supervisor is None:
                runtime_supervisor = getattr(scheduler, "_runtime_supervisor", None)
            if runtime_supervisor is not None:
                active_accounts = list(runtime_supervisor.active_run_account_ids())
            else:
                active_accounts = scheduler._snapshot_active_account_ids()
            active_in_scheduler = account_id in active_accounts
            get_device_phase = getattr(runtime_supervisor, "get_device_phase", None)
            if callable(get_device_phase) and self.device_addresses:
                device_process_phase = get_device_phase(self.device_addresses[0])
            else:
                device_process_phase = None
        else:
            device_summary = None
            active_in_scheduler = False
            device_process_phase = None

        snapshot = {
            **task_payload,
            "active_in_scheduler": active_in_scheduler,
            "captured_at": datetime.now().isoformat(),
            "device_summary": device_summary,
            "device_process_phase": device_process_phase,
        }
        logger.debug(
            "snapshot account=%s task=%s status=%s active_in_scheduler=%s",
            account_id,
            task_type,
            snapshot["task_status"],
            snapshot["active_in_scheduler"],
        )
        key = (account_id, task_type)
        signature = (
            snapshot["task_status"],
            snapshot["active_in_scheduler"],
            snapshot["active_lease_status"],
            snapshot["device_process_phase"],
        )
        previous = self._snapshot_signatures.get(key)
        if self._trace_snapshot_mode == "all" or previous != signature:
            self._trace_event(
                "snapshot",
                account_id=account_id,
                task_type=task_type,
                task_status=snapshot["task_status"],
                active_in_scheduler=snapshot["active_in_scheduler"],
                active_lease_status=snapshot["active_lease_status"],
                latest_lease_status=snapshot["latest_lease_status"],
                active_worker_pid=snapshot["active_worker_pid"],
                latest_lease_run_id=snapshot["latest_lease_run_id"],
                device_process_phase=snapshot["device_process_phase"],
            )
            self._snapshot_signatures[key] = signature
        return snapshot
