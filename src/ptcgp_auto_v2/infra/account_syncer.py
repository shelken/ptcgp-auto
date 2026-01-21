# -*- coding: utf-8 -*-
"""
账号同步模块

负责从设备同步账号信息到数据库。
通过解析 deviceAccount:.xml 中的 deviceAccount 字段唯一识别账号。
"""

import base64
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.db.repositories import AccountRepository

logger = logging.getLogger(__name__)

# PTCGP 账号 XML 路径
DEVICE_XML_PATH = "/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml"
DEVICE_TEMP_PATH = "/sdcard/deviceAccount:.xml"


@dataclass
class DeviceAccountInfo:
    """设备账号信息（从 XML 解析）"""

    device_account: str  # 设备账号 ID，唯一标识符
    nintendo_id: Optional[str] = None  # Nintendo 账号 ID（从 JWT 解析）
    country: Optional[str] = None  # 国家/地区
    xml_content: bytes = b""  # 原始 XML 内容


class AccountSyncer:
    """
    账号同步器

    从设备获取当前登录账号，并同步到数据库。
    使用 deviceAccount 字段作为账号唯一标识。
    """

    def __init__(self, adb: AdbController, storage_dir: Optional[Path] = None):
        """
        初始化账号同步器

        Args:
            adb: ADB 控制器
            storage_dir: XML 存储目录
        """
        self.adb = adb
        if storage_dir is None:
            storage_dir = Path("data/accounts")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.account_repo = AccountRepository()

    def get_current_account(self) -> Optional[Account]:
        """
        获取设备当前登录的账号

        流程：
        1. 从设备提取账号 XML
        2. 解析 deviceAccount 字段作为唯一标识
        3. 在数据库中查找匹配的账号
        4. 如果不存在则创建新账号

        Returns:
            Account 对象，失败返回 None
        """
        # 提取并解析 XML
        account_info = self._extract_account_info()
        if not account_info:
            logger.warning("无法提取账号信息，可能设备未 Root 或游戏未登录")
            return None

        device_account_id = account_info.device_account
        logger.debug(f"设备账号 ID: {device_account_id}")

        # 用 device_account 作为 game_id 查找
        account = self.account_repo.get_by_game_id(device_account_id)
        if account:
            # 更新 Nintendo ID（如果有新的）
            if account_info.nintendo_id and account.nintendo_id != account_info.nintendo_id:
                account.nintendo_id = account_info.nintendo_id
                self.account_repo.update(account)
            logger.info(f"识别到账号: {account.nickname or account.game_id} (ID: {account.id})")
            return account

        # 创建新账号
        account = Account(
            game_id=device_account_id,
            nintendo_id=account_info.nintendo_id,
            country=account_info.country,
            xml_content=account_info.xml_content,
        )
        account = self.account_repo.create(account)
        logger.info(f"创建新账号: {device_account_id} (ID: {account.id})")

        return account

    def sync_account(self, account: Account) -> bool:
        """
        同步账号的 XML 信息

        Args:
            account: 要同步的账号

        Returns:
            是否同步成功
        """
        account_info = self._extract_account_info()
        if not account_info:
            return False

        # 更新账号信息
        if account_info.nintendo_id:
            account.nintendo_id = account_info.nintendo_id
        if account_info.country:
            account.country = account_info.country
        account.xml_content = account_info.xml_content

        return self.account_repo.update(account)

    def _extract_account_info(self) -> Optional[DeviceAccountInfo]:
        """
        从设备提取并解析账号信息

        Returns:
            DeviceAccountInfo 或 None
        """
        try:
            # 检查是否有 Root 权限
            if not self._is_rooted():
                logger.debug("设备未 Root")
                return None

            # 复制 XML 到 sdcard
            self._run_su(f"cp {DEVICE_XML_PATH} {DEVICE_TEMP_PATH}")
            self._run_su(f"chmod 644 {DEVICE_TEMP_PATH}")

            # 拉取到本地
            temp_path = self.storage_dir / "temp.xml"
            if not self.adb.pull(DEVICE_TEMP_PATH, str(temp_path)):
                return None

            if not temp_path.exists():
                return None

            # 读取内容
            xml_content = temp_path.read_bytes()

            # 清理临时文件
            temp_path.unlink(missing_ok=True)
            self._run_su(f"rm {DEVICE_TEMP_PATH}")

            # 解析 XML
            return self._parse_xml(xml_content)

        except Exception as e:
            logger.error(f"提取账号信息失败: {e}")
            return None

    def _parse_xml(self, xml_content: bytes) -> Optional[DeviceAccountInfo]:
        """
        解析账号 XML 内容

        Args:
            xml_content: XML 文件内容

        Returns:
            DeviceAccountInfo 或 None
        """
        try:
            content = xml_content.decode("utf-8")

            # 解析 deviceAccount（必需字段，唯一标识）
            device_account = self._extract_xml_string(content, "deviceAccount")
            if not device_account:
                logger.warning("XML 中未找到 deviceAccount 字段")
                return None

            # 解析 Nintendo ID（从 idToken JWT 中提取）
            nintendo_id = None
            country = None
            id_token = self._extract_xml_string(content, "idToken")
            if id_token:
                jwt_payload = self._decode_jwt_payload(id_token)
                if jwt_payload:
                    nintendo_id = jwt_payload.get("sub")
                    country = jwt_payload.get("country")

            return DeviceAccountInfo(
                device_account=device_account,
                nintendo_id=nintendo_id,
                country=country,
                xml_content=xml_content,
            )

        except Exception as e:
            logger.error(f"解析 XML 失败: {e}")
            return None

    def _extract_xml_string(self, content: str, name: str) -> Optional[str]:
        """
        从 XML 内容提取指定 name 的 string 值

        Args:
            content: XML 内容
            name: 字段名称

        Returns:
            字段值或 None
        """
        pattern = rf'<string name="{name}">([^<]+)</string>'
        match = re.search(pattern, content)
        return match.group(1) if match else None

    def _decode_jwt_payload(self, token: str) -> Optional[dict]:
        """
        解码 JWT token 的 payload 部分（不验证签名）

        Args:
            token: JWT token 字符串

        Returns:
            payload 字典或 None
        """
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            # JWT payload 是第二部分
            payload_b64 = parts[1]
            # 补齐 base64 padding
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += "=" * padding

            payload_json = base64.urlsafe_b64decode(payload_b64)
            return json.loads(payload_json)

        except Exception as e:
            logger.debug(f"JWT 解码失败: {e}")
            return None

    def _is_rooted(self) -> bool:
        """检查设备是否已 Root"""
        try:
            result = self.adb.shell("su -c 'id'")
            return result is not None and "uid=0" in result
        except Exception:
            return False

    def _run_su(self, cmd: str) -> Optional[str]:
        """执行 root 命令"""
        return self.adb.shell(f"su -c '{cmd}'")


def get_current_account(adb: AdbController) -> Optional[Account]:
    """
    便捷函数：获取设备当前登录的账号

    Args:
        adb: ADB 控制器

    Returns:
        Account 对象或 None
    """
    syncer = AccountSyncer(adb)
    return syncer.get_current_account()
