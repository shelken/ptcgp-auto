# -*- coding: utf-8 -*-
"""短实机链路探针场景。

这个场景不执行任务页面循环，只把完整 device E2E 的前置链路拆成短步骤：
ADB、uiautomator2、截图、executor prepare-only、页面识别一次。
"""

from __future__ import annotations

import multiprocessing
import os
import queue
import subprocess
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import uiautomator2 as u2

from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.core.device_pool import DevicePool
from ptcgp_auto_v2.core.executor import (
    AccountExecutor,
    ExecutorConfig,
    TaskInstanceSnapshot,
)
from ptcgp_auto_v2.core.task_base import TaskRegistry
from ptcgp_auto_v2.core.task_status import TaskStatus
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories.factory import RepositoryFactory
from ptcgp_auto_v2.infra.account_syncer import AccountSnapshot
from ptcgp_auto_v2.infra.adb import AdbController, ScreenshotMode
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.tasks.claim_rewards import ClaimRewardsTask
from ptcgp_auto_v2.tests.e2e.harness import E2E_DB_PATH_ENV, rebind_test_runtime

_OUTPUT_LIMIT = 1200


class ProbeStepFailure(AssertionError):
    """探针步骤失败。"""


def _truncate(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="replace")
    else:
        text = value
    text = text.replace("\r", "\\r").replace("\n", "\\n")
    if len(text) <= _OUTPUT_LIMIT:
        return text
    return f"{text[:_OUTPUT_LIMIT]}...<truncated>"


def _fail_step(
    step: str,
    elapsed: float,
    *,
    stdout: bytes | str | None = None,
    stderr: bytes | str | None = None,
    detail: str = "",
):
    raise ProbeStepFailure(
        f"step={step} elapsed={elapsed:.2f}s "
        f"stdout={_truncate(stdout)!r} stderr={_truncate(stderr)!r} detail={detail}"
    )


def _run_adb_command(step: str, command: list[str], timeout_seconds: int) -> str:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        _fail_step(
            step,
            time.monotonic() - start,
            stdout=exc.stdout,
            stderr=exc.stderr,
            detail=f"timeout>{timeout_seconds}s cmd={' '.join(command)}",
        )
    elapsed = time.monotonic() - start
    if completed.returncode != 0:
        _fail_step(
            step,
            elapsed,
            stdout=completed.stdout,
            stderr=completed.stderr,
            detail=f"returncode={completed.returncode} cmd={' '.join(command)}",
        )
    return _truncate(completed.stdout)


def _bind_child_runtime(addr: str):
    db_path = os.getenv(E2E_DB_PATH_ENV, "").strip()
    if not db_path:
        return
    # 变更原因：spawn 子进程不会继承父进程内存中的 settings 绑定，必须重新绑定测试 DB，避免 probe 误读生产库。
    rebind_test_runtime(Path(db_path), [addr])


def _process_entry(
    result_queue: multiprocessing.Queue,
    target: Callable[..., dict[str, Any]],
    args: tuple[Any, ...],
):
    try:
        if args and isinstance(args[0], str):
            _bind_child_runtime(args[0])
        result_queue.put({"ok": True, "result": target(*args)})
    except Exception as exc:  # noqa: BLE001 - 进程边界必须把原始异常转成可诊断文本。
        result_queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        )


def _run_python_step(
    step: str,
    timeout_seconds: int,
    target: Callable[..., dict[str, Any]],
    *args: Any,
) -> dict[str, Any]:
    start = time.monotonic()
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(target=_process_entry, args=(result_queue, target, args))
    process.start()
    process.join(timeout_seconds)
    elapsed = time.monotonic() - start
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        _fail_step(step, elapsed, detail=f"timeout>{timeout_seconds}s")

    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        _fail_step(step, elapsed, detail=f"process_exitcode={process.exitcode} no_result")

    if not payload["ok"]:
        _fail_step(
            step,
            elapsed,
            stdout=payload.get("traceback", ""),
            detail=payload["error"],
        )
    result = payload["result"]
    result["elapsed"] = round(elapsed, 2)
    return result


def _probe_uiautomator2(addr: str) -> dict[str, Any]:
    info = u2.connect(addr).info
    if not isinstance(info, dict) or not info:
        raise RuntimeError(f"uiautomator2 info invalid: {type(info).__name__}")
    return {
        "displayWidth": info.get("displayWidth"),
        "displayHeight": info.get("displayHeight"),
        "screenOn": info.get("screenOn"),
    }


def _probe_screencap_with_controller(addr: str) -> dict[str, Any]:
    controller = AdbController(addr)
    if not controller.connect():
        raise RuntimeError(f"AdbController.connect failed: {addr}")
    try:
        # 变更原因：claim_rewards 实机路径使用 DISPLAY_RAW，probe 必须覆盖同一截图链路，不能用默认 RPC_JPEG。
        image = controller.screenshot(mode=ScreenshotMode.DISPLAY_RAW)
        if image is None:
            raise RuntimeError("AdbController.screenshot returned None")
        width, height = image.size
        if width <= 0 or height <= 0:
            raise RuntimeError(f"invalid screenshot size: {image.size}")
        return {"width": width, "height": height}
    finally:
        controller.disconnect()


def _load_account_snapshot(account_id: int) -> AccountSnapshot:
    with session_scope() as session:
        account = RepositoryFactory(session).accounts().get_by_id(account_id)
        if account is None:
            raise RuntimeError(f"account not found: {account_id}")
        return AccountSnapshot.from_account(account)


def _build_probe_task(account_id: int, task_type: str) -> TaskInstanceSnapshot:
    now = datetime.now()
    return TaskInstanceSnapshot(
        id=-1,
        account_id=account_id,
        task_type=task_type,
        status=TaskStatus.PENDING.value,
        reset_type="manual",
        error_message=None,
        status_changed_at=now,
        last_completed_at=None,
        schedule_anchor_at=None,
        last_duration_seconds=None,
        next_run_at=None,
        created_at=now,
        updated_at=now,
    )


def _probe_prepare_only(addr: str, account_id: int, task_type: str) -> dict[str, Any]:
    account = _load_account_snapshot(account_id)
    pool = DevicePool([addr])
    device = pool.acquire()
    if device is None:
        raise RuntimeError(f"device acquire failed: {addr}")

    executor = AccountExecutor(
        device=device,
        account=account,
        task_instances=[_build_probe_task(account_id, task_type)],
        device_pool=pool,
        config=ExecutorConfig(recovery_delay=1.0),
    )
    try:
        # 变更原因：probe 只覆盖真实 prepare/account 确认边界，不进入任务页面循环，避免复现 360s 完整任务超时。
        prepared = executor._prepare_run()
        if not prepared:
            raise RuntimeError("AccountExecutor._prepare_run returned False")
        if executor._page_detector is None:
            raise RuntimeError("page detector not initialized")
        task_class = TaskRegistry.get(task_type)
        screenshot, ocr_results = executor._page_detector.capture(
            mode=task_class.screenshot_ocr_mode,
        )
        if screenshot is None:
            raise RuntimeError("prepare capture screenshot failed")
        width, height = screenshot.size
        return {
            "prepared": prepared,
            "device_account_id": device.current_account_id,
            "screenshot": f"{width}x{height}",
            "ocr_count": len(ocr_results),
            "pool_available": pool.available_count,
        }
    finally:
        executor._cleanup()


def _probe_page_detect_once(addr: str) -> dict[str, Any]:
    controller = AdbController(addr)
    if not controller.connect():
        raise RuntimeError(f"AdbController.connect failed: {addr}")
    try:
        ocr_engine = OcrEngine()
        template_matcher = TemplateMatcher()
        template_matcher.set_screen_width(controller.screen_width)
        detector = PageDetector(
            adb=controller,
            ocr_engine=ocr_engine,
            template_matcher=template_matcher,
        )
        detector.load_base_pages(COMMON_PAGES)
        detector.load_task_pages(ClaimRewardsTask.pages)
        # 变更原因：单次 detect 明确证明 OCR 与模板规则链路跑过，但不要求当前页面属于 claim_rewards 流程。
        page_name, page_info = detector.detect(
            ocr_mode=ClaimRewardsTask.screenshot_ocr_mode,
            template_mode=ClaimRewardsTask.screenshot_template_mode,
        )
        screenshot, ocr_results = detector.get_last_page_context()
        if screenshot is None:
            raise RuntimeError("page detect did not capture screenshot")
        return {
            "page_name": page_name,
            "matched_rule": page_info.get("name", ""),
            "ocr_count": len(ocr_results),
            "screenshot": f"{screenshot.size[0]}x{screenshot.size[1]}",
        }
    finally:
        controller.disconnect()


def _probe_adb_health(addr: str, timeout_seconds: int) -> dict[str, str]:
    return {
        "connect": _run_adb_command("adb.connect", ["adb", "connect", addr], timeout_seconds),
        "devices": _run_adb_command("adb.devices", ["adb", "devices", "-l"], timeout_seconds),
        "boot_completed": _run_adb_command(
            "adb.boot_completed",
            ["adb", "-s", addr, "shell", "getprop", "sys.boot_completed"],
            timeout_seconds,
        ),
        "echo": _run_adb_command(
            "adb.echo",
            ["adb", "-s", addr, "shell", "echo", "ok"],
            timeout_seconds,
        ),
    }


def run(ctx):
    """按顺序执行短设备探针并输出每一步结果。"""
    ctx.log(ctx.config.description)
    device_config = ctx.require_device_config()
    addr = device_config.device_address
    account_id = device_config.account_id
    command_timeout = int(ctx.config.params["command_timeout_seconds"])
    prepare_timeout = int(ctx.config.params["prepare_timeout_seconds"])
    page_detect_timeout = int(ctx.config.params["page_detect_timeout_seconds"])

    adb_result = _probe_adb_health(addr, command_timeout)
    boot_completed = adb_result["boot_completed"].replace("\\r", "").replace("\\n", "").strip()
    echo = adb_result["echo"].replace("\\r", "").replace("\\n", "").strip()
    if boot_completed != "1":
        _fail_step("adb.boot_completed", 0, stdout=adb_result["boot_completed"], detail="expected 1")
    if echo != "ok":
        _fail_step("adb.echo", 0, stdout=adb_result["echo"], detail="expected ok")
    ctx.log(f"ADB health OK: echo={adb_result['echo']!r}")

    u2_result = _run_python_step("uiautomator2.info", command_timeout, _probe_uiautomator2, addr)
    ctx.log(f"uiautomator2 health OK: {u2_result}")

    screencap_result = _run_python_step(
        "screencap.controller", command_timeout, _probe_screencap_with_controller, addr
    )
    ctx.log(f"screencap health OK: {screencap_result}")

    prepare_result = _run_python_step(
        "executor.prepare_only",
        prepare_timeout,
        _probe_prepare_only,
        addr,
        account_id,
        ctx.config.task_type,
    )
    ctx.log(f"executor prepare-only OK: {prepare_result}")

    page_result = _run_python_step(
        "page_detect.once", page_detect_timeout, _probe_page_detect_once, addr
    )
    ctx.log(f"page detect once OK: {page_result}")
