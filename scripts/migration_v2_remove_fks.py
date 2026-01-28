import sys
import os
from sqlalchemy import create_engine, MetaData, select
from sqlmodel import SQLModel, Session

# 添加 src 到路径
sys.path.append(os.path.join(os.getcwd(), "src"))

# 导入所有模型以注册到 SQLModel.metadata
from ptcgp_auto_v2.db.models import *


def migrate():
    # 1. 配置路径
    # script is in scripts/
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # go up one level to worktree root
    worktree_root = os.path.dirname(script_dir)

    source_db_path = os.path.join(worktree_root, "data", "ptcgp_v2_source.db")
    target_db_path = os.path.join(worktree_root, "data", "ptcgp_v2_no_fk.db")

    print(f"Source DB: {source_db_path}")
    print(f"Target DB: {target_db_path}")

    if os.path.exists(target_db_path):
        os.remove(target_db_path)
        print("Removed existing target DB")

    # 2. 创建 Engine
    source_engine = create_engine(f"sqlite:///{source_db_path}")
    target_engine = create_engine(f"sqlite:///{target_db_path}")

    # 3. 在目标库创建表结构 (使用当前无 FK 的模型)
    print("Creating tables in target DB...")
    SQLModel.metadata.create_all(target_engine)

    # 4. 迁移数据
    # 使用 SQLAlchemy 反射获取源表结构
    source_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)

    # 获取目标表结构
    target_metadata = SQLModel.metadata

    with (
        Session(source_engine) as source_session,
        Session(target_engine) as target_session,
    ):
        # 遍历源数据库中的所有表
        for table_name in source_metadata.tables:
            if table_name not in target_metadata.tables:
                print(f"Skipping table {table_name} (not in target models)")
                continue

            print(f"Migrating table: {table_name}")
            source_table = source_metadata.tables[table_name]
            target_table = target_metadata.tables[table_name]

            # 读取源数据
            # 使用 .mappings() 获取字典格式，方便解包
            rows = source_session.execute(select(source_table)).mappings().all()

            if not rows:
                print(f"  - No data found")
                continue

            print(f"  - Copying {len(rows)} rows")

            # 批量插入
            # 过滤掉不在目标表中的列（防止源库有遗留字段）
            target_columns = set(c.name for c in target_table.columns)

            data_to_insert = []
            for row in rows:
                # 转换为字典并过滤
                row_dict = dict(row)
                clean_row = {k: v for k, v in row_dict.items() if k in target_columns}
                data_to_insert.append(clean_row)

            if data_to_insert:
                target_session.execute(target_table.insert(), data_to_insert)

        target_session.commit()

    print("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
