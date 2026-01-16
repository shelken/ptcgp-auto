"""
开包执行器

负责在单个设备上执行开包流程。
"""

import time
from pathlib import Path
from typing import Optional, Callable

from ..adb_controller import AdbController
from ..db.models import Account
from ..xml.extractor import extract_account
from ..xml.injector import inject_account
from ..logger import get_logger
from .account_manager import AccountManager

logger = get_logger(__name__)

# 开包流程超时时间（秒）
PACK_OPEN_TIMEOUT = 300


class PackOpener:
    """
    开包执行器

    负责在单个设备上执行账号切换和开包流程。
    """

    def __init__(
        self,
        adb: AdbController,
        account_manager: AccountManager,
        on_user_info_needed: Optional[Callable[[AdbController], tuple]] = None,
    ):
        """
        初始化开包执行器

        Args:
            adb: ADB 控制器
            account_manager: 账号管理器
            on_user_info_needed: 获取用户信息的回调函数，返回 (game_id, username)
        """
        self.adb = adb
        self.account_manager = account_manager
        self.on_user_info_needed = on_user_info_needed

    def process_current_account(self) -> Optional[Account]:
        """
        处理当前设备上的账号

        1. 提取当前账号 XML
        2. 检查是否在数据库中
        3. 如果不存在，获取用户信息并注册

        Returns:
            当前账号对象，如果处理失败则返回 None
        """
        logger.info(f"[{self.adb.device_address}] 处理当前账号...")

        # 1. 提取当前账号 XML
        xml_content = extract_account(self.adb)
        if not xml_content:
            logger.warning(f"[{self.adb.device_address}] 无法提取账号 XML")
            return None

        # 2. 检查是否在数据库中
        account = self.account_manager.find_account_by_xml_hash(xml_content)
        if account:
            logger.info(
                f"[{self.adb.device_address}] 当前账号已在数据库: "
                f"{account.game_id} (id={account.id})"
            )
            return account

        # 3. 账号不存在，需要获取用户信息
        logger.info(f"[{self.adb.device_address}] 当前账号不在数据库，获取用户信息...")

        if not self.on_user_info_needed:
            logger.error("未提供获取用户信息的回调函数")
            return None

        game_id, username = self.on_user_info_needed(self.adb)
        if not game_id:
            logger.error(f"[{self.adb.device_address}] 无法获取游戏 ID")
            return None

        # 4. 注册新账号
        account = self.account_manager.register_account(
            game_id=game_id,
            username=username,
            xml_content=xml_content,
        )
        return account

    def switch_to_account(self, account: Account) -> bool:
        """
        切换到指定账号

        Args:
            account: 目标账号

        Returns:
            是否切换成功
        """
        logger.info(
            f"[{self.adb.device_address}] 切换到账号: "
            f"{account.game_id} ({account.username or 'N/A'})"
        )

        xml_path = self.account_manager.get_xml_path(account)
        if not xml_path:
            logger.error(f"账号 {account.game_id} 的 XML 文件不存在")
            return False

        return inject_account(self.adb, xml_path, restart_app=True)

    def open_packs(self, account: Account, pack_types: list = None) -> bool:
        """
        为账号开包

        Args:
            account: 账号对象
            pack_types: 要开的包类型列表（暂未实现，预留扩展）

        Returns:
            是否开包成功
        """
        logger.info(f"[{self.adb.device_address}] 为账号 {account.game_id} 开包...")

        # TODO: 实现实际的开包逻辑
        # 这里需要复用现有的 actions 模块来执行开包
        # 1. 等待进入主界面
        # 2. 导航到开包界面
        # 3. 执行开包动作
        # 4. 返回主界面

        # 暂时使用占位实现
        logger.warning("开包逻辑尚未实现，使用占位实现")
        time.sleep(2)

        # 记录开包
        pack_type = pack_types[0] if pack_types else "default"
        self.account_manager.record_pack_opened(account, pack_type)

        return True

    def process_account(self, account: Account) -> bool:
        """
        处理单个账号的完整开包流程

        Args:
            account: 要处理的账号

        Returns:
            是否处理成功
        """
        try:
            # 1. 切换到目标账号
            if not self.switch_to_account(account):
                logger.error(f"切换到账号 {account.game_id} 失败")
                return False

            # 2. 等待游戏启动
            logger.info(f"[{self.adb.device_address}] 等待游戏启动...")
            time.sleep(10)  # TODO: 使用页面检测替代固定等待

            # 3. 开包
            if not self.open_packs(account):
                logger.error(f"账号 {account.game_id} 开包失败")
                return False

            logger.info(f"[{self.adb.device_address}] 账号 {account.game_id} 处理完成")
            return True

        except Exception as e:
            logger.error(f"处理账号 {account.game_id} 时出错: {e}")
            return False
