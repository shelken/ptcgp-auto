---
name: test-tasks
description: Use when 需要本地直连 BlueStacks 模拟器测试任务、确认 ADB 端口可用并执行任务调试时。
---

## 概述

目标：使用 CLI 启动并连接 BlueStacks（仅 auto- 实例），保证 data 目录存在，然后后台运行指定任务并非阻塞查看日志。

## 流程（唯一入口）

1. 获取实例名与端口（仅 auto-）

   ```bash
   rg '^bst\.instance\.[^.]+\.adb_port' "/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf"
   rg '^bst\.instance\.[^.]+\.display_name="auto-' "/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf"
   ```

2. 启动实例（后台）

   ```bash
   "/Applications/BlueStacks.app/Contents/MacOS/BlueStacks" --instance <实例名> >/dev/null 2>&1 &
   ```

3. 检查进程与端口

   ```bash
   pgrep -fl "BlueStacks.*--instance"
   lsof -n -P -iTCP:<端口> -sTCP:LISTEN
   ```

4. 连接 ADB 并确认设备

   ```bash
   adb connect 127.0.0.1:<端口>
   adb devices -l
   ```

5. 确保 data 目录存在

   ```bash
   cp -r ~/Code/MyRepo/ptcgp-auto/data ./
   ```

6. 后台执行任务并查看日志（非阻塞）

   ```bash
   python main_v2.py --debug -d <adb_port> --task <task_name> --account <id> >/tmp/ptcgp_task.log 2>&1 &
   tail -n 200 /tmp/ptcgp_task.log
   ```

   示例：

   ```bash
   python main_v2.py --debug -d 5575 --task fetch_account_info --account 195 >/tmp/ptcgp_task.log 2>&1 &
   tail -n 200 /tmp/ptcgp_task.log
   ```

7. 参数说明

   `-d` 表示 ADB 端口，`--task` 表示具体任务名。
