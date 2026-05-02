# -*- coding: utf-8 -*-
"""E2E 测试共享 fixture。"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

import ptcgp_auto_v2.tasks  # noqa: F401
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.tests.e2e.harness import (
    E2E_APP_LOG_LEVEL_ENV,
    E2E_CONSOLE_LOG_LEVEL_ENV,
    E2E_DB_PATH_ENV,
    E2E_DEVICE_ENV,
    E2E_RAW_LOG_FILE_ENV,
    E2E_TRACE_FILE_ENV,
    E2E_TRACE_SNAPSHOT_MODE_ENV,
    SchedulerHarness,
    rebind_test_runtime,
)
from ptcgp_auto_v2.tests.e2e.scenario_loader import (
    DeviceRuntimeConfig,
    E2E_CASE_ENV,
    E2E_OVERRIDE_PREFIX,
    load_e2e_scenario,
    validate_e2e_env,
)

E2E_DEVICE_WORKER_MODE_ENV = "PTCGP_E2E_DEVICE_WORKER_MODE"
E2E_ACCOUNT_ID_ENV = "PTCGP_E2E_ACCOUNT_ID"
_RECORDED_E2E_LOG_ROOTS: set[str] = set()


def pytest_addoption(parser: pytest.Parser):
    """注册 E2E CLI 参数。"""
    group = parser.getgroup("ptcgp-e2e")
    group.addoption("--e2e-case", action="store", default=None)
    group.addoption("--e2e-device", action="store", default=None)
    group.addoption("--e2e-account-id", action="store", default=None)
    group.addoption("--e2e-device-worker-mode", action="store", default=None)
    group.addoption("--e2e-app-log-level", action="store", default=None)
    group.addoption("--e2e-console-log-level", action="store", default=None)
    group.addoption("--e2e-raw-log-file", action="store", default=None)
    group.addoption("--e2e-trace-file", action="store", default=None)
    group.addoption("--e2e-trace-snapshot-mode", action="store", default=None)
    group.addoption(
        "--e2e-override",
        action="append",
        default=[],
        help="支持重复传入 KEY=VALUE，例如 TASK_TYPE=claim_gifts",
    )


def _option_or_env(config: pytest.Config, option_name: str, env_name: str) -> str:
    value = config.getoption(option_name)
    if value is None:
        return os.getenv(env_name, "").strip()
    return str(value).strip()


def _build_runtime_env(config: pytest.Config) -> dict[str, str]:
    """构造 E2E 运行时环境（CLI 优先，环境变量兜底）。"""
    env = dict(os.environ)
    env[E2E_CASE_ENV] = _option_or_env(config, "e2e_case", E2E_CASE_ENV)
    env[E2E_DEVICE_ENV] = _option_or_env(config, "e2e_device", E2E_DEVICE_ENV)
    env[E2E_ACCOUNT_ID_ENV] = _option_or_env(config, "e2e_account_id", E2E_ACCOUNT_ID_ENV)
    env[E2E_DEVICE_WORKER_MODE_ENV] = _option_or_env(
        config,
        "e2e_device_worker_mode",
        E2E_DEVICE_WORKER_MODE_ENV,
    )
    env[E2E_APP_LOG_LEVEL_ENV] = _option_or_env(
        config,
        "e2e_app_log_level",
        E2E_APP_LOG_LEVEL_ENV,
    )
    env[E2E_CONSOLE_LOG_LEVEL_ENV] = _option_or_env(
        config,
        "e2e_console_log_level",
        E2E_CONSOLE_LOG_LEVEL_ENV,
    )
    env[E2E_RAW_LOG_FILE_ENV] = _option_or_env(
        config,
        "e2e_raw_log_file",
        E2E_RAW_LOG_FILE_ENV,
    )
    env[E2E_TRACE_FILE_ENV] = _option_or_env(
        config,
        "e2e_trace_file",
        E2E_TRACE_FILE_ENV,
    )
    env[E2E_TRACE_SNAPSHOT_MODE_ENV] = _option_or_env(
        config,
        "e2e_trace_snapshot_mode",
        E2E_TRACE_SNAPSHOT_MODE_ENV,
    )

    for raw_item in list(config.getoption("e2e_override") or []):
        item = str(raw_item).strip()
        if not item:
            continue
        if "=" not in item:
            raise pytest.UsageError(f"invalid --e2e-override: {item}")
        key, value = item.split("=", 1)
        normalized_key = key.strip().upper()
        if not normalized_key:
            raise pytest.UsageError(f"invalid --e2e-override key: {item}")
        env[f"{E2E_OVERRIDE_PREFIX}{normalized_key}"] = value.strip()

    return env


def _setup_temp_log_env(
    monkeypatch: pytest.MonkeyPatch,
    runtime_env: dict[str, str],
    profile: str,
    rootpath: Path,
):
    """把日志文件统一绑定到确定性目录，并记录路径。"""
    case_id = runtime_env.get(E2E_CASE_ENV, "").strip() or "all"
    log_dir = rootpath / ".e2e-logs" / case_id / profile
    log_dir.mkdir(parents=True, exist_ok=True)
    raw_log = runtime_env.get(E2E_RAW_LOG_FILE_ENV, "").strip()
    trace_log = runtime_env.get(E2E_TRACE_FILE_ENV, "").strip()

    raw_log_path = Path(raw_log) if raw_log else (log_dir / "app.log")
    trace_log_path = Path(trace_log) if trace_log else (log_dir / "trace.jsonl")
    raw_log_path.parent.mkdir(parents=True, exist_ok=True)
    trace_log_path.parent.mkdir(parents=True, exist_ok=True)
    raw_log_path.write_text("", encoding="utf-8")
    trace_log_path.write_text("", encoding="utf-8")

    app_log_level = runtime_env.get(E2E_APP_LOG_LEVEL_ENV, "").strip() or "TRACE"
    console_log_level = runtime_env.get(E2E_CONSOLE_LOG_LEVEL_ENV, "").strip() or "ERROR"
    snapshot_mode = runtime_env.get(E2E_TRACE_SNAPSHOT_MODE_ENV, "").strip() or "changes"
    monkeypatch.setenv(E2E_APP_LOG_LEVEL_ENV, app_log_level)
    monkeypatch.setenv(E2E_CONSOLE_LOG_LEVEL_ENV, console_log_level)
    monkeypatch.setenv(E2E_RAW_LOG_FILE_ENV, str(raw_log_path))
    monkeypatch.setenv(E2E_TRACE_FILE_ENV, str(trace_log_path))
    monkeypatch.setenv(E2E_TRACE_SNAPSHOT_MODE_ENV, snapshot_mode)
    _RECORDED_E2E_LOG_ROOTS.add(str(log_dir))


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter,
    exitstatus: int,
    config: pytest.Config,
):
    """测试结束后统一输出持久化日志文件路径。"""
    del exitstatus, config
    if not _RECORDED_E2E_LOG_ROOTS:
        return
    terminalreporter.section("ptcgp e2e logs", sep="=")
    for path in sorted(_RECORDED_E2E_LOG_ROOTS):
        terminalreporter.write_line(path)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]):
    """根据运行参数过滤单场景运行，并阻止非法 override 组合。"""
    runtime_env = _build_runtime_env(config)
    validate_e2e_env(runtime_env)
    selected_case_id = runtime_env.get(E2E_CASE_ENV, "").strip()
    if not selected_case_id:
        return
    try:
        load_e2e_scenario(selected_case_id, "core")
    except RuntimeError:
        try:
            load_e2e_scenario(selected_case_id, "device")
        except RuntimeError as exc:
            raise pytest.UsageError(str(exc)) from exc
    except KeyError as exc:
        raise pytest.UsageError(str(exc)) from exc

    selected_items: list[pytest.Item] = []
    deselected_items: list[pytest.Item] = []
    for item in items:
        callspec = getattr(item, "callspec", None)
        case_id = None if callspec is None else callspec.params.get("case_id")
        if case_id is None:
            deselected_items.append(item)
            continue
        if case_id == selected_case_id:
            selected_items.append(item)
            continue
        deselected_items.append(item)

    items[:] = selected_items
    if deselected_items:
        config.hook.pytest_deselected(items=deselected_items)


@pytest.fixture
def e2e_runtime_env(pytestconfig: pytest.Config) -> dict[str, str]:
    """E2E 运行参数（CLI 优先，环境变量兜底）。"""
    return _build_runtime_env(pytestconfig)


@pytest.fixture
def core_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
    e2e_runtime_env: dict[str, str],
) -> SchedulerHarness:
    """确定性 core profile 的测试框架。"""
    device_address = "127.0.0.1:29999"
    db_path = tmp_path / "core" / "ptcgp_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _setup_temp_log_env(
        monkeypatch,
        e2e_runtime_env,
        "core",
        pytestconfig.rootpath,
    )
    monkeypatch.setenv(E2E_DB_PATH_ENV, str(db_path))
    monkeypatch.setenv(E2E_DEVICE_ENV, device_address)
    monkeypatch.setenv(E2E_DEVICE_WORKER_MODE_ENV, "probe")
    monkeypatch.setenv("PTCGP_E2E_PROBE_BEHAVIOR", "complete")
    rebind_test_runtime(db_path, [device_address])

    harness = SchedulerHarness(db_path=db_path, device_addresses=[device_address])
    try:
        yield harness
    finally:
        harness.stop_scheduler()


@pytest.fixture
def device_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    pytestconfig: pytest.Config,
    e2e_runtime_env: dict[str, str],
) -> tuple[SchedulerHarness, DeviceRuntimeConfig]:
    """实机 device profile 的测试框架。"""
    device_address = e2e_runtime_env.get(E2E_DEVICE_ENV, "").strip()
    account_id_raw = e2e_runtime_env.get(E2E_ACCOUNT_ID_ENV, "").strip()
    if not device_address or not account_id_raw:
        pytest.skip("missing args/env: e2e_device or e2e_account_id")

    account_id = int(account_id_raw)
    worker_mode = (
        e2e_runtime_env.get(E2E_DEVICE_WORKER_MODE_ENV, "real").strip().lower()
    )
    if worker_mode not in {"real", "probe"}:
        raise RuntimeError(f"invalid PTCGP_E2E_DEVICE_WORKER_MODE: {worker_mode}")

    source_db = pytestconfig.rootpath / "data" / "ptcgp_v2.db"
    if not source_db.exists():
        pytest.skip(f"source db not found: {source_db}")

    db_path = tmp_path / "device" / "ptcgp_v2.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_db, db_path)

    _setup_temp_log_env(
        monkeypatch,
        e2e_runtime_env,
        "device",
        pytestconfig.rootpath,
    )
    monkeypatch.setenv(E2E_DB_PATH_ENV, str(db_path))
    monkeypatch.setenv(E2E_DEVICE_ENV, device_address)
    rebind_test_runtime(db_path, [device_address])

    with session_scope() as session:
        repos = RepositoryFactory(session)
        account = repos.accounts().get_by_id(account_id)
        if account is None:
            pytest.skip(f"account not found in cloned db: {account_id}")

    harness = SchedulerHarness(db_path=db_path, device_addresses=[device_address])
    config = DeviceRuntimeConfig(
        device_address=device_address,
        account_id=account_id,
        worker_mode=worker_mode,
    )
    try:
        yield harness, config
    finally:
        harness.stop_scheduler()
