# 数据库模块说明

本模块使用 **SQLModel** 作为 ORM 层，**Alembic** 管理数据库迁移。

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
├── alembic.ini          # Alembic 配置
└── alembic/
    ├── env.py           # Alembic 环境配置
    ├── script.py.mako   # 迁移脚本模板
    └── versions/        # 迁移版本文件
```

## 常用操作

### 运行 Alembic 命令

所有 Alembic 命令需要在 `db/` 目录下执行，并设置 `PYTHONPATH`：

```bash
cd src/ptcgp_auto_v2/db
export PYTHONPATH=../../../src

# 或者每次命令前加上
PYTHONPATH=../../../src alembic <command>
```

### 查看当前迁移版本

```bash
alembic current
```

### 查看迁移历史

```bash
alembic history
```

## 添加新模型

1. **创建模型文件** `models/new_model.py`：

```python
# -*- coding: utf-8 -*-
"""
NewModel 模型

模型说明...
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class NewModel(SQLModel, table=True):
    """新模型"""

    __tablename__ = "new_models"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.now)
```

2. **在 `models/__init__.py` 中导出**：

```python
from .new_model import NewModel

__all__ = [
    # ... 其他模型
    "NewModel",
]
```

3. **在 `alembic/env.py` 中导入**（确保模型注册到 metadata）：

```python
from ptcgp_auto_v2.db.models import (
    # ... 其他模型
    NewModel,
)
```

4. **生成迁移脚本**：

```bash
alembic revision --autogenerate -m "add new_model table"
```

5. **检查生成的迁移脚本**（在 `alembic/versions/` 目录下），确认无误后执行：

```bash
alembic upgrade head
```

## 修改现有模型（Schema 变更）

1. **修改模型文件**，例如添加字段：

```python
class Account(SQLModel, table=True):
    # ... 现有字段
    new_field: Optional[str] = None  # 新增字段
```

2. **生成迁移脚本**：

```bash
alembic revision --autogenerate -m "add new_field to accounts"
```

3. **检查并执行迁移**：

```bash
# 检查生成的脚本
cat alembic/versions/<revision>_add_new_field_to_accounts.py

# 执行迁移
alembic upgrade head
```

## 回滚迁移

```bash
# 回滚到上一个版本
alembic downgrade -1

# 回滚到指定版本
alembic downgrade <revision>

# 回滚所有
alembic downgrade base
```

## 注意事项

1. **SQLite 限制**：SQLite 不支持部分 ALTER TABLE 操作，Alembic 使用 `render_as_batch=True` 模式处理（重建表）。

2. **时间字段**：统一使用本地时间 `datetime.now()`，不使用 UTC。

3. **JSON 字段**：如 `TaskPlan.task_types` 存储为 JSON 字符串，通过 `task_types_list` 属性获取解析后的列表。

4. **关系加载**：SQLModel 默认懒加载，访问关系属性时会触发额外查询。如需批量加载，使用 `selectinload` 或手动预加载。

5. **Session 生命周期**：Repository 方法内部创建和关闭 Session，返回的对象是 detached 状态。如需在 Session 外修改并保存，需重新查询或使用 `session.merge()`。
