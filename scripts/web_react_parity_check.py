#!/usr/bin/env python3
"""React Web 功能等价性自动验收脚本。

输出：
- AUTORESEARCH_METRIC=<float> （越高越好）
- 详细检查结果（JSON）
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
WEB_FRONTEND = ROOT / "src/ptcgp_auto_v2/web/frontend"
PWCLI = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills/playwright/scripts/playwright_cli.sh"
BASE_URL = os.environ.get("PTCGP_WEB_BASE_URL", "http://127.0.0.1:8000")


@dataclass
class CheckResult:
    name: str
    ok: bool
    score: int
    detail: str


def run_cmd(
    cmd: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = 180,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """执行命令并返回 (返回码, 输出)。"""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout


def add_check(checks: list[CheckResult], name: str, ok: bool, score: int, detail: str) -> None:
    checks.append(CheckResult(name=name, ok=ok, score=score if ok else 0, detail=detail))


def http_json(path: str) -> tuple[bool, dict[str, Any] | None, str]:
    """请求 JSON 接口。"""
    url = f"{BASE_URL}{path}"
    try:
        with urlopen(url, timeout=10) as resp:  # noqa: S310
            code = getattr(resp, "status", 200)
            body = resp.read().decode("utf-8", errors="replace")
            if code != 200:
                return False, None, f"HTTP {code}"
            try:
                return True, json.loads(body), "ok"
            except json.JSONDecodeError:
                return False, None, "invalid_json"
    except URLError as exc:
        return False, None, str(exc)


def parse_playwright_json_output(output: str) -> dict[str, Any] | None:
    """从 playwright-cli 输出中解析 ### Result JSON。"""
    marker = "### Result"
    idx = output.find(marker)
    if idx < 0:
        return None

    body = output[idx + len(marker) :]
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    return None


def parse_console_error_count(output: str) -> int:
    """解析 console error 命令输出里的错误条数。"""
    match = re.search(r"Errors:\s*(\d+)", output)
    if match is None:
        log_match = re.search(r"\((\.playwright-cli/console-[^)]+\.log)\)", output)
        if log_match:
            log_path = ROOT / log_match.group(1)
            if log_path.exists():
                first_line = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
                if first_line:
                    line_match = re.search(r"Errors:\s*(\d+)", first_line[0])
                    if line_match:
                        return int(line_match.group(1))
        return 999
    return int(match.group(1))


def run_playwright_step(args: list[str], timeout: int = 120) -> tuple[bool, str]:
    """运行一次 playwright-cli。"""
    if PWCLI.exists():
        cmd = [str(PWCLI), *args]
    elif shutil.which("playwright-cli"):
        cmd = ["playwright-cli", *args]
    else:
        return False, f"PWCLI_NOT_FOUND:{PWCLI}"

    code, out = run_cmd(cmd, cwd=ROOT, timeout=timeout)
    return code == 0, out


def main() -> int:
    checks: list[CheckResult] = []

    # 1) 基础构建检查
    ruff_env = dict(os.environ)
    ruff_env["PYTHONPATH"] = "src"
    code, out = run_cmd(["uv", "run", "ruff", "check", "src/ptcgp_auto_v2/web"], cwd=ROOT, env=ruff_env)
    add_check(checks, "ruff_check", code == 0, 10, "ok" if code == 0 else out[-400:])

    code, out = run_cmd(["bun", "run", "--cwd", str(WEB_FRONTEND), "build"], cwd=ROOT, timeout=240)
    add_check(checks, "bun_build", code == 0, 10, "ok" if code == 0 else out[-600:])

    # 2) bootstrap API
    ok, payload, detail = http_json("/api/react/bootstrap?lang=zh_CN")
    bootstrap_ok = bool(
        ok
        and isinstance(payload, dict)
        and isinstance(payload.get("t"), dict)
        and isinstance(payload.get("options"), dict)
        and isinstance(payload.get("assets"), dict)
    )
    add_check(checks, "bootstrap_api", bootstrap_ok, 10, detail if not bootstrap_ok else "ok")

    # 3) Playwright 页面渲染与关键交互
    # 先重启会话，避免上一轮脏状态
    run_playwright_step(["close-all"])
    ok_open, out_open = run_playwright_step(["open", f"{BASE_URL}/#/records"], timeout=90)
    add_check(checks, "pw_open", ok_open, 10, "ok" if ok_open else out_open[-400:])

    route_scores = {
        "#/records": 8,
        "#/owned-cards": 8,
        "#/management/accounts": 8,
        "#/management/tasks": 8,
        "#/management/notifications": 8,
    }
    for route, score in route_scores.items():
        ok_goto, out_goto = run_playwright_step(["-s=default", "goto", f"{BASE_URL}/{route}"])
        if not ok_goto:
            add_check(checks, f"route_{route}_goto", False, score, out_goto[-300:])
            continue
        ok_console, out_console = run_playwright_step(["-s=default", "console", "error"])
        if not ok_console:
            add_check(checks, f"route_{route}_console", False, score, out_console[-300:])
            continue
        error_count = parse_console_error_count(out_console)
        add_check(checks, f"route_{route}_console", error_count == 0, score, f"errors={error_count}")

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/records');\n"
                "  await page.waitForTimeout(1200);\n"
                "  const count = await page.locator('.record-card-grid .record-card-tile button').count();\n"
                "  if (count > 0) { await page.locator('.record-card-grid .record-card-tile button').first().click(); }\n"
                "  await page.waitForTimeout(300);\n"
                "  const overlay = await page.locator('.dialog-overlay').count();\n"
                "  return { count, overlay };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        ok_preview = int(payload.get("count", 0)) > 0 and int(payload.get("overlay", 0)) > 0
        add_check(checks, "records_preview_modal", ok_preview, 15, json.dumps(payload, ensure_ascii=False))
    else:
        add_check(checks, "records_preview_modal", False, 15, out_run[-400:])

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/records');\n"
                "  await page.waitForTimeout(1200);\n"
                "  const overviewCount = await page.locator('.record-batch-overview-grid .record-batch-pack').count();\n"
                "  if (overviewCount === 0) {\n"
                "    return { overviewCount, switched: true, reason: 'no_batch_data' };\n"
                "  }\n"
                "  await page.locator('.record-batch-overview-grid .record-batch-pack').first().click();\n"
                "  await page.waitForTimeout(300);\n"
                "  const detailCount = await page.locator('.record-card-grid .record-card-tile').count();\n"
                "  const hasBack = await page.getByRole('button', { name: /overview|总览/i }).count();\n"
                "  return { overviewCount, detailCount, hasBack, switched: detailCount > 0 && hasBack > 0 };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        add_check(
            checks,
            "records_batch_toggle",
            bool(payload.get("switched", False)),
            12,
            json.dumps(payload, ensure_ascii=False),
        )
    else:
        add_check(checks, "records_batch_toggle", False, 12, out_run[-400:])

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/management/tasks');\n"
                "  await page.fill('input[list=\"task-account-options\"]', 'skn');\n"
                "  await page.waitForTimeout(1000);\n"
                "  const count = await page.$$eval('#task-account-options option', (nodes) => nodes.length);\n"
                "  return { count };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        ok_task_options = int(payload.get("count", 0)) > 0
        add_check(checks, "tasks_remote_account_options", ok_task_options, 15, json.dumps(payload, ensure_ascii=False))
    else:
        add_check(checks, "tasks_remote_account_options", False, 15, out_run[-400:])

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/owned-cards');\n"
                "  await page.waitForTimeout(1200);\n"
                "  const detailBtn = page.getByRole('button', { name: /detail|详情/i }).first();\n"
                "  if ((await detailBtn.count()) > 0) {\n"
                "    await detailBtn.click();\n"
                "  } else {\n"
                "    const cardButton = page.locator('.owned-grid .owned-card').first();\n"
                "    if ((await cardButton.count()) === 0) {\n"
                "      return { ok: false, reason: 'no_entry_button' };\n"
                "    }\n"
                "    await cardButton.click();\n"
                "  }\n"
                "  await page.waitForTimeout(500);\n"
                "  const rows = await page.locator('.dialog-card .grid-table tbody tr').count();\n"
                "  const copyButton = await page.getByRole('button', { name: /copy|复制/i }).count();\n"
                "  const pageSizeRaw = await page.evaluate(() => window.localStorage.getItem('ptcgp_owned_modal_page_size') || '0');\n"
                "  const pageSize = Number.parseInt(pageSizeRaw, 10);\n"
                "  return { ok: rows > 0 && copyButton > 0 && pageSize > 0, rows, copyButton, pageSize };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        add_check(
            checks,
            "owned_detail_adaptive_page_size",
            bool(payload.get("ok", False)),
            12,
            json.dumps(payload, ensure_ascii=False),
        )
    else:
        add_check(checks, "owned_detail_adaptive_page_size", False, 12, out_run[-400:])

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/management/notifications');\n"
                "  await page.waitForTimeout(1200);\n"
                "  const configCards = await page.locator('.form-grid .surface-card').count();\n"
                "  const rows = await page.locator('.grid-table tbody tr').count();\n"
                "  return { configCards, rows };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        ok_notifications = int(payload.get("configCards", 0)) > 0 and int(payload.get("rows", 0)) > 0
        add_check(checks, "notifications_render", ok_notifications, 16, json.dumps(payload, ensure_ascii=False))
    else:
        add_check(checks, "notifications_render", False, 16, out_run[-400:])

    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        js_path = Path(f.name)
        f.write(
            (
                "async (page) => {\n"
                f"  await page.goto('{BASE_URL}/#/management/notifications');\n"
                "  await page.waitForTimeout(1200);\n"
                "  const rareRows = await page.locator('.grid-table tbody tr').filter({ hasText: 'rare_card_obtained' }).count();\n"
                "  const thumbs = await page.locator('.notification-thumb').count();\n"
                "  const ok = rareRows === 0 ? true : thumbs > 0;\n"
                "  return { ok, rareRows, thumbs };\n"
                "}\n"
            )
        )
    ok_run, out_run = run_playwright_step(["-s=default", "run-code", js_path.read_text(encoding="utf-8")], timeout=150)
    js_path.unlink(missing_ok=True)
    if ok_run:
        payload = parse_playwright_json_output(out_run) or {}
        add_check(
            checks,
            "notifications_image_render",
            bool(payload.get("ok", False)),
            10,
            json.dumps(payload, ensure_ascii=False),
        )
    else:
        add_check(checks, "notifications_image_render", False, 10, out_run[-400:])

    metric = float(sum(item.score for item in checks))
    report = {
        "metric": metric,
        "checks": [item.__dict__ for item in checks],
        "passed": sum(1 for item in checks if item.ok),
        "total": len(checks),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"AUTORESEARCH_METRIC={metric:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
