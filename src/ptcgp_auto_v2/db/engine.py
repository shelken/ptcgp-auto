# -*- coding: utf-8 -*-
"""
SQLModel 数据库引擎

提供数据库连接和会话管理。
"""

from contextlib import contextmanager
from typing import Generator

from sqlmodel import Session, create_engine

from ptcgp_auto_v2.config.settings import get_settings

# 全局引擎实例（延迟初始化）
_engine = None


def get_engine():
    """
    获取数据库引擎

    使用单例模式，确保全局只有一个引擎实例。
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(f"sqlite:///{settings.db_path}", echo=False)
    return _engine


def get_session() -> Session:
    """
    获取数据库会话

    返回一个新的 Session 实例，调用者负责管理其生命周期。
    推荐使用 with 语句或 session_scope() 上下文管理器。
    """
    return Session(get_engine())


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    数据库会话上下文管理器

    自动处理提交和回滚：
    - 正常退出时自动提交
    - 发生异常时自动回滚

    用法：
        with session_scope() as session:
            account = session.get(Account, 1)
            account.nickname = "new_name"
            # 自动提交
    """
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
