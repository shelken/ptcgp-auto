"""
PTCGP 单人对战自动化脚本 - 主入口
"""

import sys
import subprocess
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
from device_discovery import discover_devices
from logger import setup_logging, set_username, get_logger, allocate_colors

logger = get_logger(__name__)


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
        logger.info("正在获取用户信息...")

        while not self.state.has_user_info():
            screenshot = self.adb.screenshot()
            if not screenshot:
                time.sleep(1)
                continue

            page_name, page_info, match_info = self.page_detector.detect(screenshot)

            if not page_name:
                time.sleep(1)
                continue

            logger.debug(f"  [{page_name}]")

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
                    logger.debug("  -> 点击社群图标")
                    self.adb.tap_center(box)
            elif page_name in ("_main_page", "game_open_page"):
                # 模拟器主页或游戏开启页面，执行默认动作进入游戏
                match_info["page_info"] = page_info
                self.action_handler.execute("click_identifier", screenshot, match_info)
            else:
                # 其他页面，尝试查找社群图标
                box = self.recognizer.find_template(screenshot, "icon_community", threshold=0.7)
                if box:
                    logger.debug("  -> 点击社群图标")
                    self.adb.tap_center(box)
                else:
                    # 找不到社群图标，按返回键
                    logger.debug("  -> 返回上一页")
                    self.adb.back()

            time.sleep(config.WAIT_PAGE_TRANSITION)

        logger.info("用户信息获取完成")

    def start(self, tutorial_mode=False):
        """启动自动化

        Args:
            tutorial_mode: 是否直接进入教程解锁模式
        """
        logger.info("=" * 50)
        logger.info("PTCGP 单人对战自动化脚本")
        logger.info("=" * 50)

        # 连接 ADB
        if not self.adb.connect():
            logger.error("无法连接到模拟器，请检查 ADB 配置")
            return False

        # 连接后重新加载模板（根据实际分辨率缩放）
        self.recognizer.reload_templates()

        # 获取用户信息（如果没有）
        if not self.state.has_user_info():
            self.fetch_user_info()

        # 显示用户信息并设置日志上下文
        if self.state.has_user_info():
            user = self.state.get_user_info()
            set_username(user['username'])
            logger.info(f"用户: {user['username']} ({user['friend_id']})")

        logger.info("开始自动化流程...")

        try:
            if tutorial_mode:
                # 先进入教程模式
                logger.info("提示: 教程解锁模式")
                from actions.tutorial import TutorialRunner
                runner = TutorialRunner(self.adb, self.recognizer)
                runner.run()
                logger.info("教程完成，进入正常对战流程...")

            # 正常主循环
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
            # 截图
            screenshot = self.adb.screenshot()
            if not screenshot:
                logger.warning("截图失败，等待重试...")
                time.sleep(1)
                continue

            # 识别当前界面
            page_name, page_info, match_info = self.page_detector.detect(screenshot)

            if page_name:
                no_action_count = 0
                self.unrecognized_notified = False  # Reset notification state
                logger.info(f"[界面] {page_name}")

                # 执行对应动作
                action = page_info.get("action", "unknown")
                # 把 page_info 传给动作，让动作能访问配置（如 action_template）
                match_info["page_info"] = page_info
                self.action_handler.execute(action, screenshot, match_info)

                # 等待页面切换
                time.sleep(config.WAIT_PAGE_TRANSITION)
            else:
                no_action_count += 1
                logger.debug(f"无法识别次数 {no_action_count} 次")
                if no_action_count >= config.UNRECOGNIZED_THRESHOLD:
                    logger.warning("连续多次无法识别界面，可能需要手动干预")
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
                    # 强制停止应用
                    self.adb.force_stop_app(config.PTCGP_PACKAGE_NAME)
                    no_action_count = 0
                time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)


def run_all_devices(settings: dict):
    """多设备模式：发现设备 → 启动子进程"""
    devices = discover_devices()

    if not devices:
        logger.warning("未发现运行中的 BlueStacks 设备")
        return

    # 处理排除端口
    exclude_str = settings.get("exclude", "")
    if exclude_str:
        exclude_ports = set(p.strip() for p in exclude_str.split(",") if p.strip())
        devices = [d for d in devices if d.split(":")[1] not in exclude_ports]
        if exclude_ports:
            logger.info(f"排除端口: {', '.join(sorted(exclude_ports))}")

    if not devices:
        logger.warning("排除后无可用设备")
        return

    logger.info(f"发现 {len(devices)} 个设备:")
    for addr in devices:
        logger.info(f"  - {addr}")

    # 为所有端口分配颜色（父进程统一分配，避免子进程冲突）
    ports = [addr.split(":")[1] for addr in devices]
    port_colors = allocate_colors(ports)

    # 启动子进程
    processes = []
    for addr in devices:
        port = addr.split(":")[1]
        color = port_colors[port]
        # 构建参数（每个设备的颜色不同）
        base_args = build_base_args(settings, color=color)
        cmd = [sys.executable, __file__, "-a", addr] + base_args
        p = subprocess.Popen(cmd)
        processes.append((addr, p))
        logger.info(f"[{port}] 已启动 (颜色: {color})")

    # 等待所有子进程
    try:
        for addr, p in processes:
            p.wait()
    except KeyboardInterrupt:
        logger.info("正在终止所有子进程...")
        for addr, p in processes:
            p.terminate()
        for addr, p in processes:
            p.wait()


def build_base_args(settings: dict, color: str = None) -> list:
    """从 settings 构建子进程参数（排除 all 和 address）

    Args:
        settings: 配置字典
        color: 分配给此设备的日志颜色
    """
    args = []
    if settings.get("language"):
        args.extend(["-l", settings["language"]])
    if settings.get("tutorial"):
        args.append("-t")
    if settings.get("log_level"):
        args.extend(["--log-level", settings["log_level"]])
    if color:
        args.extend(["--log-color", color])
    if settings.get("no_auto_battle"):
        args.append("--no-auto-battle")
    if settings.get("notify_key"):
        args.extend(["--notify-key", settings["notify_key"]])
    if settings.get("no_notify_sound"):
        args.append("--no-notify-sound")
    return args


def run_single_device(settings: dict):
    """单设备模式：原有逻辑"""
    apply_settings_to_config(settings)

    # 初始化日志系统
    log_level = settings.get("log_level", "INFO")
    log_color = settings.get("log_color")  # 由父进程分配的颜色
    setup_logging(port=config.ADB_PORT, level=log_level, color=log_color)

    print_active_settings(settings)

    host = config.ADB_HOST
    port = config.ADB_PORT

    auto = PTCGPAuto(host, port)
    auto.start(tutorial_mode=settings.get("tutorial", False))


def main():
    """主入口"""
    # 加载配置（CLI > 环境变量 > .env > 默认值）
    settings = load_settings()

    if settings.get("all"):
        run_all_devices(settings)
    else:
        run_single_device(settings)


if __name__ == "__main__":
    main()
