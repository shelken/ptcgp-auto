# -*- coding: utf-8 -*-
"""
SQLModel 数据库引擎

提供数据库连接和会话管理。
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.pool import NullPool
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
        # 确保数据库 Schema 已初始化并完成自动补列迁移。
        # 注意：项目的 auto-migration 逻辑实现于 db/connection.py，
        # Web/任务等所有通过 SQLModel engine 访问数据库的入口都必须在这里先触发一次。
        from ptcgp_auto_v2.db.connection import get_database

        get_database()

        settings = get_settings()
        # 当前仅支持 SQLite，本项目同时在多线程场景运行。
        # 使用 NullPool 避免 QueuePool 在多线程/多连接下的限制与泄漏风险。
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            echo=False,
            poolclass=NullPool,
        )
    return _engine


def get_session() -> Session:
    """
    获取数据库会话 (普通模式)

    返回一个新的 Session 实例，调用者负责管理其生命周期 (调用 .close())。
    """
    return Session(get_engine())


def get_fastapi_session() -> Generator[Session, None, None]:
    """
    获取数据库会话 (FastAPI 依赖注入模式)

    使用 yield 确保请求结束后自动关闭会话。
    """
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()


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
