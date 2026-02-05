# -*- coding: utf-8 -*-
"""
回填 TaskInstance.next_run_at。

运行方式：
python scripts/backfill_next_run_at.py
"""

from datetime import datetime
import os
import sys

from sqlmodel import Session, select

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import ptcgp_auto_v2.tasks

from ptcgp_auto_v2.core.task_plan_utils import (
    build_account_plan_cache,
    compute_next_run_for_instance,
)
from ptcgp_auto_v2.db.engine import get_engine
from ptcgp_auto_v2.db.models import TaskInstance
from ptcgp_auto_v2.db.repositories import AccountRepository


def main() -> None:
    """回填 next_run_at 字段。"""
    account_repo = AccountRepository()
    accounts = account_repo.get_accounts_with_plans()
    if not accounts:
        print("未找到账号，跳过回填")
        return

    with Session(get_engine()) as session:
        updated = 0
        for account in accounts:
            if account.id is None:
                continue
            cache = build_account_plan_cache(account)
            statement = select(TaskInstance).where(
                TaskInstance.account_id == account.id
            )
            instances = session.exec(statement).all()
            for instance in instances:
                next_run_at, _, _, _ = compute_next_run_for_instance(instance, cache)
                instance.next_run_at = next_run_at
                instance.updated_at = datetime.now()
                session.add(instance)
                updated += 1
        session.commit()

    print(f"回填完成，共更新 {updated} 条任务实例")


if __name__ == "__main__":
    main()
