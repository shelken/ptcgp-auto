"""
账号 XML 注入器

通过 ADB 将账号 XML 文件注入到设备中。
"""

import time
from pathlib import Path
from typing import Optional

from ..adb_controller import AdbController
from ..config import PTCGP_PACKAGE_NAME
from ..logger import get_logger

logger = get_logger(__name__)

# PTCGP 账号 XML 在设备中的路径
DEVICE_XML_PATH = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
DEVICE_TEMP_PATH = "/sdcard/deviceAccount.xml"
DEVICE_SHARED_PREFS_DIR = "/data/data/jp.pokemon.pokemontcgp/shared_prefs"

# 游戏主 Activity
PTCGP_MAIN_ACTIVITY = f"{PTCGP_PACKAGE_NAME}/com.unity3d.player.UnityPlayerActivity"


class AccountInjector:
    """账号 XML 注入器"""

    def __init__(self, adb: AdbController):
        """
        初始化注入器

        Args:
            adb: ADB 控制器实例
        """
        self.adb = adb

    def inject(
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

        try:
            # 1. 强制关闭游戏
            logger.debug("关闭游戏...")
            self.adb.force_stop_app(PTCGP_PACKAGE_NAME)
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

            # 4. 复制 XML 到 shared_prefs（需要 root）
            logger.debug("复制 XML 到 shared_prefs...")
            result = self._run_su_command(f"cp {DEVICE_TEMP_PATH} {DEVICE_XML_PATH}")
            if result is None:
                logger.error("复制 XML 到 shared_prefs 失败，可能设备未 root")
                return False

            # 5. 设置正确的权限和所有者
            self._run_su_command(f"chmod 660 {DEVICE_XML_PATH}")
            # 获取应用 UID（通常 PTCGP 的 UID 格式为 u0_aXXX）
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


def inject_account(
    adb: AdbController,
    xml_path: Path,
    restart_app: bool = True,
) -> bool:
    """
    便捷函数：注入账号 XML 到设备

    Args:
        adb: ADB 控制器实例
        xml_path: 本地 XML 文件路径
        restart_app: 是否在注入后重启游戏

    Returns:
        是否注入成功
    """
    injector = AccountInjector(adb)
    return injector.inject(xml_path, restart_app=restart_app)
