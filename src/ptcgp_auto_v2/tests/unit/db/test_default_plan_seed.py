# -*- coding: utf-8 -*-
"""默认任务计划 seed 测试。

验证 Database 初始化时空库写入的 base 计划:
- 默认开启 3 个低风险日常任务, 让新用户开箱即用
- 任务类型与间隔配置与生产环境一致
- INSERT OR IGNORE 幂等, 重复实例化不重复写入
"""

from __future__ import annotations

import json

from sqlmodel import Session, create_engine
from sqlalchemy import text

from ptcgp_auto_v2.db.connection import Database


def _new_database(tmp_path):
    """在临时路径建一个全新 Database, 触发完整 _init_schema + _init_default_data。"""
    db_path = tmp_path / "default_plan.db"
    # Database 实例化内部会用 create_engine 建表 + seed 默认数据
    # 用独立 engine 测试, 避免污染全局单例
    db = Database(db_path=db_path)
    return db


def test_init_seeds_base_plan_with_three_default_tasks(tmp_path):
    """空库 init 后 base 计划应含 fetch_account_info/open_pack/collect_account_cards 三个任务。"""
    db = _new_database(tmp_path)

    engine = create_engine(f"sqlite:///{db.db_path}")
    with Session(engine) as session:
        row = session.exec(
            text("SELECT name, task_types FROM task_plans WHERE name='base'")
        ).first()

    assert row is not None, "base 计划未被写入"
    name, task_types_json = row
    assert name == "base"

    task_types = json.loads(task_types_json)
    assert task_types == ["fetch_account_info", "open_pack", "collect_account_cards"]


def test_init_base_plan_has_production_intervals(tmp_path):
    """base 计划的间隔配置应与生产环境一致: 日常任务 24h, 扫卡 7 天。"""
    db = _new_database(tmp_path)

    engine = create_engine(f"sqlite:///{db.db_path}")
    with Session(engine) as session:
        row = session.exec(
            text("SELECT configuration FROM task_plans WHERE name='base'")
        ).first()

    assert row is not None
    config = json.loads(row[0])

    # 日常任务 24 小时间隔
    assert config["fetch_account_info"] == {"reset_type": "interval", "interval_seconds": 86400}
    assert config["open_pack"] == {"reset_type": "interval", "interval_seconds": 86400}
    # 扫卡 7 天间隔
    assert config["collect_account_cards"] == {"reset_type": "interval", "interval_seconds": 604800}


def test_init_is_idempotent(tmp_path):
    """重复实例化 Database (重新 init) 不应产生重复 base 计划。"""
    db_path = tmp_path / "default_plan.db"

    # 首次建库
    Database(db_path=db_path)
    # 模拟程序重启, 在同一文件上再跑一次 init
    Database(db_path=db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        count = session.exec(
            text("SELECT COUNT(*) FROM task_plans WHERE name='base'")
        ).first()

    assert count is not None
    assert count[0] == 1, "重复 init 后 base 计划应为 1 行"
