"""
每日开包运行器

负责协调多设备并行开包的主流程。
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Dict

from ..adb_controller import AdbController
from ..db.connection import Database
from ..db.models import Account
from ..logger import get_logger
from .account_manager import AccountManager
from .pack_opener import PackOpener
from .root_checker import filter_rooted_devices

logger = get_logger(__name__)

# 默认配置
DEFAULT_DB_PATH = Path.home() / ".ptcgp_auto" / "accounts.db"
DEFAULT_XML_DIR = Path.home() / ".ptcgp_auto" / "accounts"


class DailyRunner:
    """
    每日开包运行器

    协调多设备并行执行账号轮换和开包。
    """

    def __init__(
        self,
        device_addresses: List[str],
        db_path: Optional[Path] = None,
        xml_dir: Optional[Path] = None,
        get_user_info_func=None,
    ):
        """
        初始化运行器

        Args:
            device_addresses: 设备地址列表
            db_path: 数据库文件路径
            xml_dir: XML 文件存储目录
            get_user_info_func: 获取用户信息的函数
        """
        self.device_addresses = device_addresses
        self.db_path = db_path or DEFAULT_DB_PATH
        self.xml_dir = xml_dir or DEFAULT_XML_DIR

        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.xml_dir.mkdir(parents=True, exist_ok=True)

        # 数据库和账号管理器
        self.db = Database(self.db_path)
        self.account_manager = AccountManager(self.db, self.xml_dir)

        # 获取用户信息的回调
        self.get_user_info_func = get_user_info_func

        # 已 root 的设备
        self.rooted_devices: List[str] = []

        # 运行状态
        self.running = False

    def initialize(self) -> bool:
        """
        初始化运行器

        1. 连接数据库
        2. 过滤已 root 的设备

        Returns:
            是否初始化成功
        """
        logger.info("初始化每日开包运行器...")

        # 1. 初始化数据库
        self.db.connect()
        logger.info(f"数据库已连接: {self.db_path}")
        logger.info(f"当前账号数量: {self.account_manager.get_account_count()}")

        # 2. 过滤已 root 的设备
        if not self.device_addresses:
            logger.error("没有可用的设备")
            return False

        self.rooted_devices, not_rooted = filter_rooted_devices(self.device_addresses)

        if not self.rooted_devices:
            logger.error("没有已 root 的设备可用")
            return False

        logger.info(f"可用设备: {len(self.rooted_devices)} 个")
        return True

    def run_once(self) -> Dict[str, int]:
        """
        执行一轮开包

        Returns:
            统计结果 {"success": n, "failed": m, "skipped": k}
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}

        # 1. 获取待开包账号
        pending_accounts = self.account_manager.get_pending_accounts(hours=24)

        if not pending_accounts:
            logger.info("没有待开包的账号")
            return stats

        logger.info(f"待开包账号: {len(pending_accounts)} 个")
        logger.info(f"可用设备: {len(self.rooted_devices)} 个")

        # 2. 先处理各设备上的当前账号
        self._process_current_accounts()

        # 3. 分配账号到设备并行处理
        # 使用线程池，每个设备一个线程
        with ThreadPoolExecutor(max_workers=len(self.rooted_devices)) as executor:
            # 分配账号：轮询分配到各设备
            device_accounts: Dict[str, List[Account]] = {
                addr: [] for addr in self.rooted_devices
            }

            for i, account in enumerate(pending_accounts):
                device_idx = i % len(self.rooted_devices)
                device_addr = self.rooted_devices[device_idx]
                device_accounts[device_addr].append(account)

            # 提交任务
            futures = {}
            for device_addr, accounts in device_accounts.items():
                if accounts:
                    future = executor.submit(
                        self._process_device_accounts, device_addr, accounts
                    )
                    futures[future] = device_addr

            # 收集结果
            for future in as_completed(futures):
                device_addr = futures[future]
                try:
                    result = future.result()
                    stats["success"] += result.get("success", 0)
                    stats["failed"] += result.get("failed", 0)
                except Exception as e:
                    logger.error(f"设备 {device_addr} 处理失败: {e}")
                    # 将该设备的所有账号计为失败
                    stats["failed"] += len(device_accounts[device_addr])

        logger.info(
            f"本轮完成: 成功 {stats['success']}, 失败 {stats['failed']}, "
            f"跳过 {stats['skipped']}"
        )
        return stats

    def _process_current_accounts(self):
        """处理各设备上的当前账号（提取并注册）"""
        logger.info("处理各设备上的当前账号...")

        for device_addr in self.rooted_devices:
            try:
                adb = AdbController(device_addr)
                opener = PackOpener(
                    adb=adb,
                    account_manager=self.account_manager,
                    on_user_info_needed=self.get_user_info_func,
                )
                opener.process_current_account()
            except Exception as e:
                logger.warning(f"处理设备 {device_addr} 当前账号时出错: {e}")

    def _process_device_accounts(
        self, device_addr: str, accounts: List[Account]
    ) -> Dict[str, int]:
        """
        在单个设备上处理多个账号

        Args:
            device_addr: 设备地址
            accounts: 要处理的账号列表

        Returns:
            统计结果
        """
        stats = {"success": 0, "failed": 0}

        adb = AdbController(device_addr)
        opener = PackOpener(
            adb=adb,
            account_manager=self.account_manager,
            on_user_info_needed=self.get_user_info_func,
        )

        for account in accounts:
            try:
                if opener.process_account(account):
                    stats["success"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"[{device_addr}] 处理账号 {account.game_id} 时出错: {e}")
                stats["failed"] += 1

        return stats

    def run_daemon(self, check_interval: int = 3600):
        """
        以守护模式运行

        完成一轮后进入定时扫描，每隔指定时间检查待开包账号。

        Args:
            check_interval: 检查间隔（秒），默认 1 小时
        """
        self.running = True
        logger.info("进入守护模式...")

        while self.running:
            # 执行一轮
            stats = self.run_once()

            if stats["success"] == 0 and stats["failed"] == 0:
                logger.info(f"没有待处理账号，{check_interval // 60} 分钟后重新检查...")
            else:
                logger.info(f"本轮完成，{check_interval // 60} 分钟后重新检查...")

            # 等待下一轮
            try:
                for _ in range(check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到中断信号，停止运行...")
                self.running = False
                break

    def stop(self):
        """停止运行"""
        self.running = False
        logger.info("停止每日开包运行器...")

    def close(self):
        """关闭资源"""
        self.db.close()
        logger.info("资源已释放")


def run_daily_mode(
    device_addresses: List[str],
    db_path: Optional[str] = None,
    xml_dir: Optional[str] = None,
    daemon: bool = True,
):
    """
    运行每日开包模式

    便捷函数，用于从 main.py 调用。

    Args:
        device_addresses: 设备地址列表
        db_path: 数据库路径
        xml_dir: XML 存储目录
        daemon: 是否以守护模式运行
    """
    runner = DailyRunner(
        device_addresses=device_addresses,
        db_path=Path(db_path) if db_path else None,
        xml_dir=Path(xml_dir) if xml_dir else None,
    )

    try:
        if not runner.initialize():
            logger.error("初始化失败")
            return

        if daemon:
            runner.run_daemon()
        else:
            runner.run_once()
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        runner.close()
