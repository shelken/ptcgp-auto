# -*- coding: utf-8 -*-

"""Web 模块测试公共 fixture。"""

import pytest
from sqlmodel import Session, SQLModel, create_engine


def _create_in_memory_engine():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture():
    """提供测试会话。"""
    engine = _create_in_memory_engine()
    with Session(engine) as session:
        yield session
