# -*- coding: utf-8 -*-
"""
SQLModel 数据库引擎

这个文件负责 engine 单例和会话边界。
覆盖 SQLite engine 初始化、连接事件注册和 Session 入口。
关键依赖是 get_settings、apply_sqlite_pragmas 和 SQLModel Session。
"""

from contextlib import contextmanager
import logging
import threading
from typing import Generator

from sqlalchemy import event
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, create_engine

from ptcgp_auto_v2.config.settings import get_settings
from ptcgp_auto_v2.db.sqlite_config import (
    SQLITE_BUSY_TIMEOUT_MS,
    apply_sqlite_pragmas,
)

logger = logging.getLogger(__name__)

# 全局引擎实例（延迟初始化）
_engine = None


def get_engine():
    """
    变更前文件库场景使用 NullPool，每次创建 Session 都会重建 SQLite 连接。
    中间版本改成 SingletonThreadPool，但多线程守护模式会在唯一线程数超过 pool_size 时随机关闭仍在使用的连接。
    变更后改为 QueuePool，继续复用 SQLite 连接，同时去掉按线程身份回收连接的风险。
    """
    global _engine
    if _engine is None:
        # 确保数据库 Schema 已初始化并完成自动补列迁移。
        # 注意：项目的 auto-migration 逻辑实现于 db/connection.py，
        # Web/任务等所有通过 SQLModel engine 访问数据库的入口都必须在这里先触发一次。
        from ptcgp_auto_v2.db.connection import get_database

        get_database()

        settings = get_settings()
        # 这里显式使用 QueuePool，原因是守护模式长期运行且线程数会波动，需要稳定复用连接。
        _engine = create_engine(
            f"sqlite:///{settings.db_path}",
            echo=False,
            poolclass=QueuePool,
            connect_args={
                "check_same_thread": False,
                "timeout": SQLITE_BUSY_TIMEOUT_MS / 1000,
            },
        )
        event.listen(_engine, "connect", apply_sqlite_pragmas)
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

    默认的高层动作事务边界。

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
    thread = threading.current_thread()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.exception(
            "session_scope 异常: stage=work_or_commit thread=%s tid=%s error=%s",
            thread.name,
            threading.get_ident(),
            type(e).__name__,
        )
        try:
            session.rollback()
        except Exception as rollback_error:
            logger.exception(
                "session_scope 回滚失败: thread=%s tid=%s error=%s",
                thread.name,
                threading.get_ident(),
                type(rollback_error).__name__,
            )
            raise
        raise
    finally:
        try:
            session.close()
        except Exception as close_error:
            logger.exception(
                "session_scope 关闭失败: thread=%s tid=%s error=%s",
                thread.name,
                threading.get_ident(),
                type(close_error).__name__,
            )
            raise
