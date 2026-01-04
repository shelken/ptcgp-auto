"""
PTCGP 单人对战自动化脚本 - 主入口
"""

import argparse
import time
import sys

import config
from utils import get_data_dir
from adb_controller import AdbController
from recognizer import get_recognizer
from state_manager import get_state_manager
from page_detector import PageDetector
from actions import ActionHandler


class PTCGPAuto:
    """PTCGP 单人对战自动化 - 状态机版本"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.ADB_HOST
        self.port = port or config.ADB_PORT
        self.adb = AdbController(host, port)
        self.recognizer = get_recognizer()
        # 使用统一的数据目录
        data_dir = get_data_dir(self.port)
        state_file = str(data_dir / "state.json")
        self.state = get_state_manager(state_file)
        self.page_detector = PageDetector(self.recognizer)
        self.action_handler = ActionHandler(self.adb, self.recognizer, self.state)
        self.running = True

    def start(self):
        """启动自动化"""
        print("=" * 50)
        print("PTCGP 单人对战自动化脚本")
        print("=" * 50)

        # 连接 ADB
        if not self.adb.connect():
            print("无法连接到模拟器，请检查 ADB 配置")
            return False

        print("\n开始自动化流程...")
        print("提示: 脚本会自动识别当前界面并执行相应操作")

        # 显示当前进度
        self.state.print_status()

        try:
            self.main_loop()
        except KeyboardInterrupt:
            print("\n用户中断，退出...")
        except Exception as e:
            print(f"\n发生错误: {e}")
            if config.DEBUG:
                import traceback
                traceback.print_exc()
        finally:
            self.state.save()
            self.adb.disconnect()

        return True

    def main_loop(self):
        """主循环 - 状态机"""
        no_action_count = 0

        while self.running:
            # 截图
            screenshot = self.adb.screenshot()
            if not screenshot:
                print("截图失败，等待重试...")
                time.sleep(1)
                continue

            # 识别当前界面
            page_name, page_info, match_info = self.page_detector.detect(screenshot)

            if page_name:
                no_action_count = 0
                print(f"\n[界面] {page_name}")

                # 执行对应动作
                action = page_info.get("action", "unknown")
                # 把 page_info 传给动作，让动作能访问配置（如 action_template）
                match_info["page_info"] = page_info
                self.action_handler.execute(action, screenshot, match_info)

                # 等待页面切换
                time.sleep(config.WAIT_PAGE_TRANSITION)
            else:
                no_action_count += 1
                if no_action_count >= 5:
                    print("连续多次无法识别界面，可能需要手动干预")
                    no_action_count = 0
                time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(description='PTCGP 单人对战自动化脚本')
    parser.add_argument(
        '-a', '--address',
        type=str,
        default=None,
        help='ADB 连接地址，格式: host:port 或 port (默认: 127.0.0.1:5555)'
    )
    parser.add_argument(
        '-l', '--language',
        type=str,
        choices=['zh_Hant', 'en_US'],
        default=None,
        help='界面语言 (默认: zh_Hant)'
    )
    parser.add_argument(
        '--no-auto-battle-in-battle',
        action='store_true',
        help='禁用对战中自动开启自动对战（允许人工接管）'
    )
    args = parser.parse_args()

    # 加载语言配置
    if args.language:
        config.load_language(args.language)
        print(f"语言设置: {args.language}")

    # 设置自动对战开关
    if args.no_auto_battle_in_battle:
        config.AUTO_ENABLE_AUTO_BATTLE = False
        print("对战中自动开启自动对战: 禁用")

    # 解析地址
    host = None
    port = None
    if args.address:
        if ':' in args.address:
            parts = args.address.split(':')
            host = parts[0]
            port = int(parts[1])
        else:
            # 只有端口号
            port = int(args.address)

    auto = PTCGPAuto(host, port)
    auto.start()


if __name__ == "__main__":
    main()
