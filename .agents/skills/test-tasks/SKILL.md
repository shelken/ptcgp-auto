---
name: test-tasks
description: Use when 需要通过 BlueStacks auto- 实例做任务实机测试、验证 ADB 连接或查看任务实时日志时。
---

## 概述

目标：使用 CLI 启动并连接 BlueStacks（仅 auto- 实例），确认 ADB 可用后执行单任务实机测试。

## 硬规则

1. 仅使用 `display_name` 为 `auto-` 的 BlueStacks 实例。
2. 测试账号必须使用高 ID 账号，禁止默认使用低 ID 或主力账号。
3. Python 命令统一使用 `PYTHONPATH=src UV_CACHE_DIR=/tmp/uv-cache uv run python`。
4. 在当前执行器环境中，优先前台运行并直接看实时日志；不要默认假设后台重定向日志一定可用。

## 流程（唯一入口）

1. 获取 `auto-` 实例名与对应端口

   先找 `display_name="auto-"` 的实例名，再取同一实例名的 `adb_port`。

   ```bash
   rg '^bst\.instance\.[^.]+\.adb_port' "/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf"
   rg '^bst\.instance\.[^.]+\.display_name="auto-' "/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf"
   ```

2. 启动实例

   ```bash
   "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks" --instance <实例名> >/tmp/ptcgp_bluestacks.log 2>&1 &
   ```

3. 轮询进程与端口，直到实例真正就绪

   `BlueStacks` 刚启动时，进程、监听端口、ADB 握手不是同时完成。不要只检查一次。

   ```bash
   pgrep -fl "BlueStacks.*--instance|BlueStacks"
   lsof -n -P -iTCP:<端口> -sTCP:LISTEN
   ```

4. 连接 ADB，并轮询直到设备真正出现

   ```bash
   adb connect 127.0.0.1:<端口>
   adb devices -l
   ```

5. 确认测试账号是高 ID 账号

   执行前先确认账号存在，且使用当前库里靠后的测试账号。

   ```bash
   PYTHONPATH=src UV_CACHE_DIR=/tmp/uv-cache uv run python - <<'PY'
   from ptcgp_auto_v2.db.engine import session_scope
   from ptcgp_auto_v2.db.repositories import AccountRepository
   with session_scope() as session:
       account = AccountRepository(session).get_by_id(<high_account_id>)
       print('account-ok' if account else 'account-missing')
   PY
   ```

6. 确保 `data` 目录存在

   ```bash
   test -d data || cp -r ~/Code/active/ptcgp-auto/data ./
   ```

7. 执行任务并查看日志

   当前执行器环境优先前台运行，直接看实时日志：

   ```bash
   PYTHONPATH=src UV_CACHE_DIR=/tmp/uv-cache uv run python main_v2.py --debug -d <adb_port> --task <task_name> --account <high_account_id>
   ```

   如果是在本地终端里手工调试，确认后台子进程可稳定保留后，才使用后台日志方式：

   ```bash
   : > /tmp/ptcgp_task.log
   PYTHONPATH=src UV_CACHE_DIR=/tmp/uv-cache uv run python main_v2.py --debug -d <adb_port> --task <task_name> --account <high_account_id> >/tmp/ptcgp_task.log 2>&1 &
   tail -n 200 /tmp/ptcgp_task.log
   ```

8. 参数说明

   `-d` 表示 ADB 端口，`--task` 表示具体任务名，`UV_CACHE_DIR=/tmp/uv-cache` 用于固定 `uv` 缓存目录。
