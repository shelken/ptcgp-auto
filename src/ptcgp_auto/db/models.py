"""
数据模型定义

使用 dataclass 定义数据结构，便于类型检查和序列化。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import json


@dataclass
class Account:
    """账号数据模型"""

    id: Optional[int] = None
    game_id: str = ""
    username: Optional[str] = None
    xml_path: Optional[str] = None
    xml_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "Account":
        """从数据库行创建 Account 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            game_id=row["game_id"],
            username=row["username"],
            xml_path=row["xml_path"],
            xml_hash=row["xml_hash"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "game_id": self.game_id,
            "username": self.username,
            "xml_path": self.xml_path,
            "xml_hash": self.xml_hash,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class PackRecord:
    """开包记录数据模型"""

    id: Optional[int] = None
    account_id: int = 0
    pack_type: str = ""
    opened_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> "PackRecord":
        """从数据库行创建 PackRecord 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            pack_type=row["pack_type"],
            opened_at=_parse_datetime(row["opened_at"]),
        )


@dataclass
class AccountConfig:
    """账号配置数据模型"""

    id: Optional[int] = None
    account_id: int = 0
    pack_preference: dict = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_row(cls, row) -> "AccountConfig":
        """从数据库行创建 AccountConfig 对象"""
        if row is None:
            return None

        # 解析 JSON 格式的 pack_preference
        pack_pref = row["pack_preference"]
        if isinstance(pack_pref, str):
            try:
                pack_pref = json.loads(pack_pref)
            except (json.JSONDecodeError, TypeError):
                pack_pref = {}

        return cls(
            id=row["id"],
            account_id=row["account_id"],
            pack_preference=pack_pref or {},
            enabled=bool(row["enabled"]),
        )

    def pack_preference_json(self) -> str:
        """将 pack_preference 转换为 JSON 字符串"""
        return json.dumps(self.pack_preference, ensure_ascii=False)


def _parse_datetime(value) -> Optional[datetime]:
    """解析日期时间字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        # SQLite 默认格式
        return datetime.fromisoformat(value.replace(" ", "T"))
    except (ValueError, AttributeError):
        return None
