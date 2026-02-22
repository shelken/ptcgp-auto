# -*- coding: utf-8 -*-

"""Web 模块测试公共 fixture。"""

import importlib
import pkgutil

import pytest
from sqlmodel import Session, SQLModel, create_engine


def _create_in_memory_engine():
    """创建内存数据库引擎。"""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return engine


def _patch_repository_engines_to_memory(
    monkeypatch: pytest.MonkeyPatch, engine
) -> None:
    """将仓储层 get_engine 统一指向内存数据库，避免触达真实库。"""
    monkeypatch.setattr("ptcgp_auto_v2.db.engine.get_engine", lambda: engine)

    repositories_pkg = importlib.import_module("ptcgp_auto_v2.db.repositories")
    for module_info in pkgutil.iter_modules(repositories_pkg.__path__):
        module_name = f"ptcgp_auto_v2.db.repositories.{module_info.name}"
        module = importlib.import_module(module_name)
        if hasattr(module, "get_engine"):
            monkeypatch.setattr(module, "get_engine", lambda: engine)


@pytest.fixture(name="session")
def session_fixture(memory_engine):
    """提供测试会话。"""
    with Session(memory_engine) as session:
        yield session


@pytest.fixture(name="memory_engine", autouse=True)
def memory_engine_fixture(monkeypatch):
    """所有 web 测试默认强制使用内存数据库引擎。"""
    engine = _create_in_memory_engine()
    _patch_repository_engines_to_memory(monkeypatch, engine)
    return engine
