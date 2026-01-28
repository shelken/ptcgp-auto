import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, MetaData, Table, select, insert

# 迁移脚本：将 Account.task_plan_id 迁移到 AccountTaskPlan 关联表


def migrate_task_plans():
    # script is in scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # go up one level to worktree root
    worktree_root = os.path.dirname(script_dir)

    db_path = os.path.join(worktree_root, "data", "ptcgp_v2.db")
    print(f"Target DB: {db_path}")

    if not os.path.exists(db_path):
        print("Database not found!")
        return

    engine = create_engine(f"sqlite:///{db_path}")
    metadata = MetaData()
    # metadata.reflect(bind=engine)  <-- Remove this

    # 获取表对象
    try:
        accounts_table = Table("accounts", metadata, autoload_with=engine)
    except Exception as e:
        print(f"Table 'accounts' not found: {e}")
        return

    # 检查是否存在 task_plan_id 列
    if "task_plan_id" not in accounts_table.columns:
        print(
            "Column 'task_plan_id' not found in 'accounts'. Migration might have already run."
        )
        return

    try:
        assoc_table = Table("account_task_plans", metadata, autoload_with=engine)
    except Exception as e:
        print(f"Table 'account_task_plans' not found: {e}")
        return

    with engine.connect() as conn:
        # 查找有 task_plan_id 的账号
        stmt = select(accounts_table.c.id, accounts_table.c.task_plan_id).where(
            accounts_table.c.task_plan_id.isnot(None)
        )
        results = conn.execute(stmt).fetchall()

        print(f"Found {len(results)} accounts with legacy task_plan_id")

        migrated_count = 0
        for account_id, plan_id in results:
            if plan_id is None:
                continue

            # 检查是否已存在关联
            check_stmt = select(assoc_table.c.id).where(
                assoc_table.c.account_id == account_id,
                assoc_table.c.task_plan_id == plan_id,
            )
            exists = conn.execute(check_stmt).first()

            if not exists:
                # 插入新关联
                ins_stmt = insert(assoc_table).values(
                    account_id=account_id,
                    task_plan_id=plan_id,
                    priority=0,
                    is_active=True,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                conn.execute(ins_stmt)
                migrated_count += 1
                print(f"Migrated Account {account_id} -> Plan {plan_id}")
            else:
                print(f"Skipping Account {account_id} (Association already exists)")

        conn.commit()

    print(f"Migration completed. {migrated_count} associations created.")


if __name__ == "__main__":
    migrate_task_plans()
