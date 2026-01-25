# 数据库模块说明

本模块使用 **SQLModel** 作为 ORM 层

## 目录结构

```
db/
├── __init__.py          # 模块导出
├── engine.py            # 数据库引擎和会话管理
├── connection.py        # 旧的连接模块（仅用于初始化 schema）
├── repositories.py      # 数据访问层（Repository 模式）
├── models/              # SQLModel 模型定义
│   ├── __init__.py
│   ├── base.py          # 基础类和 Mixin
│   ├── account.py
│   ├── account_pack_config.py
│   ├── pack_record.py
│   ├── task_instance.py
│   └── task_plan.py

```
