# -*- coding: utf-8 -*-
"""数据库 engine 连接复用测试。

这个文件负责验证 engine 连接复用修复。
覆盖连接池类型、跨线程并发访问、PRAGMA 保持和 session_scope 事务语义。
关键依赖是 Settings、get_engine 和 session_scope。
"""

from __future__ import annotations

from pathlib import Path
from threading import Barrier, Lock, Thread

import pytest
from sqlalchemy import text
from sqlalchemy.pool import QueuePool
from sqlmodel import Session

from ptcgp_auto_v2.config.settings import Settings, set_settings
from ptcgp_auto_v2.db import connection as connection_module
from ptcgp_auto_v2.db import engine as engine_module
from ptcgp_auto_v2.db.engine import get_engine, session_scope
from ptcgp_auto_v2.db.sqlite_config import SQLITE_BUSY_TIMEOUT_MS


def _prepare_probe_table():
    """变更前提交和回滚断言没有固定载体。变更后这里统一准备最小探针表。变更原因是让事务语义验证落在稳定的 SQL 目标上。"""
    with session_scope() as session:
        session.exec(
            text(
                """
                CREATE TABLE IF NOT EXISTS engine_pool_probe (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
        )
    with session_scope() as session:
        session.exec(text("DELETE FROM engine_pool_probe"))


@pytest.fixture
def isolated_engine(tmp_path: Path):
    """变更前 engine 测试会共享全局单例，连接池结果会互相污染。变更后这里为每个用例重绑独立数据库和单例状态。变更原因是只在干净环境里观察连接复用行为。"""
    original_settings = getattr(
        __import__("ptcgp_auto_v2.config.settings", fromlist=["_settings"]),
        "_settings",
    )
    original_engine = engine_module._engine
    original_db_instance = connection_module._db_instance

    engine_module._engine = None
    connection_module._db_instance = None

    settings = Settings(
        data_dir=tmp_path / "data",
        db_name="engine_pooling.db",
        auto_scale_emulators=False,
    )
    set_settings(settings)

    try:
        yield settings.db_path
    finally:
        current_engine = engine_module._engine
        if current_engine is not None and current_engine is not original_engine:
            current_engine.dispose()
        current_db_instance = connection_module._db_instance
        if (
            current_db_instance is not None
            and current_db_instance is not original_db_instance
        ):
            current_db_instance.close()
        engine_module._engine = original_engine
        connection_module._db_instance = original_db_instance
        set_settings(original_settings or Settings.from_env())


def test_engine_uses_queue_pool(isolated_engine):
    assert isolated_engine.name == "engine_pooling.db"
    engine = get_engine()

    assert isinstance(engine.pool, QueuePool)


def test_engine_handles_more_threads_than_previous_singleton_pool_limit(isolated_engine):
    assert isolated_engine.name == "engine_pooling.db"
    thread_count = 8
    barrier = Barrier(thread_count)
    errors: list[str] = []
    errors_lock = Lock()

    def _worker(worker_id: int):
        try:
            barrier.wait(timeout=5)
            with Session(get_engine()) as session:
                statement = text("SELECT :value").bindparams(value=worker_id)
                value = session.exec(statement).one()
                assert int(value[0]) == worker_id
        except Exception as exc:
            with errors_lock:
                errors.append(f"worker-{worker_id}:{type(exc).__name__}:{exc}")

    threads = [
        Thread(target=_worker, args=(worker_id,), name=f"db-pool-{worker_id}")
        for worker_id in range(thread_count)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        if thread.is_alive():
            errors.append(f"{thread.name}:Timeout:thread still alive")

    assert not errors


def test_sqlite_pragmas_remain_applied_when_connection_is_reused(isolated_engine):
    assert isolated_engine.name == "engine_pooling.db"
    with Session(get_engine()) as session:
        foreign_keys = session.exec(text("PRAGMA foreign_keys")).one()[0]
        journal_mode = session.exec(text("PRAGMA journal_mode")).one()[0]
        synchronous = session.exec(text("PRAGMA synchronous")).one()[0]
        busy_timeout = session.exec(text("PRAGMA busy_timeout")).one()[0]

    assert int(foreign_keys) == 0
    assert str(journal_mode).lower() == "wal"
    assert int(synchronous) == 1
    assert int(busy_timeout) == SQLITE_BUSY_TIMEOUT_MS


def test_session_scope_commit_and_rollback_semantics_unchanged(isolated_engine):
    assert isolated_engine.name == "engine_pooling.db"
    _prepare_probe_table()

    with session_scope() as session:
        session.exec(
            text(
                "INSERT INTO engine_pool_probe (id, value) VALUES (1, 'commit_path')"
            )
        )

    with Session(get_engine()) as session:
        committed_rows = session.exec(
            text(
                "SELECT COUNT(*) FROM engine_pool_probe WHERE value = 'commit_path'"
            )
        ).one()[0]

    with pytest.raises(RuntimeError, match="rollback_check"):
        with session_scope() as session:
            session.exec(
                text(
                    "INSERT INTO engine_pool_probe (id, value) VALUES (2, 'rollback_path')"
                )
            )
            raise RuntimeError("rollback_check")

    with Session(get_engine()) as session:
        rolled_back_rows = session.exec(
            text(
                "SELECT COUNT(*) FROM engine_pool_probe WHERE value = 'rollback_path'"
            )
        ).one()[0]

    assert int(committed_rows) == 1
    assert int(rolled_back_rows) == 0
