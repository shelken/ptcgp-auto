"""
账号管理器

负责账号的增删改查、待开包账号查询等业务逻辑。
"""

import hashlib
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from ..db.connection import Database
from ..db.models import Account, PackRecord
from ..db.repository import AccountRepository, PackRecordRepository, AccountConfigRepository
from ..logger import get_logger

logger = get_logger(__name__)


class AccountManager:
    """账号管理器"""

    def __init__(self, db: Database, xml_dir: Path):
        """
        初始化账号管理器

        Args:
            db: 数据库连接
            xml_dir: XML 文件存储目录
        """
        self.db = db
        self.xml_dir = Path(xml_dir)
        self.xml_dir.mkdir(parents=True, exist_ok=True)

        self.account_repo = AccountRepository(db)
        self.pack_repo = PackRecordRepository(db)
        self.config_repo = AccountConfigRepository(db)

    def get_pending_accounts(self, hours: int = 24) -> List[Account]:
        """
        获取待开包账号

        Args:
            hours: 时间阈值（小时），超过此时间未开包的账号将被返回

        Returns:
            待开包的账号列表
        """
        accounts = self.pack_repo.get_accounts_pending_packs(hours)
        logger.info(f"找到 {len(accounts)} 个待开包账号（>{hours}h 未开包）")
        return accounts

    def get_all_accounts(self, enabled_only: bool = True) -> List[Account]:
        """
        获取所有账号

        Args:
            enabled_only: 是否只返回启用的账号

        Returns:
            账号列表
        """
        return self.account_repo.get_all(enabled_only=enabled_only)

    def find_account_by_xml_hash(self, xml_content: bytes) -> Optional[Account]:
        """
        根据 XML 内容哈希查找账号

        Args:
            xml_content: XML 文件内容

        Returns:
            找到的账号，如果不存在则返回 None
        """
        xml_hash = self._compute_hash(xml_content)
        return self.account_repo.get_by_xml_hash(xml_hash)

    def find_account_by_game_id(self, game_id: str) -> Optional[Account]:
        """
        根据游戏 ID 查找账号

        Args:
            game_id: 游戏内 ID

        Returns:
            找到的账号，如果不存在则返回 None
        """
        return self.account_repo.get_by_game_id(game_id)

    def register_account(
        self,
        game_id: str,
        username: Optional[str] = None,
        xml_content: Optional[bytes] = None,
    ) -> Account:
        """
        注册新账号

        Args:
            game_id: 游戏内 ID
            username: 用户名（可选）
            xml_content: XML 文件内容（可选）

        Returns:
            创建的账号对象
        """
        # 检查是否已存在
        existing = self.account_repo.get_by_game_id(game_id)
        if existing:
            logger.info(f"账号已存在: {game_id} (id={existing.id})")
            # 更新信息
            if username:
                existing.username = username
            if xml_content:
                existing.xml_hash = self._compute_hash(xml_content)
                existing.xml_path = str(self._save_xml(game_id, xml_content))
            self.account_repo.update(existing)
            return existing

        # 创建新账号
        account = Account(game_id=game_id, username=username)

        if xml_content:
            account.xml_hash = self._compute_hash(xml_content)
            account.xml_path = str(self._save_xml(game_id, xml_content))

        account = self.account_repo.create(account)
        logger.info(f"注册新账号: {game_id} (id={account.id})")
        return account

    def update_account_xml(self, account: Account, xml_content: bytes) -> bool:
        """
        更新账号的 XML 文件

        Args:
            account: 账号对象
            xml_content: 新的 XML 内容

        Returns:
            是否更新成功
        """
        account.xml_hash = self._compute_hash(xml_content)
        account.xml_path = str(self._save_xml(account.game_id, xml_content))
        return self.account_repo.update(account)

    def record_pack_opened(self, account: Account, pack_type: str) -> PackRecord:
        """
        记录开包

        Args:
            account: 账号对象
            pack_type: 开的包类型

        Returns:
            开包记录对象
        """
        record = PackRecord(account_id=account.id, pack_type=pack_type)
        record = self.pack_repo.create(record)
        logger.info(f"记录开包: {account.game_id} - {pack_type}")
        return record

    def get_last_pack_time(self, account: Account) -> Optional[datetime]:
        """
        获取账号最后开包时间

        Args:
            account: 账号对象

        Returns:
            最后开包时间，如果从未开过则返回 None
        """
        return self.pack_repo.get_last_pack_time(account.id)

    def set_account_enabled(self, account: Account, enabled: bool) -> bool:
        """
        设置账号启用状态

        Args:
            account: 账号对象
            enabled: 是否启用

        Returns:
            是否设置成功
        """
        return self.config_repo.set_enabled(account.id, enabled)

    def get_account_count(self) -> int:
        """获取账号总数"""
        return self.account_repo.count()

    def get_xml_path(self, account: Account) -> Optional[Path]:
        """
        获取账号的 XML 文件路径

        Args:
            account: 账号对象

        Returns:
            XML 文件路径，如果不存在则返回 None
        """
        if account.xml_path:
            path = Path(account.xml_path)
            if path.exists():
                return path
        return None

    def _save_xml(self, game_id: str, xml_content: bytes) -> Path:
        """保存 XML 文件到本地"""
        # 使用 game_id 作为文件名
        safe_id = game_id.replace("/", "_").replace("\\", "_")
        xml_path = self.xml_dir / f"{safe_id}.xml"
        xml_path.write_bytes(xml_content)
        logger.debug(f"保存 XML: {xml_path}")
        return xml_path

    def _compute_hash(self, content: bytes) -> str:
        """计算内容的 SHA256 哈希"""
        return hashlib.sha256(content).hexdigest()
