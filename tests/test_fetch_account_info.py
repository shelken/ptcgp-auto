#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号信息获取任务测试脚本

复用 Scheduler.run_single_task 执行完整的任务流程。

使用方式:
    python tests/test_fetch_account_info.py                    # 自动发现设备
    python tests/test_fetch_account_info.py -d 127.0.0.1:5555  # 指定设备
    python tests/test_fetch_account_info.py -a 2               # 指定账号 ID
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.utils.device_discovery import discover_devices
from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.repositories import AccountRepository
from ptcgp_auto_v2.core.scheduler import Scheduler

# 导入 tasks 模块触发任务注册
import ptcgp_auto_v2.tasks  # noqa: F401

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="账号信息获取任务测试")
    parser.add_argument(
        "-d", "--device",
        type=str,
        default=None,
        help="ADB 设备地址（默认自动发现）",
    )
    parser.add_argument(
        "-a", "--account",
        type=int,
        default=None,
        help="账号 ID（默认使用设备当前账号）",
    )
    args = parser.parse_args()

    # 获取设备地址
    device_address = args.device
    if not device_address:
        devices = discover_devices()
        if devices:
            device_address = devices[0]
            print(f"自动发现设备: {device_address}")
        else:
            device_address = "127.0.0.1:5555"
            print(f"未发现设备，使用默认地址: {device_address}")

    # 初始化数据库
    get_database()

    # 获取账号 ID
    account_id = args.account
    if not account_id:
        # 获取第一个账号
        repo = AccountRepository()
        accounts = repo.get_all()
        if not accounts:
            print("错误: 数据库中没有账号")
            return 1
        account_id = accounts[0].id
        print(f"使用账号 ID: {account_id} ({accounts[0].nickname})")

    # 使用 Scheduler 执行任务
    scheduler = Scheduler([device_address])
    success = scheduler.run_single_task(
        device_address=device_address,
        account_id=account_id,
        task_type="fetch_account_info",
    )

    if success:
        print("\n任务执行成功")
        # 重新获取账号查看结果
        repo = AccountRepository()
        account = repo.get_by_id(account_id)
        if account:
            print(f"\n更新后账号信息:")
            print(f"  friend_id: {account.friend_id or '(未知)'}")
            print(f"  nickname:  {account.nickname or '(未知)'}")
            print(f"  level:     {account.level or '(未知)'}")
        return 0
    else:
        print("\n任务执行失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
