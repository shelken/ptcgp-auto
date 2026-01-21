#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号切换功能测试脚本

测试 AccountSwitcher 的核心功能：
1. Root 检测
2. 提取当前账号 XML
3. 注入账号 XML（切换账号）

使用方式:
    python tests/test_account_switcher.py                    # 自动发现设备
    python tests/test_account_switcher.py -d 127.0.0.1:5555  # 指定设备
    python tests/test_account_switcher.py --extract          # 仅提取 XML
    python tests/test_account_switcher.py --switch 1         # 切换到账号 ID=1
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.account_switcher import AccountSwitcher
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer
from ptcgp_auto_v2.utils.device_discovery import discover_devices
from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.db.repositories import AccountRepository

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def test_root_status(switcher: AccountSwitcher) -> bool:
    """测试 Root 状态检测"""
    print("\n" + "=" * 50)
    print("测试 1: Root 状态检测")
    print("=" * 50)

    is_rooted = switcher.is_rooted()
    print(f"设备 Root 状态: {'已 Root ✓' if is_rooted else '未 Root ✗'}")

    if not is_rooted:
        print("警告: 设备未 Root，账号切换功能将无法使用")
        return False

    return True


def test_extract_xml(switcher: AccountSwitcher, output_path: Path) -> bool:
    """测试提取账号 XML"""
    print("\n" + "=" * 50)
    print("测试 2: 提取账号 XML")
    print("=" * 50)

    success = switcher.extract_current_account_xml(output_path)
    if success:
        print(f"XML 提取成功: {output_path}")
        print(f"文件大小: {output_path.stat().st_size} 字节")

        # 显示 XML 内容摘要
        content = output_path.read_text()
        print(f"内容预览: {content[:200]}...")
    else:
        print("XML 提取失败")

    return success


def test_get_hash(switcher: AccountSwitcher) -> bool:
    """测试获取账号 XML 哈希"""
    print("\n" + "=" * 50)
    print("测试 3: 获取账号 XML 哈希")
    print("=" * 50)

    hash_value = switcher.get_current_account_hash()
    if hash_value:
        print(f"当前账号 XML 哈希: {hash_value}")
        return True
    else:
        print("无法获取哈希（可能设备未 Root 或无账号登录）")
        return False


def test_account_syncer(adb: AdbController) -> bool:
    """测试 AccountSyncer 获取当前账号"""
    print("\n" + "=" * 50)
    print("测试 4: AccountSyncer 获取当前账号")
    print("=" * 50)

    syncer = AccountSyncer(adb)
    account = syncer.get_current_account()

    if account:
        print("当前账号信息:")
        print(f"  ID:         {account.id}")
        print(f"  游戏 ID:    {account.game_id}")
        print(f"  朋友 ID:    {account.friend_id or '(未知)'}")
        print(f"  昵称:       {account.nickname or '(未设置)'}")
        print(f"  国家/地区:  {account.country or '(未知)'}")
        print(f"  XML 已保存: {'是' if account.xml_content else '否'}")
        return True
    else:
        print("无法获取当前账号")
        return False


def test_switch_account(switcher: AccountSwitcher, account_id: int) -> bool:
    """测试切换到指定账号"""
    print("\n" + "=" * 50)
    print(f"测试 5: 切换到账号 ID={account_id}")
    print("=" * 50)

    # 初始化数据库并获取账号
    get_database()
    repo = AccountRepository()
    account = repo.get_by_id(account_id)

    if not account:
        print(f"错误: 找不到 ID={account_id} 的账号")
        return False

    print(f"目标账号: {account.nickname or account.game_id}")

    if not account.xml_content:
        print("错误: 账号没有保存 XML 内容，无法切换")
        return False

    print(f"XML 内容大小: {len(account.xml_content)} 字节")

    # 执行切换
    print("正在切换账号...")
    success = switcher.switch_to(account, restart_app=True)

    if success:
        print("账号切换成功 ✓")
        print("游戏应用已重启，请检查是否切换到目标账号")
    else:
        print("账号切换失败 ✗")

    return success


def list_accounts():
    """列出所有可用账号"""
    print("\n" + "=" * 50)
    print("数据库中的账号列表")
    print("=" * 50)

    get_database()
    repo = AccountRepository()
    accounts = repo.get_all()

    if not accounts:
        print("没有找到任何账号")
        return

    print(f"{'ID':<6} {'昵称':<15} {'游戏ID':<20} {'有XML':<6}")
    print("-" * 50)

    for account in accounts:
        has_xml = "是" if account.xml_content else "否"
        nickname = account.nickname or "(未设置)"
        game_id = account.game_id[:18] + ".." if len(account.game_id) > 20 else account.game_id
        print(f"{account.id:<6} {nickname:<15} {game_id:<20} {has_xml:<6}")


def main():
    parser = argparse.ArgumentParser(description="账号切换功能测试")
    parser.add_argument(
        "-d", "--device",
        type=str,
        default=None,
        help="ADB 设备地址（默认自动发现）",
    )
    parser.add_argument(
        "--extract",
        action="store_true",
        help="仅测试提取 XML",
    )
    parser.add_argument(
        "--switch",
        type=int,
        default=None,
        help="切换到指定账号 ID",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="列出所有账号",
    )
    args = parser.parse_args()

    # 列出账号
    if args.list:
        list_accounts()
        return 0

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

    # 连接设备
    print(f"\n连接设备: {device_address}")
    adb = AdbController(device_address)
    if not adb.connect():
        print("错误: 无法连接设备")
        return 1

    try:
        switcher = AccountSwitcher(adb)

        # 测试 Root 状态
        if not test_root_status(switcher):
            print("\n设备未 Root，无法继续测试")
            return 1

        # 仅提取 XML
        if args.extract:
            output_path = Path(f"/tmp/ptcgp_account_test.xml")
            test_extract_xml(switcher, output_path)
            return 0

        # 切换账号
        if args.switch:
            test_switch_account(switcher, args.switch)
            return 0

        # 完整测试流程
        print("\n运行完整测试流程...")

        # 测试提取 XML
        output_path = Path(f"/tmp/ptcgp_account_test.xml")
        test_extract_xml(switcher, output_path)

        # 测试获取哈希
        test_get_hash(switcher)

        # 测试 AccountSyncer
        test_account_syncer(adb)

        print("\n" + "=" * 50)
        print("测试完成")
        print("=" * 50)
        print("\n提示: 使用 --switch <账号ID> 测试账号切换")
        print("      使用 --list 查看可用账号")

        return 0

    finally:
        adb.disconnect()


if __name__ == "__main__":
    sys.exit(main())
