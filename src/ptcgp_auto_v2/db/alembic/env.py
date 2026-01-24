# -*- coding: utf-8 -*-
"""
Alembic 环境配置

配置 Alembic 与 SQLModel 集成，支持自动生成迁移脚本。
"""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlmodel import SQLModel

# 确保项目 src 目录在 sys.path 中
src_path = Path(__file__).resolve().parent.parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

# 导入所有模型以注册到 SQLModel.metadata
from ptcgp_auto_v2.db.models import *  # noqa: E402, F403

# Alembic Config 对象，提供对 .ini 文件中值的访问
config = context.config

# 配置 Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLModel 元数据，用于 autogenerate 支持
target_metadata = SQLModel.metadata


def get_url() -> str:
    """获取数据库 URL"""
    # 强制使用 settings 中的配置，忽略 alembic.ini 中的 sqlalchemy.url
    # 这样可以确保路径统一由 settings 管理（支持环境变量等）
    from ptcgp_auto_v2.config.settings import get_settings

    settings = get_settings()
    return f"sqlite:///{settings.db_path}"


def run_migrations_offline() -> None:
    """
    离线模式运行迁移

    仅配置 URL，不需要数据库连接。
    用于生成 SQL 脚本而不实际执行。
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite 需要批量模式支持 ALTER TABLE
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    在线模式运行迁移

    创建数据库引擎并执行迁移。
    """
    from sqlalchemy import create_engine, text

    url = get_url()
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        # [关键修复] 在 Batch 迁移前显式关闭 SQLite 外键约束
        # 防止表重命名时，SQLite 自动将外键引用更新到临时表 (_old)
        connection.execute(text("PRAGMA foreign_keys=OFF"))

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # SQLite 需要批量模式支持 ALTER TABLE
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
