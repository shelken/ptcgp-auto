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

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.db.models import Account
from ptcgp_auto_v2.db.repositories import AccountRepository

logger = logging.getLogger(__name__)

# 注意：adb push/pull 无法处理带冒号的文件名，使用不带冒号的临时路径
DEVICE_TEMP_PATH = "/sdcard/deviceAccount_temp.xml"


@dataclass
class DeviceAccountInfo:
    """设备账号信息（从 XML 解析）"""

    device_account: str  # 设备账号 ID，唯一标识符
    nintendo_id: Optional[str] = None  # Nintendo 账号 ID（从 JWT 解析）
    country: Optional[str] = None  # 国家/地区
    session_token_iat: Optional[int] = None  # sessionToken 的 iat（签发时间戳）
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
        self._settings = get_settings()
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
            if self._update_account_from_info(account, account_info):
                self.account_repo.update(account)
                logger.debug(f"已更新账号: {account.nickname or account.game_id}")
            logger.info(
                f"识别到账号: {account.nickname or account.game_id} (ID: {account.id})"
            )
            return account

        # 创建新账号
        account = Account(
            game_id=device_account_id,
            nintendo_id=account_info.nintendo_id,
            country=account_info.country,
            xml_content=account_info.xml_content,
            session_token_iat=account_info.session_token_iat,
        )
        account = self.account_repo.create(account, auto_assign_plan=False)
        logger.info(
            f"创建新账号: {device_account_id} (ID: {account.id}) [未分配计划，等待初始化]"
        )

        # 仅在启用自动创建账号时生成 init_account 任务
        if self._settings.auto_create_accounts:
            self._create_init_task(account)
        else:
            logger.info("自动创建账号未启用，跳过 init_account 任务")

        return account

    def _create_init_task(self, account: Account):
        """为新账号创建初始化任务"""
        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository
        from ptcgp_auto_v2.db.models import TaskInstance

        try:
            task_repo = TaskInstanceRepository()
            # 检查是否已存在 init_account 任务
            existing = task_repo.get_by_account_and_type(account.id, "init_account")
            if existing:
                logger.debug(f"账号 {account.id} 已存在 init_account 任务")
                return

            # 创建 init_account 任务
            init_task = TaskInstance(
                account_id=account.id,
                task_type="init_account",
                status="pending",
                reset_type="once",
            )
            task_repo.create(init_task)
            logger.info(f"为账号 {account.id} 创建 init_account 任务")
        except Exception as e:
            logger.warning(f"创建 init_account 任务失败: {e}")

    def _update_account_from_info(
        self, account: Account, info: DeviceAccountInfo
    ) -> bool:
        """
        根据设备信息更新账号对象

        Args:
            account: 账号对象
            info: 设备提取的账号信息

        Returns:
            bool: 是否有更新
        """
        updated = False

        if info.nintendo_id and account.nintendo_id != info.nintendo_id:
            account.nintendo_id = info.nintendo_id
            updated = True
        if info.country and account.country != info.country:
            account.country = info.country
            updated = True

        # 比较 iat，决定是否更新 xml_content
        if self._should_update_xml(account, info):
            old_iat = account.session_token_iat
            account.xml_content = info.xml_content
            account.session_token_iat = info.session_token_iat
            updated = True
            logger.debug(f"Token 已更新: iat {old_iat} -> {info.session_token_iat}")

        return updated

    def _extract_account_info(self) -> Optional[DeviceAccountInfo]:
        """
        从设备提取并解析账号信息

        Returns:
            DeviceAccountInfo 或 None
        """
        try:
            # 检查是否有 Root 权限
            if not self.adb.is_rooted():
                logger.warning("设备未 Root")
                return None

            # 检查源文件是否存在
            check_result = self.adb.run_as_root(f"ls {self._settings.device_xml_path}")
            if not check_result or "No such file" in check_result:
                logger.debug("设备上未找到账号 XML 文件")
                return None

            # 复制 XML 到 sdcard
            self.adb.run_as_root(
                f"cp {self._settings.device_xml_path} {DEVICE_TEMP_PATH}"
            )
            self.adb.run_as_root(f"chmod 644 {DEVICE_TEMP_PATH}")

            # 拉取到本地（使用随机文件名，避免多设备并发冲突）
            import uuid

            temp_path = self.storage_dir / f"temp_{uuid.uuid4().hex[:8]}.xml"
            if not self.adb.pull(DEVICE_TEMP_PATH, str(temp_path)):
                return None

            if not temp_path.exists():
                return None

            # 读取内容
            xml_content = temp_path.read_bytes()

            # 清理临时文件
            temp_path.unlink(missing_ok=True)
            self.adb.run_as_root(f"rm {DEVICE_TEMP_PATH}")

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

            # 解析 Nintendo ID 和 country（从 idToken JWT 中提取）
            nintendo_id = None
            country = None
            id_token = self._extract_xml_string(content, "idToken")
            if id_token:
                jwt_payload = self._decode_jwt_payload(id_token)
                if jwt_payload:
                    nintendo_id = jwt_payload.get("sub")
                    country = jwt_payload.get("country")

            # 解析 sessionToken 的 iat（签发时间戳，用于判断 token 新旧）
            session_token_iat = None
            session_token = self._extract_xml_string(content, "sessionToken")
            if session_token:
                jwt_payload = self._decode_jwt_payload(session_token)
                if jwt_payload:
                    session_token_iat = jwt_payload.get("iat")

            return DeviceAccountInfo(
                device_account=device_account,
                nintendo_id=nintendo_id,
                country=country,
                session_token_iat=session_token_iat,
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

    def _should_update_xml(
        self, account: Account, account_info: DeviceAccountInfo
    ) -> bool:
        """
        判断是否应该更新 xml_content

        基于 session_token_iat 比较，新 token 更新时返回 True
        """
        new_iat = account_info.session_token_iat
        old_iat = account.session_token_iat

        # 条件1：设备 iat 比数据库更新
        iat_is_newer = new_iat and (old_iat is None or new_iat > old_iat)
        # 条件2：数据库没有 xml_content 但设备有
        db_missing_xml = bool(account_info.xml_content) and not bool(account.xml_content)

        should_update = iat_is_newer or db_missing_xml

        # 打印调试日志
        if should_update:
            if iat_is_newer:
                logger.debug(
                    f"XML 需更新: 设备 iat ({new_iat}) > 数据库 iat ({old_iat})"
                )
            elif db_missing_xml:
                logger.debug("XML 需更新: 数据库缺少 xml_content")
        else:
            if new_iat and old_iat and new_iat == old_iat:
                logger.debug(f"XML 无需更新: iat 相同 ({new_iat})")
            elif new_iat and old_iat and new_iat < old_iat:
                logger.debug(
                    f"XML 无需更新: 数据库 iat ({old_iat}) > 设备 iat ({new_iat})"
                )
            elif not new_iat:
                logger.debug("XML 无需更新: 账号无 iat")

        return should_update


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
