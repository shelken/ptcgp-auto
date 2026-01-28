# 移除 Account.task_plan_id 设计文档

**日期:** 2026-01-28
**状态:** 已完成
**作者:** Antigravity

## 1. 概述

目标是移除旧的 `Account.task_plan_id` 字段（一对一关系），并完全迁移到 `AccountTaskPlan`（多对多关系），以支持灵活的任务调度。

## 2. 迁移策略

### 2.1 数据迁移
在修改模式之前，我们必须迁移现有数据以防止丢失。

**脚本逻辑:**
1. 遍历所有 `Account` 记录。
2. 如果设置了 `account.task_plan_id`:
   - 检查该 `(account_id, task_plan_id)` 对是否已存在 `AccountTaskPlan` 条目。
   - 如果不存在，创建一个新的 `AccountTaskPlan`:
     - `priority = 0`
     - `is_active = True`
   - 记录迁移数量。

### 2.2 Schema 迁移 (SQLite)
由于 SQLite 在旧版本中不支持直接使用 `DROP COLUMN`（且 SQLAlchemy/Alembic 在没有正确设置的情况下支持可能比较棘手），我们将使用 **"Copy and Swap"** 方法：

1. 创建不含 `task_plan_id` 的新表 `accounts_new`。
2. 将数据从 `accounts` 复制到 `accounts_new`。
3. 删除表 `accounts`。
4. 将 `accounts_new` 重命名为 `accounts`。
5. 重建索引。

*注意：由于我们使用 SQLModel，如果我们删除表，可以依赖 SQLModel 重新创建表，但为了数据保存，手动迁移更安全。*

## 3. 代码重构

### 3.1 `src/ptcgp_auto_v2/db/models/account.py`
- 移除 `task_plan_id` 字段。
- 移除 `task_plan` 关系。
- 保留 `task_plan_associations`。

### 3.2 `src/ptcgp_auto_v2/core/scheduler.py`

**`_aggregate_account_plans`**:
- 移除步骤 1（处理 `account.task_plan`）。
- 仅遍历 `account.task_plan_associations`，按优先级排序。

**`_order_tasks_by_plan`**:
- 通过查找优先级最高的活动关联来确定“主计划”。
- 使用 `primary_plan.task_types_list` 进行排序。

### 3.3 `src/ptcgp_auto_v2/db/repositories/account_repository.py`
- `create`: 代替设置 `task_plan_id`，创建 `AccountTaskPlan` 关联。
- `assign_task_plan`: 更新以修改 `AccountTaskPlan`。
- `get_by_id`: 从加载器选项中移除 `task_plan`，确保加载 `task_plan_associations`。

### 3.4 `src/ptcgp_auto_v2/web/app.py`
- 搜索并替换所有使用 `account.task_plan_id` 的地方。
- 更新设置/获取任务计划的 API 端点以使用新的关联结构。

## 4. 实施步骤

1. **备份数据库**: 将 `data/ptcgp_v2.db` 复制到 `data/ptcgp_v2.db.bak`。
2. **运行数据迁移**: 执行 Python 脚本填充 `AccountTaskPlan`。
3. **重构代码**: 应用更改到模型、调度器、仓库和 Web 应用。
4. **重建表**: 由于我们要“删除列”，并且我们有迁移脚本，我们可以实际上：
   - 运行数据迁移脚本（填充 AccountTaskPlan）。
   - 停止应用。
   - 手动或通过脚本删除 `accounts` 表。
   - 让应用（SQLModel）在启动时重新创建 `accounts` 表（此时将为空）。
   - **等等**，这会丢失账号数据！
   - **更正**: 我们必须使用 "Copy and Swap" SQL 脚本或正确处理模式更改的 Python 脚本。

## 5. 验证
- 验证所有账号至少有一个 `AccountTaskPlan`（如果之前有计划的话）。
- 验证调度器根据最高优先级计划正确排序任务。
- 验证 Web UI 仍可查看和编辑计划。
