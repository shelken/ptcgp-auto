"""
PTCGP 单人对战自动化脚本 - 主入口
"""

import time

import config
from utils import get_data_dir
from adb_controller import AdbController
from recognizer import get_recognizer
from state_manager import get_state_manager
from page_detector import PageDetector
from actions import ActionHandler
from notifier import notify_unrecognized
from settings import load_settings, apply_settings_to_config, print_active_settings


class PTCGPAuto:
    """PTCGP 单人对战自动化 - 状态机版本"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.ADB_HOST
        self.port = port or config.ADB_PORT
        self.adb = AdbController(self.host, self.port)
        self.recognizer = get_recognizer()
        # 使用统一的数据目录
        data_dir = get_data_dir(self.port)
        state_file = str(data_dir / "state.json")
        self.state = get_state_manager(state_file)
        self.page_detector = PageDetector(self.recognizer)
        self.action_handler = ActionHandler(self.adb, self.recognizer, self.state)
        self.running = True
        self.unrecognized_notified = False  # Notification state flag

    def start(self, tutorial_mode=False):
        """启动自动化

        Args:
            tutorial_mode: 是否直接进入教程解锁模式
        """
        print("=" * 50)
        print("PTCGP 单人对战自动化脚本")
        print("=" * 50)

        # 连接 ADB
        if not self.adb.connect():
            print("无法连接到模拟器，请检查 ADB 配置")
            return False

        # 连接后重新加载模板（根据实际分辨率缩放）
        self.recognizer.reload_templates()

        print("\n开始自动化流程...")

        try:
            if tutorial_mode:
                # 先进入教程模式
                print("提示: 教程解锁模式")
                from actions.tutorial import TutorialRunner
                runner = TutorialRunner(self.adb, self.recognizer)
                runner.run()
                print("教程完成，进入正常对战流程...")

            # 正常主循环
            print("提示: 脚本会自动识别当前界面并执行相应操作")
            self.state.print_status()
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
                self.unrecognized_notified = False  # Reset notification state
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
                    # Send notification only once per unrecognized state
                    if not self.unrecognized_notified and config.NOTIFICATION_ENABLED:
                        notify_unrecognized(
                            config.NOTIFICATION_WEBHOOK_KEY,
                            config.NOTIFICATION_SOUND
                        )
                        self.unrecognized_notified = True
                    no_action_count = 0
                time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)


def main():
    """主入口"""
    # 加载配置（CLI > 环境变量 > .env > 默认值）
    settings = load_settings()

    # 应用配置到 config 模块
    apply_settings_to_config(settings)

    # 打印非默认配置
    print_active_settings(settings)

    # 解析地址
    host = config.ADB_HOST
    port = config.ADB_PORT

    auto = PTCGPAuto(host, port)
    auto.start(tutorial_mode=settings.get("tutorial", False))


if __name__ == "__main__":
    main()
