#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
账号信息获取任务测试脚本

测试 FetchAccountInfoTask 的核心功能：
1. 从主页进入个人资料页
2. OCR 获取 friend_id 和 nickname
3. 更新数据库

使用方式:
    python tests/test_fetch_account_info.py                    # 自动发现设备
    python tests/test_fetch_account_info.py -d 127.0.0.1:5555  # 指定设备
"""

import argparse
import logging
import sys
from pathlib import Path

# 添加 src 目录到 Python 路径
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.ocr import OcrEngine
from ptcgp_auto_v2.infra.template import TemplateMatcher
from ptcgp_auto_v2.infra.page_detector import PageDetector
from ptcgp_auto_v2.infra.account_syncer import AccountSyncer
from ptcgp_auto_v2.utils.device_discovery import discover_devices
from ptcgp_auto_v2.db.connection import get_database
from ptcgp_auto_v2.tasks.fetch_account_info import FetchAccountInfoTask

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
        "--max-turns",
        type=int,
        default=10,
        help="最大执行轮数（默认 10）",
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

    # 连接设备
    print(f"\n连接设备: {device_address}")
    adb = AdbController(device_address)
    if not adb.connect():
        print("错误: 无法连接设备")
        return 1

    try:
        # 初始化组件
        ocr = OcrEngine()
        template_matcher = TemplateMatcher()
        page_detector = PageDetector(adb, ocr, template_matcher)

        # 获取当前账号
        syncer = AccountSyncer(adb)
        account = syncer.get_current_account()
        if not account:
            print("错误: 无法获取当前账号")
            return 1

        print(f"\n当前账号: {account.nickname or account.game_id}")
        print(f"  friend_id: {account.friend_id or '(未知)'}")
        print(f"  nickname:  {account.nickname or '(未知)'}")

        # 创建任务
        task = FetchAccountInfoTask(
            adb=adb,
            recognizer=ocr,
            page_detector=page_detector,
        )
        task.bind_account(account)

        # 执行任务
        print("\n开始执行任务...")
        if not task.setup():
            print("错误: 任务初始化失败")
            return 1

        turn = 0
        while turn < args.max_turns:
            turn += 1
            print(f"\n--- 轮次 {turn} ---")

            # 检查是否完成
            result = task.check_completion()
            if result:
                msg = result.data.get("message", result.error or "完成")
                print(f"\n任务完成: {msg}")
                break

            # 截图并识别页面
            screenshot = adb.screenshot()
            if screenshot is None:
                print("警告: 截图失败")
                continue

            page_name, page_config = page_detector.detect(screenshot)
            ocr_results = page_detector.get_last_ocr_results()

            # 构建 page_info 字典
            # OCR 结果格式: {"text": str, "box": (x1, y1, x2, y2), "confidence": float}
            # 转换为 (text, (center_x, center_y)) 格式
            def box_to_center(box):
                """计算边界框中心点"""
                x1, y1, x2, y2 = box
                return ((x1 + x2) // 2, (y1 + y2) // 2)

            page_info = {
                "name": page_name,
                "config": page_config,
                "ocr_results": [(r.get("text", ""), box_to_center(r.get("box", (0, 0, 0, 0)))) for r in ocr_results],
            }

            print(f"页面: {page_name}")

            # 处理页面
            action_result = task.process_page(page_info)
            print(f"动作结果: should_wait={action_result.should_wait}s")

            # 等待
            if action_result.should_wait > 0:
                import time
                time.sleep(action_result.should_wait)

        # 清理
        task.cleanup()

        # 重新获取账号查看结果
        account = syncer.get_current_account()
        print(f"\n更新后账号信息:")
        print(f"  friend_id: {account.friend_id or '(未知)'}")
        print(f"  nickname:  {account.nickname or '(未知)'}")

        return 0

    finally:
        adb.disconnect()


if __name__ == "__main__":
    sys.exit(main())
