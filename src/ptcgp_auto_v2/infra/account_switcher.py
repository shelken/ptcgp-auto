# -*- coding: utf-8 -*-
"""
账号切换模块

通过 ADB 注入 XML 文件实现账号切换。
"""

import logging
import time
from pathlib import Path
from typing import Optional, TYPE_CHECKING

from ptcgp_auto_v2.infra.adb import AdbController

if TYPE_CHECKING:
    from ptcgp_auto_v2.db.models import Account

logger = logging.getLogger(__name__)

# 配置常量
PTCGP_PACKAGE_NAME = "jp.pokemon.pokemontcgp"
DEVICE_XML_PATH = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
# 注意：adb push 无法处理带冒号的文件名，使用不带冒号的临时路径
DEVICE_TEMP_PATH = "/sdcard/deviceAccount_temp.xml"
DEVICE_SHARED_PREFS_DIR = "/data/data/jp.pokemon.pokemontcgp/shared_prefs"
PTCGP_MAIN_ACTIVITY = f"{PTCGP_PACKAGE_NAME}/com.unity3d.player.UnityPlayerActivity"


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
        self._is_rooted: Optional[bool] = None

    def is_rooted(self) -> bool:
        """
        检查设备是否已 Root

        Returns:
            True 表示已 Root
        """
        if self._is_rooted is not None:
            return self._is_rooted

        try:
            result = self.adb.shell("su -c 'id'")
            self._is_rooted = result is not None and "uid=0" in result
        except Exception:
            self._is_rooted = False

        logger.debug(f"设备 Root 状态: {self._is_rooted}")
        return self._is_rooted

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
            logger.error(f"账号 {account.nickname} 没有 XML 内容")
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

        if not self.is_rooted():
            logger.error("设备未 Root，无法注入 XML")
            return False

        try:
            # 1. 强制关闭游戏
            logger.debug("关闭游戏...")
            self.adb.force_stop(PTCGP_PACKAGE_NAME)
            time.sleep(wait_seconds)

            # 2. 推送 XML 到 sdcard
            logger.debug("推送 XML 到设备...")
            push_result = self.adb.push(str(xml_path), DEVICE_TEMP_PATH)
            if not push_result:
                logger.error("推送 XML 文件失败")
                return False
            time.sleep(wait_seconds * 0.5)

            # 3. 确保 shared_prefs 目录存在
            self._run_su_command(f"mkdir -p {DEVICE_SHARED_PREFS_DIR}")

            # 4. 复制 XML 到 shared_prefs
            logger.debug("复制 XML 到 shared_prefs...")
            result = self._run_su_command(f"cp {DEVICE_TEMP_PATH} {DEVICE_XML_PATH}")
            if result is None:
                logger.error("复制 XML 到 shared_prefs 失败")
                return False

            # 5. 设置正确的权限和所有者
            self._run_su_command(f"chmod 660 {DEVICE_XML_PATH}")
            self._run_su_command(
                f"chown $(stat -c %u:%g {DEVICE_SHARED_PREFS_DIR}) {DEVICE_XML_PATH}"
            )
            time.sleep(wait_seconds * 0.5)

            # 6. 清理临时文件
            self._run_su_command(f"rm {DEVICE_TEMP_PATH}")

            # 7. 可选：重启游戏
            if restart_app:
                logger.debug("启动游戏...")
                self._start_app()
                time.sleep(wait_seconds)

            logger.info(f"账号 XML 已注入: {xml_path.name}")
            return True

        except Exception as e:
            logger.error(f"注入账号 XML 时出错: {e}")
            return False

    def _run_su_command(self, cmd: str) -> Optional[str]:
        """执行需要 root 权限的命令"""
        full_cmd = f"su -c '{cmd}'"
        try:
            result = self.adb.shell(full_cmd)
            return result
        except Exception as e:
            logger.debug(f"执行 su 命令失败: {e}")
            return None

    def _start_app(self):
        """启动游戏应用"""
        self.adb.shell(f"am start -n {PTCGP_MAIN_ACTIVITY}")

    def extract_current_account_xml(self, local_path: Path) -> bool:
        """
        提取当前设备上的账号 XML

        Args:
            local_path: 本地保存路径

        Returns:
            是否提取成功
        """
        if not self.is_rooted():
            logger.error("设备未 Root，无法提取 XML")
            return False

        try:
            # 复制到 sdcard
            self._run_su_command(f"cp {DEVICE_XML_PATH} {DEVICE_TEMP_PATH}")
            time.sleep(0.5)

            # 拉取到本地
            result = self.adb.pull(DEVICE_TEMP_PATH, str(local_path))

            # 清理临时文件
            self._run_su_command(f"rm {DEVICE_TEMP_PATH}")

            if result:
                logger.info(f"已提取账号 XML: {local_path}")
            return result

        except Exception as e:
            logger.error(f"提取账号 XML 时出错: {e}")
            return False

    def get_current_account_hash(self) -> Optional[str]:
        """
        获取当前账号 XML 的哈希值

        Returns:
            MD5 哈希值或 None
        """
        if not self.is_rooted():
            return None

        try:
            result = self._run_su_command(f"md5sum {DEVICE_XML_PATH}")
            if result:
                # 输出格式: "hash  /path/to/file"
                return result.split()[0]
        except Exception:
            pass

        return None
