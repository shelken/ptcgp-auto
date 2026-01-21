"""
PTCGP 自动化主流程
"""

import time

from ptcgp_auto import config
from ptcgp_auto.utils import get_data_dir
from ptcgp_auto.adb_controller import AdbController
from ptcgp_auto.recognizer import get_recognizer
from ptcgp_auto.state_manager import get_state_manager
from ptcgp_auto.page_detector import PageDetector
from ptcgp_auto.actions import ActionHandler
from ptcgp_auto.actions.user import fetch_user_info_via_ui
from ptcgp_auto.notifier import notify_unrecognized, notify_recovered
from ptcgp_auto.logger import set_username, get_logger

logger = get_logger(__name__)


class PTCGPAuto:
    """PTCGP 单人对战自动化 - 状态机版本"""

    def __init__(self, host: str = None, port: int = None):
        self.host = host or config.ADB_HOST
        self.port = port or config.ADB_PORT
        self.adb = AdbController(self.host, self.port)
        self.recognizer = get_recognizer()
        data_dir = get_data_dir(self.port)
        state_file = str(data_dir / "state.json")
        self.state = get_state_manager(state_file)
        self.page_detector = PageDetector(self.recognizer)
        self.action_handler = ActionHandler(self.adb, self.recognizer, self.state)
        self.running = True
        self.unrecognized_notified = False

    def fetch_user_info(self) -> bool:
        """获取用户信息子流程 - 独立于主循环"""
        return fetch_user_info_via_ui(
            self.adb,
            self.recognizer,
            self.state,
            self.page_detector,
            self.action_handler,
            allow_restart=config.ALLOW_RESTART_ON_HOME_FAIL,
        )

    def start(self, tutorial_mode: bool = False):
        """启动自动化"""
        logger.info("=" * 50)
        logger.info("PTCGP 单人对战自动化脚本")
        logger.info("=" * 50)

        if not self.adb.connect():
            logger.error("无法连接到模拟器，请检查 ADB 配置")
            return False

        self.recognizer.reload_templates()

        if not self.state.has_user_info():
            self.fetch_user_info()

        if self.state.has_user_info():
            user = self.state.get_user_info()
            set_username(user["username"])
            logger.info(f"用户: {user['username']} ({user['friend_id']})")

        logger.info("开始自动化流程...")

        try:
            if tutorial_mode:
                logger.info("提示: 教程解锁模式")
                from ptcgp_auto.actions.tutorial import TutorialRunner

                runner = TutorialRunner(self.adb, self.recognizer)
                runner.run()
                logger.info("教程完成，进入正常对战流程...")

            logger.info("提示: 脚本会自动识别当前界面并执行相应操作")
            self.state.print_status()
            self.main_loop()
        except KeyboardInterrupt:
            logger.info("用户中断，退出...")
        except Exception as e:
            logger.error(f"发生错误: {e}")
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
            screenshot = self.adb.screenshot()
            if not screenshot:
                logger.warning("截图失败，等待重试...")
                time.sleep(1)
                continue

            page_name, page_info, match_info = self.page_detector.detect(screenshot)

            if page_name:
                no_action_count = 0
                if self.unrecognized_notified and config.NOTIFICATION_ENABLED:
                    username = None
                    if self.state.has_user_info():
                        username = self.state.get_user_info().get("username")
                    notify_recovered(
                        config.NOTIFICATION_WEBHOOK_KEY,
                        config.NOTIFICATION_SOUND,
                        port=self.port,
                        username=username,
                    )
                self.unrecognized_notified = False
                logger.info(f"[界面] {page_name}")

                action = page_info.get("action", "unknown")
                match_info["page_info"] = page_info
                self.action_handler.execute(action, screenshot, match_info)

                time.sleep(config.WAIT_PAGE_TRANSITION)
            else:
                no_action_count += 1
                logger.debug(f"无法识别次数 {no_action_count} 次")
                if no_action_count >= config.UNRECOGNIZED_THRESHOLD:
                    logger.warning("连续多次无法识别界面，可能需要手动干预")
                    if not self.unrecognized_notified and config.NOTIFICATION_ENABLED:
                        username = None
                        if self.state.has_user_info():
                            user = self.state.get_user_info()
                            username = user.get("username")

                        notify_unrecognized(
                            config.NOTIFICATION_WEBHOOK_KEY,
                            config.NOTIFICATION_SOUND,
                            port=self.port,
                            username=username,
                        )
                        self.unrecognized_notified = True
                    self.adb.force_stop_app(config.PTCGP_PACKAGE_NAME)
                    no_action_count = 0
                time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)
