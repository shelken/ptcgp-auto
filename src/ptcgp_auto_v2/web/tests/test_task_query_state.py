# -*- coding: utf-8 -*-
"""任务列表查询状态回归测试。"""

from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

import ptcgp_auto_v2.db.models  # noqa: F401
from ptcgp_auto_v2.web.services.task_service import build_task_list_render_context


@pytest.fixture
def session() -> Session:
    """为每个用例准备独立内存数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        yield session

    engine.dispose()


def test_build_task_list_render_context_exposes_filter_options(
    session: Session,
) -> None:
    context = build_task_list_render_context(
        session=session,
        page=-3,
        page_size=999,
        status=[],
        task_type=[],
        account_id=None,
        account_q="",
        sort_by="id",
        sort_order="asc",
        table_only=False,
    )

    assert context["page"] == 0
    assert context["page_size"] == 100
    assert context["filter_options"]["status"] == context["status_options"]
    assert context["filter_options"]["task_type"] == context["task_types"]
