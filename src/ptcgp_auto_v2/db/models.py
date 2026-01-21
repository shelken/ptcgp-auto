# -*- coding: utf-8 -*-
"""
数据模型定义

使用 dataclass 定义数据结构，便于类型检查和序列化。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


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


@dataclass
class TaskPlan:
    """
    任务计划模型

    定义账号应执行的任务列表。
    """

    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    task_types: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> Optional["TaskPlan"]:
        """从数据库行创建 TaskPlan 对象"""
        if row is None:
            return None

        # 解析 JSON 格式的 task_types
        task_types = row["task_types"]
        if isinstance(task_types, str):
            try:
                task_types = json.loads(task_types)
            except (json.JSONDecodeError, TypeError):
                task_types = []

        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            task_types=task_types or [],
            created_at=_parse_datetime(row["created_at"]),
        )

    def task_types_json(self) -> str:
        """将 task_types 转换为 JSON 字符串"""
        return json.dumps(self.task_types, ensure_ascii=False)

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "task_types": self.task_types,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class Account:
    """
    账号模型

    表示一个游戏账号，是任务状态的主体。

    字段说明：
    - game_id: 设备账号 ID（来自 XML deviceAccount 字段），唯一标识符
    - friend_id: 游戏内朋友 ID（格式 XXXX-XXXX-XXXX-XXXX），用户可见，可通过 OCR 获取
    - nintendo_id: Nintendo 账号 ID（从 JWT 解析），用于关联任天堂账号
    - nickname: 用户昵称，方便识别
    - country: 国家/地区代码（从 JWT 解析）
    - xml_content: 账号 XML 文件内容（用于账号切换）
    - session_token_iat: sessionToken 的 iat 字段（签发时间戳），用于判断 token 是否最新
    """

    id: Optional[int] = None
    game_id: str = ""  # deviceAccount 字段，唯一标识
    friend_id: Optional[str] = None  # 朋友 ID，格式 XXXX-XXXX-XXXX-XXXX
    nintendo_id: Optional[str] = None  # Nintendo 账号 ID
    nickname: Optional[str] = None  # 用户昵称
    level: Optional[int] = None  # 账号等级（从 UI 获取）
    country: Optional[str] = None  # 国家/地区
    xml_content: Optional[bytes] = None  # XML 文件内容
    session_token_iat: Optional[int] = None  # sessionToken 的签发时间戳
    task_plan_id: Optional[int] = None
    task_plan: Optional[TaskPlan] = None  # 关联的任务计划（延迟加载）
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> Optional["Account"]:
        """从数据库行创建 Account 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            game_id=row["game_id"],
            friend_id=row["friend_id"],
            nintendo_id=row["nintendo_id"],
            nickname=row["nickname"],
            level=row["level"] if "level" in row.keys() else None,
            country=row["country"],
            xml_content=row["xml_content"],
            session_token_iat=row["session_token_iat"] if "session_token_iat" in row.keys() else None,
            task_plan_id=row["task_plan_id"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "game_id": self.game_id,
            "friend_id": self.friend_id,
            "nintendo_id": self.nintendo_id,
            "nickname": self.nickname,
            "level": self.level,
            "country": self.country,
            "xml_content": self.xml_content.hex() if self.xml_content else None,
            "session_token_iat": self.session_token_iat,
            "task_plan_id": self.task_plan_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @property
    def display_name(self) -> str:
        """获取显示名称（优先昵称 > 朋友ID > 游戏ID）"""
        return self.nickname or self.friend_id or self.game_id or f"Account#{self.id}"


@dataclass
class TaskInstance:
    """
    任务实例模型

    表示一个具体的任务执行实例（如账号A的今日开包任务）。
    """

    id: Optional[int] = None
    account_id: int = 0
    task_type: str = ""
    status: str = "pending"  # pending/running/completed/failed
    reset_type: str = "daily"  # daily/weekly/once
    error_message: Optional[str] = None
    last_completed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 关联对象（延迟加载）
    account: Optional[Account] = None

    @classmethod
    def from_row(cls, row) -> Optional["TaskInstance"]:
        """从数据库行创建 TaskInstance 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            task_type=row["task_type"],
            status=row["status"],
            reset_type=row["reset_type"],
            error_message=row["error_message"],
            last_completed_at=_parse_datetime(row["last_completed_at"]),
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "task_type": self.task_type,
            "status": self.status,
            "reset_type": self.reset_type,
            "error_message": self.error_message,
            "last_completed_at": (
                self.last_completed_at.isoformat() if self.last_completed_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def save(self):
        """保存到数据库"""
        from ptcgp_auto_v2.db.repositories import TaskInstanceRepository

        repo = TaskInstanceRepository()
        repo.update(self)


@dataclass
class AccountPackConfig:
    """
    账号开包配置模型

    记录账号在不同类型任务下的目标卡包设置。

    字段说明：
    - type: 配置类型（如 daily）
    - pack_code: 卡包系列编码（如 A1, A1a）
    - booster_name: 子包名称（用于模板目录）
    """

    id: Optional[int] = None
    account_id: int = 0
    type: str = ""
    pack_code: str = ""
    booster_name: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> Optional["AccountPackConfig"]:
        """从数据库行创建 AccountPackConfig 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            type=row["type"],
            pack_code=row["pack_code"],
            booster_name=row["booster_name"],
            created_at=_parse_datetime(row["created_at"]),
            updated_at=_parse_datetime(row["updated_at"]),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "type": self.type,
            "pack_code": self.pack_code,
            "booster_name": self.booster_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


@dataclass
class PackRecord:
    """
    开包记录模型

    记录账号的开包历史。
    """

    id: Optional[int] = None
    account_id: int = 0
    pack_type: str = ""
    opened_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> Optional["PackRecord"]:
        """从数据库行创建 PackRecord 对象"""
        if row is None:
            return None
        return cls(
            id=row["id"],
            account_id=row["account_id"],
            pack_type=row["pack_type"],
            opened_at=_parse_datetime(row["opened_at"]),
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "pack_type": self.pack_type,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
