# -*- coding: utf-8 -*-
"""send_card_daily/exchange_cards 选卡扫描只读 device E2E 场景。

场景只验证真实设备链路、页面识别与共享选卡扫描状态 helper。
不执行送卡/交换任务循环，不点击送出、交换、确认等不可逆按钮。
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import queue
import subprocess
import time
import traceback
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import uiautomator2 as u2

from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.infra.adb import AdbController, ScreenshotMode
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.tasks.exchange_cards import ExchangeCardsTask
from ptcgp_auto_v2.tasks.send_card_daily import SendCardDailyTask
from ptcgp_auto_v2.tasks.utils.friend_card_flow import (
    CardScanScrollState,
    advance_card_scan_scroll_state,
    build_ocr_signature,
)
from ptcgp_auto_v2.tests.e2e.harness import E2E_DB_PATH_ENV, rebind_test_runtime

_OUTPUT_LIMIT = 1200


class ReadonlyProbeFailure(AssertionError):
    """只读探针步骤失败。"""


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
    raise ReadonlyProbeFailure(
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
    # 变更原因：spawn 子进程不会继承父进程 settings，必须重绑测试 DB，避免 probe 读取生产配置。
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
    except Exception as exc:  # noqa: BLE001 - 进程边界需要返回完整异常文本，便于定位卡点。
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


def _probe_uiautomator2(addr: str) -> dict[str, Any]:
    info = u2.connect(addr).info
    if not isinstance(info, dict) or not info:
        raise RuntimeError(f"uiautomator2 info invalid: {type(info).__name__}")
    return {
        "displayWidth": info.get("displayWidth"),
        "displayHeight": info.get("displayHeight"),
        "screenOn": info.get("screenOn"),
    }


def _wait_for_known_app_page(
    controller: AdbController,
    detector: PageDetector,
    expected_package: str,
    timeout_seconds: int,
) -> tuple[str, dict[str, Any]]:
    deadline = time.monotonic() + timeout_seconds
    last_package = ""
    last_signature = ""
    while time.monotonic() < deadline:
        current_app = controller._require_device().app_current()
        last_package = str(current_app.get("package", ""))
        if last_package != expected_package:
            time.sleep(1.0)
            continue

        page_name, page_info = detector.detect(
            ocr_mode=ScreenshotMode.DISPLAY_RAW,
            template_mode=ScreenshotMode.DISPLAY_RAW,
        )
        _, ocr_results = detector.get_last_page_context()
        last_signature = build_ocr_signature(ocr_results)
        if page_name != "unknown" and ocr_results:
            return page_name, page_info
        time.sleep(1.0)

    raise RuntimeError(
        "PTCGP 页面识别失败: "
        f"package={last_package!r} expected={expected_package!r} "
        f"ocr_signature={last_signature!r}"
    )


def _probe_page_detect_and_scan_state(addr: str, page_detect_timeout: int) -> dict[str, Any]:
    controller = AdbController(addr)
    if not controller.connect():
        raise RuntimeError(f"AdbController.connect failed: {addr}")
    try:
        # 变更原因：只读 probe 的持久化日志不需要 raw OCR，避免本地排障日志带出服務ID等账号标识。
        logging.getLogger("ptcgp_auto_v2.infra.page_detector").setLevel(logging.INFO)
        settings = get_settings()
        # 变更原因：该场景只验证启动与页面识别边界，不进入送卡/交换页面循环，避免任何最终确认动作。
        controller.restart_app(settings.app_package, wait_time=1.0)
        ocr_engine = OcrEngine()
        template_matcher = TemplateMatcher()
        template_matcher.set_screen_width(controller.screen_width)
        detector = PageDetector(
            adb=controller,
            ocr_engine=ocr_engine,
            template_matcher=template_matcher,
        )
        detector.load_base_pages(COMMON_PAGES)
        detector.load_task_pages(SendCardDailyTask.pages + ExchangeCardsTask.pages)
        page_name, page_info = _wait_for_known_app_page(
            controller,
            detector,
            settings.app_package,
            page_detect_timeout,
        )
        screenshot, ocr_results = detector.get_last_page_context()
        if screenshot is None:
            raise RuntimeError("page detect did not capture screenshot")
        if not ocr_results:
            raise RuntimeError("page detect did not produce OCR results")

        # 变更原因：不可安全进入真实选卡页时，用当前真实设备截图/OCR证明页面链路，再用最小 recognizer 输出 seam 推进共享扫描状态；不触发滑动或点击。
        detected_cards = [SimpleNamespace(set_code="A1", card_number=153)]
        first_state, first_reached_limit = advance_card_scan_scroll_state(
            detected_cards,
            CardScanScrollState(),
            max_stable_rounds=2,
        )
        second_state, second_reached_limit = advance_card_scan_scroll_state(
            detected_cards,
            first_state,
            max_stable_rounds=2,
        )
        if first_state.last_signature != "A1:153":
            raise RuntimeError(f"unexpected first scan signature: {first_state}")
        if second_state.stable_rounds != 1:
            raise RuntimeError(f"scan stable rounds did not advance: {second_state}")
        if first_reached_limit or second_reached_limit:
            raise RuntimeError("scan state reached limit too early")

        empty_state, empty_reached_limit = advance_card_scan_scroll_state(
            [],
            CardScanScrollState(last_signature="__EMPTY__", stable_rounds=1),
            max_stable_rounds=2,
        )
        if empty_state.last_signature != "__EMPTY__" or not empty_reached_limit:
            raise RuntimeError(f"empty scan limit branch not covered: {empty_state}")

        ocr_signature = build_ocr_signature(ocr_results)
        return {
            "page_name": page_name,
            "matched_rule": page_info.get("name", ""),
            "ocr_count": len(ocr_results),
            "ocr_signature_len": len(ocr_signature),
            "screenshot": f"{screenshot.size[0]}x{screenshot.size[1]}",
            "scan_signature": second_state.last_signature,
            "stable_rounds": second_state.stable_rounds,
            "would_scroll_if_task_loop_continued": not second_reached_limit,
            "empty_scan_reached_limit": empty_reached_limit,
        }
    finally:
        controller.disconnect()


def run(ctx):
    """执行只读短链路探针，并断言共享扫描 helper 被真实调用。"""
    ctx.log(ctx.config.description)
    device_config = ctx.require_device_config()
    addr = device_config.device_address
    command_timeout = int(ctx.config.params["command_timeout_seconds"])
    page_detect_timeout = int(ctx.config.params["page_detect_timeout_seconds"])
    scan_probe_timeout = int(ctx.config.params["scan_probe_timeout_seconds"])

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

    page_result = _run_python_step(
        "page_detect_and_scan_state.readonly",
        page_detect_timeout + scan_probe_timeout,
        _probe_page_detect_and_scan_state,
        addr,
        page_detect_timeout,
    )
    if page_result["scan_signature"] != "A1:153":
        raise AssertionError(f"unexpected scan signature: {page_result}")
    if page_result["stable_rounds"] != 1:
        raise AssertionError(f"stable rounds not advanced: {page_result}")
    if page_result["would_scroll_if_task_loop_continued"] is not True:
        raise AssertionError(f"scroll decision not asserted: {page_result}")
    if page_result["empty_scan_reached_limit"] is not True:
        raise AssertionError(f"empty scan limit branch not asserted: {page_result}")
    ctx.log(f"page detect + shared scan helper OK: {page_result}")
    ctx.log("未覆盖：最终送卡确认、最终交换确认、真实选卡点击与提交。")
