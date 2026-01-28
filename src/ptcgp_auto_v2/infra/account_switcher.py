# -*- coding: utf-8 -*-
"""
账号切换模块

通过 ADB 注入 XML 文件实现账号切换。
"""

import logging
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.infra.adb import AdbController

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account

logger = logging.getLogger(__name__)

# 注意：adb push 无法处理带冒号的文件名，使用不带冒号的临时路径
DEVICE_TEMP_PATH = "/sdcard/deviceAccount_temp.xml"


class AccountSwitcher:
    """
    账号切换器

    通过注入 XML 文件实现账号切换。需要设备已 Root。
    """

    def __init__(self, adb: AdbController):
        """
        初始化账号切换器

        Args:
            adb: ADB 控制器实例
        """
        self.adb = adb
        self._settings = get_settings()

    def switch_to(self, account: "Account", restart_app: bool = False) -> bool:
        """
        切换到指定账号

        Args:
            account: 目标账号
            restart_app: 是否在切换后重启游戏

        Returns:
            True 表示切换成功
        """
        if not account.xml_content:
            logger.warning(f"账号 {account.nickname} 没有 XML 内容")
            return False

        xml_path = self._write_temp_xml(account)
        if not xml_path:
            return False

        try:
            return self.inject_xml(xml_path, restart_app=restart_app)
        finally:
            try:
                if xml_path.exists():
                    xml_path.unlink()
            except Exception as e:
                logger.debug(f"清理临时 XML 失败: {e}")

    def _write_temp_xml(self, account: "Account") -> Optional[Path]:
        """写入账号 XML 内容到临时文件"""
        if not account.xml_content:
            return None

        try:
            temp_path = Path(f"/tmp/ptcgp_auto_v2_account_{account.id}.xml")
            temp_path.write_bytes(account.xml_content)
            return temp_path
        except Exception as e:
            logger.error(f"写入临时 XML 失败: {e}")
            return None

    def reset_game_environment(self):
        """
        重置游戏环境

        执行以下操作：
        1. 强制停止游戏应用
        2. 清理设备上的账号 XML
        3. 清理账号绑定相关文件
        """
        logger.debug("正在重置游戏环境...")
        self.adb.force_stop(self._settings.app_package)
        self.clean_device_xml()
        self._clean_account_bound_files()

    def inject_xml(
        self,
        xml_path: Path,
        restart_app: bool = True,
        wait_seconds: float = 1.0,
    ) -> bool:
        """
        注入账号 XML 到设备

        Args:
            xml_path: 本地 XML 文件路径
            restart_app: 是否在注入后重启游戏
            wait_seconds: 操作间等待时间

        Returns:
            是否注入成功
        """
        xml_path = Path(xml_path)
        if not xml_path.exists():
            logger.error(f"XML 文件不存在: {xml_path}")
            return False

        if not self.adb.is_rooted():
            logger.warning("设备未 Root，无法注入 XML")
            return False

        try:
            # 1. 重置游戏环境（关闭、清理）
            self.reset_game_environment()
            time.sleep(wait_seconds)

            # 2. 推送 XML 到 sdcard
            logger.debug("推送 XML 到设备...")
            push_result = self.adb.push(str(xml_path), DEVICE_TEMP_PATH)
            if not push_result:
                logger.error("推送 XML 文件失败")
                return False
            time.sleep(wait_seconds * 0.5)

            # 3. 确保 shared_prefs 目录存在
            self.adb.run_as_root(f"mkdir -p {self._settings.shared_prefs_dir}")

            # 4. 复制 XML 到 shared_prefs
            logger.debug("复制 XML 到 shared_prefs...")
            result = self.adb.run_as_root(f"cp {DEVICE_TEMP_PATH} {self._settings.device_xml_path}")
            if result is None:
                logger.error("复制 XML 到 shared_prefs 失败")
                return False

            # 5. 设置正确的权限和所有者
            self.adb.run_as_root(f"chmod 660 {self._settings.device_xml_path}")
            self.adb.run_as_root(
                f"chown $(stat -c %u:%g {self._settings.shared_prefs_dir}) {self._settings.device_xml_path}"
            )
            time.sleep(wait_seconds * 0.5)

            # 6. 清理临时文件
            self.adb.run_as_root(f"rm {DEVICE_TEMP_PATH}")

            # 7. 可选：重启游戏
            if restart_app:
                self.adb.restart_app(self._settings.app_package)

            logger.info(f"账号 XML 已注入: {xml_path.name}")
            return True

        except Exception as e:
            logger.error(f"注入账号 XML 时出错: {e}")
            return False

    def _clean_account_bound_files(self):
        """
        清理账号绑定相关文件

        切换账号前清理这些文件，避免服务端校验失败（错误码 102-243-017）。
        这些文件会在游戏启动时自动重新生成。
        """
        logger.debug("清理账号绑定相关文件...")
        for pattern in self._settings.files_to_clean_on_switch:
            self.adb.run_as_root(f"rm -f {pattern}")
        logger.debug("账号绑定文件清理完成")



    def clean_device_xml(self) -> bool:
        """
        清理设备上的账号 XML 文件

        通常在账号同步完成后调用，防止被手动登录导致 Token 失效。

        Returns:
            bool: 是否清理成功
        """
        try:
            logger.debug("清理设备上的账号 XML...")
            # 尝试直接删除（如果之前设置了权限可能不需要 root），或者尝试用 root 删除
            # 优先使用 run_as_root 因为该文件通常在受保护目录
            self.adb.run_as_root(f"rm {self._settings.device_xml_path}")
            return True
        except Exception as e:
            logger.error(f"清理账号 XML 失败: {e}")
            return False


