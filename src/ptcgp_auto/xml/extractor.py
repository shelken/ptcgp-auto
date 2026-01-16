"""
账号 XML 提取器

通过 ADB 从设备中提取账号 XML 文件。
"""

import hashlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from ..adb_controller import AdbController
from ..utils import get_data_dir
from ..logger import get_logger

logger = get_logger(__name__)

# PTCGP 账号 XML 在设备中的路径
DEVICE_XML_PATH = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
DEVICE_TEMP_PATH = "/sdcard/deviceAccount.xml"


class AccountExtractor:
    """账号 XML 提取器"""

    def __init__(self, adb: AdbController, storage_dir: Optional[Path] = None):
        """
        初始化提取器

        Args:
            adb: ADB 控制器实例
            storage_dir: XML 文件存储目录，默认为数据目录下的 accounts/
        """
        self.adb = adb
        if storage_dir is None:
            storage_dir = get_data_dir() / "accounts"
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def extract(self) -> Optional[Tuple[Path, str]]:
        """
        提取当前设备的账号 XML

        Returns:
            (xml_path, xml_hash) 元组，失败返回 None
        """
        try:
            # 1. 复制 XML 到 sdcard（需要 root）
            result = self._run_su_command(f"cp {DEVICE_XML_PATH} {DEVICE_TEMP_PATH}")
            if result is None:
                logger.error("复制 XML 到 sdcard 失败，可能设备未 root")
                return None

            # 2. 设置权限以便 adb pull
            self._run_su_command(f"chmod 644 {DEVICE_TEMP_PATH}")

            # 3. 拉取 XML 到本地临时文件
            temp_file = self.storage_dir / "temp_extract.xml"
            pull_result = self.adb.pull(DEVICE_TEMP_PATH, str(temp_file))
            if not pull_result or not temp_file.exists():
                logger.error("拉取 XML 文件失败")
                return None

            # 4. 计算哈希
            xml_hash = self._calculate_hash(temp_file)

            # 5. 重命名为最终文件名（使用时间戳和哈希前8位）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = f"{timestamp}_{xml_hash[:8]}.xml"
            final_path = self.storage_dir / final_name
            temp_file.rename(final_path)

            # 6. 清理设备上的临时文件
            self._run_su_command(f"rm {DEVICE_TEMP_PATH}")

            logger.info(f"账号 XML 已提取: {final_path}")
            return (final_path, xml_hash)

        except Exception as e:
            logger.error(f"提取账号 XML 时出错: {e}")
            return None

    def extract_to_path(self, target_path: Path) -> Optional[str]:
        """
        提取 XML 到指定路径

        Args:
            target_path: 目标路径

        Returns:
            XML 哈希，失败返回 None
        """
        try:
            # 1. 复制 XML 到 sdcard（需要 root）
            result = self._run_su_command(f"cp {DEVICE_XML_PATH} {DEVICE_TEMP_PATH}")
            if result is None:
                return None

            # 2. 设置权限
            self._run_su_command(f"chmod 644 {DEVICE_TEMP_PATH}")

            # 3. 拉取到目标路径
            target_path.parent.mkdir(parents=True, exist_ok=True)
            pull_result = self.adb.pull(DEVICE_TEMP_PATH, str(target_path))
            if not pull_result or not target_path.exists():
                return None

            # 4. 计算哈希
            xml_hash = self._calculate_hash(target_path)

            # 5. 清理
            self._run_su_command(f"rm {DEVICE_TEMP_PATH}")

            return xml_hash

        except Exception as e:
            logger.error(f"提取账号 XML 到 {target_path} 时出错: {e}")
            return None

    def _run_su_command(self, cmd: str) -> Optional[str]:
        """执行需要 root 权限的命令"""
        full_cmd = f"su -c '{cmd}'"
        try:
            result = self.adb.shell(full_cmd)
            return result
        except Exception as e:
            logger.debug(f"执行 su 命令失败: {e}")
            return None

    @staticmethod
    def _calculate_hash(file_path: Path) -> str:
        """计算文件 SHA256 哈希"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


def extract_account(adb: AdbController) -> Optional[Tuple[Path, str]]:
    """
    便捷函数：提取当前设备的账号 XML

    Args:
        adb: ADB 控制器实例

    Returns:
        (xml_path, xml_hash) 元组，失败返回 None
    """
    extractor = AccountExtractor(adb)
    return extractor.extract()
