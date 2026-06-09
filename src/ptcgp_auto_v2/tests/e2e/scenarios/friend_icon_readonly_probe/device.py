# -*- coding: utf-8 -*-
"""manage_friendship 好友图标只读 device probe。

这个场景只读取真实设备截图，并通过真实 AdbController、TemplateMatcher、PageDetector 跑好友状态图标 helper。场景不点击好友申请、删除、取消邀请、确认等社交动作；当前页面不是搜索结果页时，只证明真实截图/模板链路可运行，不判定业务状态。
"""

from __future__ import annotations

import multiprocessing
import queue
import subprocess
import time
import traceback
from typing import Any

import uiautomator2 as u2
from PIL import Image

from ptcgp_auto_v2.config.pages.common import COMMON_PAGES
from ptcgp_auto_v2.infra.adb import AdbController, ScreenshotMode
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.template import TemplateMatcher, TemplateMatch
from ptcgp_auto_v2.tasks.manage_friendship import ManageFriendshipTask
from ptcgp_auto_v2.tasks.utils.friend_status_icons import friend_status_by_icons

_OUTPUT_LIMIT = 1200


class ProbeStepFailure(AssertionError):
    """探针步骤失败。"""


class RecordingPageDetector(PageDetector):
    """记录 helper 的 scale 调用，同时继续走真实 PageDetector/TemplateMatcher。"""

    def __init__(
        self,
        adb: AdbController,
        ocr_engine: OcrEngine,
        template_matcher: TemplateMatcher,
        screenshot: Image.Image,
    ):
        super().__init__(adb, ocr_engine, template_matcher)
        self._probe_screenshot = screenshot
        self.scale_calls: list[tuple[str, float, float | None]] = []

    def find_template_with_scale(
        self,
        template_name: str,
        scale: float = 1.0,
        threshold: float | None = None,
        screenshot: Image.Image | None = None,
        lossless: bool | None = None,
        mode: ScreenshotMode | str | None = None,
    ) -> TemplateMatch | None:
        self.scale_calls.append((template_name, scale, threshold))
        return super().find_template_with_scale(
            template_name,
            scale=scale,
            threshold=threshold,
            screenshot=screenshot or self._probe_screenshot,
            lossless=lossless,
            mode=mode,
        )


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


def _run_adb_health(addr: str, timeout_seconds: int) -> dict[str, str]:
    return {
        "connect": _run_adb_command(
            "adb.connect", ["adb", "connect", addr], timeout_seconds
        ),
        "boot_completed": _run_adb_command(
            "adb.boot_completed",
            ["adb", "-s", addr, "shell", "getprop", "sys.boot_completed"],
            timeout_seconds,
        ),
        "echo": _run_adb_command(
            "adb.echo", ["adb", "-s", addr, "shell", "echo", "ok"], timeout_seconds
        ),
    }


def _process_entry(result_queue: multiprocessing.Queue, addr: str):
    try:
        result_queue.put({"ok": True, "result": _probe_friend_icons(addr)})
    except Exception as exc:  # noqa: BLE001 - 进程边界必须把异常转成可诊断文本。
        result_queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        )


def _run_probe_with_timeout(addr: str, timeout_seconds: int) -> dict[str, Any]:
    start = time.monotonic()
    ctx = multiprocessing.get_context("spawn")
    result_queue = ctx.Queue()
    process = ctx.Process(target=_process_entry, args=(result_queue, addr))
    process.start()
    process.join(timeout_seconds)
    elapsed = time.monotonic() - start
    if process.is_alive():
        process.terminate()
        process.join(2)
        if process.is_alive():
            process.kill()
            process.join(2)
        _fail_step("friend_icon.probe", elapsed, detail=f"timeout>{timeout_seconds}s")

    try:
        payload = result_queue.get_nowait()
    except queue.Empty:
        _fail_step(
            "friend_icon.probe",
            elapsed,
            detail=f"process_exitcode={process.exitcode} no_result",
        )

    if not payload["ok"]:
        _fail_step(
            "friend_icon.probe",
            elapsed,
            stdout=payload.get("traceback", ""),
            detail=payload["error"],
        )
    result = payload["result"]
    result["elapsed"] = round(elapsed, 2)
    return result


def _match_summary(match: TemplateMatch | None) -> dict[str, Any] | None:
    if match is None:
        return None
    return {
        "template": match.template_name,
        "box": match.box,
        "confidence": round(float(match.confidence), 4),
    }


def _assert_icon_semantics_not_mixed(status) -> dict[str, bool]:
    pending_reply = status.green_1x is not None and status.red_1x is not None
    already_friend = status.green_08 is not None
    has_green = status.green_1x is not None or status.green_08 is not None
    has_red = status.red_1x is not None or status.red_08 is not None
    friend_confirmed = has_green and not has_red
    green_and_red = has_green and has_red

    if status.is_pending_reply != pending_reply:
        raise AssertionError("1.0 待回复语义被混淆")
    if status.is_already_friend != already_friend:
        raise AssertionError("0.8 已是好友语义被混淆")
    if status.is_friend_confirmed != friend_confirmed:
        raise AssertionError("绿色勾确认语义被红叉混淆")
    if status.has_green_and_red != green_and_red:
        raise AssertionError("绿色勾/红叉组合语义被混淆")

    return {
        "pending_reply": pending_reply,
        "already_friend": already_friend,
        "friend_confirmed": friend_confirmed,
        "has_green_and_red": green_and_red,
    }


def _probe_friend_icons(addr: str) -> dict[str, Any]:
    info = u2.connect(addr).info
    if not isinstance(info, dict) or not info:
        raise RuntimeError(f"uiautomator2 info invalid: {type(info).__name__}")

    controller = AdbController(addr)
    try:
        # 变更原因：只读 probe 已先做 ADB/u2 健康检查，这里避免触发 AdbController.connect 的重启兜底。
        controller.device = u2.connect(addr)
        controller._update_screen_size()
        screenshot = controller.screenshot(mode=ScreenshotMode.DISPLAY_RAW)
        if screenshot is None:
            raise RuntimeError("AdbController.screenshot returned None")

        template_matcher = TemplateMatcher()
        template_matcher.set_screen_width(controller.screen_width)
        detector = RecordingPageDetector(
            controller,
            OcrEngine(),
            template_matcher,
            screenshot,
        )
        detector.load_base_pages(COMMON_PAGES)
        detector.load_task_pages(ManageFriendshipTask.pages)

        status = friend_status_by_icons(detector)
        expected_calls = [
            ("icon_green_yes", 1.0, 0.8),
            ("icon_red_no", 1.0, 0.8),
            ("icon_green_yes", 0.8, 0.8),
            ("icon_red_no", 0.8, 0.8),
        ]
        if detector.scale_calls != expected_calls:
            raise AssertionError(f"unexpected scale calls: {detector.scale_calls}")
        semantics = _assert_icon_semantics_not_mixed(status)

        page_name, page_info = detector.detect(
            screenshot=screenshot,
            ocr_mode=ScreenshotMode.DISPLAY_RAW,
            template_mode=ScreenshotMode.DISPLAY_RAW,
        )
        return {
            "u2": {
                "displayWidth": info.get("displayWidth"),
                "displayHeight": info.get("displayHeight"),
                "screenOn": info.get("screenOn"),
            },
            "screenshot": f"{screenshot.size[0]}x{screenshot.size[1]}",
            "page_name": page_name,
            "ocr_count": len(page_info.get("ocr_results", [])),
            "is_friend_search_result": page_name == "friend_search_result_popup",
            "scale_calls": detector.scale_calls,
            "matches": {
                "green_1x": _match_summary(status.green_1x),
                "red_1x": _match_summary(status.red_1x),
                "green_08": _match_summary(status.green_08),
                "red_08": _match_summary(status.red_08),
            },
            "semantics": semantics,
        }
    finally:
        controller.disconnect()


def run(ctx):
    """执行只读好友图标探针：健康检查、截图、1.0/0.8 模板 helper、页面识别。"""
    ctx.log(ctx.config.description)
    device_config = ctx.require_device_config()
    addr = device_config.device_address
    adb_timeout = int(ctx.config.params["adb_timeout_seconds"])
    probe_timeout = int(ctx.config.params["probe_timeout_seconds"])

    adb_result = _run_adb_health(addr, adb_timeout)
    boot_completed = adb_result["boot_completed"].replace("\\r", "").replace("\\n", "").strip()
    echo = adb_result["echo"].replace("\\r", "").replace("\\n", "").strip()
    if boot_completed != "1":
        _fail_step(
            "adb.boot_completed",
            0,
            stdout=adb_result["boot_completed"],
            detail="expected 1",
        )
    if echo != "ok":
        _fail_step("adb.echo", 0, stdout=adb_result["echo"], detail="expected ok")
    ctx.log(f"ADB health OK: echo={adb_result['echo']!r}")

    probe_result = _run_probe_with_timeout(addr, probe_timeout)
    ctx.log(f"friend icon readonly probe OK: {probe_result}")
    if not probe_result["is_friend_search_result"]:
        ctx.log(
            "当前页面不是好友搜索结果页：不判定业务状态，只验证真实截图/模板链路"
        )
    else:
        ctx.log("当前页面是好友搜索结果页：仅输出只读图标命中状态，不执行任何好友动作")
