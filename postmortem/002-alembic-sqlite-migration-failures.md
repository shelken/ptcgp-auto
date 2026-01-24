# 002-Alembic SQLite 迁移连环失败分析

## 基本信息

- **严重级别**：P1 (阻塞开发流程)
- **发现时间**：2026-01-24
- **组件**：Database (SQLite + Alembic + SQLModel)

## 事故概述

在集成卡牌识别与数据持久化功能时，执行数据库迁移 (`alembic upgrade head`) 遭遇了连续的失败。问题涉及循环依赖、模板配置缺失、SQLite 约束命名限制以及脏数据清理，导致开发过程中断且产生挫败感。

## 原因分析与修复

### 1. 循环依赖 (Circular Import)
- **现象**：运行任务时报错 `ImportError`。
- **原因**：`utils/card_naming.py` 导入了 `db/models.py` 用于类型提示，而 `db` 层又依赖 `utils`，形成闭环。
- **修复**：重构 `get_card_filename`，将参数从 `Card` 对象改为基础类型 `(number, name)`，解除耦合。

### 2. 迁移脚本缺失导入 (NameError)
- **现象**：`NameError: name 'sqlmodel' is not defined`。
- **原因**：Alembic 自动生成的脚本使用了 `sqlmodel.AutoString`，但未自动添加 `import sqlmodel`。
- **根因**：Alembic 的生成模板 `script.py.mako` 默认只有 sqlalchemy。
- **修复**：修改 `src/ptcgp_auto_v2/db/alembic/script.py.mako`，永久添加 `import sqlmodel`。

### 3. SQLite 约束命名缺失 (ValueError)
- **现象**：`ValueError: Constraint must have a name`。
- **原因**：SQLite 不支持对匿名约束进行 `DROP` 操作。Alembic 在 `batch_alter_table` 模式下要求所有约束必须有名字。
- **修复**：手动修改迁移脚本，移除了所有会导致报错的 `drop_constraint` 语句（在 SQLite 批处理模式下，重建表时会自动丢弃旧约束，无需显式删除）。

### 4. 脏状态残留 (OperationalError)
- **现象**：`table pack_cards already exists` 或 `table _alembic_tmp_... already exists`。
- **原因**：由于 SQLite DDL 不支持事务回滚，迁移脚本中途失败后，已创建的表（正式表或临时表）遗留在数据库中，阻碍下一次运行。
- **修复**：编写 Python 脚本手动清理所有 `_alembic_tmp_` 开头的表及目标表。

## 经验教训

### 需要改进的地方
1.  **SQLite 的脆弱性**：在 SQLite 上做复杂的 Schema 变更（尤其是改约束）极其痛苦。应尽早配置 **SQLAlchemy Naming Convention**，确保所有约束在创建时就有确定性的名字，避免 `drop_constraint` 找不到名字的问题。
2.  **清理机制**：在迁移失败后，应意识到 SQLite 环境可能残留脏数据，优先检查并清理 `_alembic_tmp_` 表。
3.  **模板管理**：项目初始化时应立即检查 Alembic 模板，确保包含项目特有的依赖（如 SQLModel）。

## 预防措施

1.  **配置自动命名规则**：在 `models.py` 的 metadata 中配置 `naming_convention`，一劳永逸解决约束名问题。
2.  **脚本化清理**：编写一个 `make clean-db-state` 脚本，用于自动清理 Alembic 的临时表，减少手动操作。
