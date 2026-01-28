import os
import sys
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, Session

# 添加 src 到路径
script_dir = os.path.dirname(os.path.abspath(__file__))
worktree_root = os.path.dirname(script_dir)
src_path = os.path.join(worktree_root, "src")
sys.path.append(src_path)

from ptcgp_auto_v2.db.models import Account


def migrate_schema():
    db_path = os.path.join(worktree_root, "data", "ptcgp_v2.db")
    print(f"Target DB: {db_path}")

    if not os.path.exists(db_path):
        print("Database not found!")
        return

    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as session:
        # 1. 检查是否存在 task_plan_id 列
        try:
            result = session.exec(text("SELECT task_plan_id FROM accounts LIMIT 1"))
            result.first()
        except Exception:
            print(
                "Column 'task_plan_id' not found or table not exists. Migration might have already run."
            )
            return

        print("Starting schema migration...")

        # 2. 重命名旧表
        print("Renaming accounts -> accounts_old")
        session.exec(text("ALTER TABLE accounts RENAME TO accounts_old"))

        # 3. 创建新表 (使用当前的 SQLModel 定义，它应该已经没有 task_plan_id 了)
        print("Creating new accounts table...")
        # 为了只创建 accounts 表，我们可以使用 SQLModel.metadata.create_all，
        # 但这会尝试创建所有表。稍微低效但安全。
        # 或者我们可以直接提取 Account.__table__ 并创建。
        Account.__table__.create(engine)

        # 4. 复制数据
        print("Copying data...")
        # 获取新表的列名
        columns = [c.name for c in Account.__table__.columns]
        columns_str = ", ".join(columns)

        # 插入数据 (忽略 task_plan_id)
        insert_sql = f"INSERT INTO accounts ({columns_str}) SELECT {columns_str} FROM accounts_old"
        session.exec(text(insert_sql))

        # 5. 删除旧表
        print("Dropping accounts_old...")
        session.exec(text("DROP TABLE accounts_old"))

        session.commit()
        print("Schema migration completed successfully!")


if __name__ == "__main__":
    migrate_schema()
