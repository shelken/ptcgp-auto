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

    def fetch_user_info(self):
        """获取用户信息子流程 - 独立于主循环"""
        print("正在获取用户信息...")

        while not self.state.has_user_info():
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            page_name, page_info, match_info = self.page_detector.detect(screenshot)

            if not page_name:
                time.sleep(1)
                continue

            print(f"  [{page_name}]")

            # 已到达目标页面，执行提取
            if page_name == "user_info_popup":
                match_info["page_info"] = page_info
                self.action_handler.execute("extract_user_info", screenshot, match_info)
                break

            # 导航到目标的步骤
            if page_name == "friends_list":
                match_info["page_info"] = page_info
                self.action_handler.execute("click_add_friends", screenshot, match_info)
            elif page_name == "community_page":
                match_info["page_info"] = page_info
                self.action_handler.execute("click_friends_tab", screenshot, match_info)
            elif page_name == "game_home_main":
                # 点击社群图标
                box = self.recognizer.find_template(screenshot, "icon_community", threshold=0.7)
                if box:
                    print("  -> 点击社群图标")
                    self.adb.tap_center(box)
            elif page_name in ("_main_page", "game_open_page"):
                # 模拟器主页或游戏开启页面，执行默认动作进入游戏
                match_info["page_info"] = page_info
                self.action_handler.execute("click_identifier", screenshot, match_info)
            else:
                # 其他页面，尝试查找社群图标
                box = self.recognizer.find_template(screenshot, "icon_community", threshold=0.7)
                if box:
                    print("  -> 点击社群图标")
                    self.adb.tap_center(box)
                else:
                    # 找不到社群图标，按返回键
                    print("  -> 返回上一页")
                    self.adb.back()

            time.sleep(config.WAIT_PAGE_TRANSITION)

        print("用户信息获取完成")

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

        # 获取用户信息（如果没有）
        if not self.state.has_user_info():
            self.fetch_user_info()

        # 显示用户信息
        if self.state.has_user_info():
            user = self.state.get_user_info()
            print(f"用户: {user['username']} ({user['friend_id']})")

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
                if no_action_count >= config.UNRECOGNIZED_THRESHOLD:
                    print("连续多次无法识别界面，可能需要手动干预")
                    # Send notification only once per unrecognized state
                    if not self.unrecognized_notified and config.NOTIFICATION_ENABLED:
                        # 获取用户名
                        username = None
                        if self.state.has_user_info():
                            user = self.state.get_user_info()
                            username = user.get("username")

                        notify_unrecognized(
                            config.NOTIFICATION_WEBHOOK_KEY,
                            config.NOTIFICATION_SOUND,
                            port=self.port,
                            username=username
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
