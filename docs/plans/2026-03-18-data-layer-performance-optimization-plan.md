# Data Layer Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不改变 v2 业务行为的前提下，重构数据库访问模型，减少无意义的 session/连接创建、消除高频 N+1 查询，并把调度与执行热路径收敛到可维护的数据层接口。

**Architecture:** 当前性能瓶颈不在单个 SQL，而在“每个 repo 方法自开 session + 模型方法偷偷写库 + 调度器按账号逐个查库”的整体访问模型。优化顺序必须先统一 session 边界，再重写热路径查询，最后再回收 Web 侧和业务侧零散 N+1；否则只是局部修补，后续还会继续回退成碎片化访问。

**Tech Stack:** Python 3.12、SQLModel、SQLAlchemy、SQLite、现有 Repository 模式、Scheduler/Executor 任务框架

---

### 目标边界

- 只处理 `src/ptcgp_auto_v2/` 的数据层与其直接调用方。
- 不修改 v1。
- 不改变表结构，不引入 Alembic。
- 不改变业务语义，不再引入新的事务边界写法。
- 允许重写 repo 接口、删除模型层 `save()` 之类的坏入口，并同步修改全部调用点。

### 当前已落地事实（2026-03-18）

- `TaskInstance.save()` 已删除，模型层不再直接写库。
- `RepositoryFactory(session)` 已落地，用于单个高层动作内组装多个 Repository。
- 核心 repo 已删除 `with Session(get_engine())` 写法，Repository 方法内部不再自建 Session。
- 当前标准已经统一为：
  - 高层动作默认使用 `session_scope()`
  - 所有 Repository 构造都必须显式传入 `session`
  - 需要多个 Repository 时统一通过 `RepositoryFactory(session)` 组装
- `BaseRepository._finish_write()` 当前语义：
  - 只执行 `flush()`
  - 不负责 `commit()`
- `get_session()` / `get_fastapi_session()` 使用 SQLAlchemy 默认的提交后过期语义
- `session_scope()` 只在存在写入时提交，纯查询路径不主动提交

### 改造前基线热点

- `138` 处 `with Session(get_engine())`，数据库访问过于碎片化。
- `142` 处 `Repository()` 直接创建，依赖关系分散。
- `TaskInstance.save()` 这类模型方法会隐藏一次额外查库与写库。
- `Scheduler` 的派发与生成逻辑存在明显 N+1。
- 多个 Web 服务层存在全量加载后再逐项查询的问题。

### 文件边界

**核心数据层**

- Modify: `src/ptcgp_auto_v2/db/engine.py`
- Modify: `src/ptcgp_auto_v2/db/models/task_instance.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/friend_request_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/friendship_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_plan_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/pack_record_repository.py`

**核心热路径调用方**

- Modify: `src/ptcgp_auto_v2/core/scheduler.py`
- Modify: `src/ptcgp_auto_v2/core/executor.py`
- Modify: `src/ptcgp_auto_v2/services/friendship_service.py`
- Modify: `src/ptcgp_auto_v2/services/gift_record_service.py`
- Modify: `src/ptcgp_auto_v2/services/exchange_card_service.py`
- Modify: `src/ptcgp_auto_v2/infra/account_syncer.py`
- Modify: `src/ptcgp_auto_v2/utils/pack_auto_selector.py`

**第二阶段 Web 调用方**

- Modify: `src/ptcgp_auto_v2/web/services/owned_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_sync_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/record_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/plan_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/account_service.py`

### 执行顺序总览

1. 先建立统一 session 边界与 repo 基线。
2. 再删除模型层隐藏写库入口。
3. 再改 Scheduler/Executor 热路径查询。
4. 再改服务层和脚本层 repo 复用。
5. 最后清理 Web 侧 N+1 和全量加载。

## Chunk 1: 数据层基线与访问模型冻结

### Task 1: 盘点当前 session 与 repo 创建模式

**Files:**
- Modify: `docs/plans/2026-03-18-data-layer-performance-optimization-plan.md`
- Inspect: `src/ptcgp_auto_v2/db/**/*.py`
- Inspect: `src/ptcgp_auto_v2/core/**/*.py`
- Inspect: `src/ptcgp_auto_v2/services/**/*.py`
- Inspect: `src/ptcgp_auto_v2/web/services/**/*.py`

- [ ] 统计所有 `with Session(get_engine())`、`Repository()`、模型 `.save()` 调用点，确认迁移范围。
- [ ] 按“调度热路径 / 执行热路径 / Web 查询 / 一次性脚本”四类整理调用方。
- [ ] 明确本次不处理表结构与索引，只处理访问模型与查询形态。

**验收标准**

- 有一份完整迁移边界，不允许后续边改边猜。

### Task 2: 冻结新的访问原则

**Files:**
- Modify: `src/ptcgp_auto_v2/db/README.md`
- Modify: `AGENTS.md`

- [ ] 写明新的硬规则：
  - 业务对象、模型对象禁止自己 new repo 并写库。
  - repo 不允许在已传入 `session` 的路径里自己 `commit`。
  - 长生命周期组件必须在构造时持有 repo。
  - 一个高层业务动作只允许一个明确的 session 边界。

**验收标准**

- 后续重构不再出现“代码改回旧写法”的口子。

## Chunk 2: 统一 session 生命周期

### Task 3: 建立明确的 session 获取入口

**Files:**
- Modify: `src/ptcgp_auto_v2/db/engine.py`

- [ ] 保留 `get_engine()` 单例。
- [ ] 明确保留两个入口：
  - `get_session()`：裸 session，仅供显式管理生命周期的调用方使用。
  - `session_scope()`：高层动作边界统一入口。
- [ ] 删除或禁止继续扩散“repo 方法内部自建事务边界”的写法。
- [ ] 在文档中写清楚 `session_scope()` 是默认高层动作入口。

**验收标准**

- 后续 repo 可以接收外部 session，不再被迫每次自开。

### Task 4: 所有 repo 改为显式持有 session

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/account_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/friend_request_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/friendship_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_plan_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/pack_record_repository.py`

- [ ] 所有 repo 构造函数统一接收 `session: Session`。
- [ ] 删除 repo 方法内部 `with Session(get_engine())`。
- [ ] 对“只读”和“写入”方法保持显式语义，不在 repo 内部再开新 session；显式传入 `session` 时不得自己 `commit`。
- [ ] 保持接口足够小，不保留双轨 session 入口。

**验收标准**

- 代码库内核心 repo 不再出现 `with Session(get_engine())`。

### Task 5: 提供 repo 组装入口，避免调用方手写一堆构造

**Files:**
- Create: `src/ptcgp_auto_v2/db/repositories/factory.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/__init__.py`

- [ ] 新增单一工厂，按 session 生成需要的 repo 集合。
- [ ] 工厂只做组装，不做业务逻辑。
- [ ] 避免每个调用方都手写十几个 `XxxRepository(session)`。

**验收标准**

- 构造 repo 的代码收敛到一个地方。

## Chunk 3: 删除模型层隐藏持久化

### Task 6: 移除 `TaskInstance.save()` 这类模型写库入口

**Files:**
- Modify: `src/ptcgp_auto_v2/db/models/task_instance.py`
- Search/Modify: `src/ptcgp_auto_v2/**/*.py`

- [ ] 删除 `TaskInstance.save()`。
- [ ] 全库替换所有 `instance.save()` 调用，改为明确 repo 调用。
- [ ] 禁止模型对象依赖 `repositories` 包。

**验收标准**

- 模型层只表达数据，不负责数据库访问。

### Task 7: 清理“模型对象驱动 repo”的剩余坏入口

**Files:**
- Search/Modify: `src/ptcgp_auto_v2/db/models/**/*.py`
- Search/Modify: `src/ptcgp_auto_v2/**/*.py`

- [ ] 搜索其余模型上是否还有 `save/update/delete` 一类数据库入口。
- [ ] 一律删除，并同步修改调用方。

**验收标准**

- 数据流方向固定为 `service/core -> repo -> model`，不允许反向依赖。

## Chunk 4: 调度热路径重写

### Task 8: 改造 Scheduler 的 session 边界

**Files:**
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`

- [ ] 调度循环中按“单轮 loop”或“单个高层动作”建立 session_scope。
- [ ] `Scheduler` 构造时持有 repo 工厂或 repo provider，而不是持有长期绑定旧 session 的 repo 实例。
- [ ] 保证线程边界清晰，禁止跨线程共享同一个 session。

**验收标准**

- 调度器中 repo 生命周期明确，线程安全边界明确。

### Task 9: 合并派发查询，消除账号级 N+1

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_repository.py`
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`

- [ ] 新增“直接返回下一批可派发账号及其待执行任务”的批量查询接口。
- [ ] 删除 `_get_next_account_batch()` 中的逐账号：
  - `get_pending_by_account`
  - `has_running_tasks`
  - `get_by_id`
- [ ] 把 init_account 优先级、running 排除、pending 排序都尽量前移到查询层。

**验收标准**

- 选出下一账号批次不再按账号做多次 round-trip。

### Task 10: 合并任务生成逻辑，避免逐任务 `get_or_create`

**Files:**
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_repository.py`

- [ ] 查询“所有账号 + 已有 task_instance 状态”时一次性拿齐需要的数据。
- [ ] 在内存完成计划聚合后，按账号批量 upsert task_instance。
- [ ] 删除每个任务类型一次 `get_or_create` 的调用模式。

**验收标准**

- 任务生成阶段的数据库往返量与“账号数 × 任务数”脱钩。

## Chunk 5: 执行器与服务层收敛

### Task 11: Executor 中的任务状态更新改成单 session 收口

**Files:**
- Modify: `src/ptcgp_auto_v2/core/executor.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`

- [ ] 任务开始、完成、失败、解锁依赖任务时，统一在明确 session 下完成。
- [ ] 删除 `_get_or_create_task_instance()`、`_unblock_dependent_tasks()` 中的临时 repo new。
- [ ] 保证单次任务执行的状态流转尽量使用同一 session。

**验收标准**

- 执行器不再在状态更新路径里频繁自建 repo/session。

### Task 12: 服务层改为构造注入 repo

**Files:**
- Modify: `src/ptcgp_auto_v2/services/friendship_service.py`
- Modify: `src/ptcgp_auto_v2/services/gift_record_service.py`
- Modify: `src/ptcgp_auto_v2/services/exchange_card_service.py`
- Modify: `src/ptcgp_auto_v2/infra/account_syncer.py`
- Modify: `src/ptcgp_auto_v2/utils/pack_auto_selector.py`

- [ ] 静态方法服务重构为显式依赖注入的实例服务，或收口到单个高层函数内部统一创建 repo。
- [ ] 删除服务方法内部多次 `XxxRepository()`。
- [ ] 对跨多步数据库写入的逻辑使用单一 session。

**验收标准**

- 服务层的数据库访问关系从“散点式”变成“可追踪”。

## Chunk 6: Web 侧查询优化

### Task 13: 清理已确认的 Web N+1

**Files:**
- Modify: `src/ptcgp_auto_v2/web/services/owned_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_sync_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/record_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/plan_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/account_service.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/account_card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`

- [ ] `owned_card_service` 中把 `has_active_request(account_id)` 改成批量查询。
- [ ] `metadata_service` / `metadata_sync_service` 中把 `sum(len(repo.get_cards_by_set(...)))` 改成单 SQL 聚合。
- [ ] `record_service` 中把 set/pack 标签映射的获取方式改成更窄的范围，避免每次列表页全量加载。
- [ ] `plan_service` / `account_service` 检查是否存在全量计划/账号再内存筛选，能前推到 SQL 的前推。

**验收标准**

- Web 页面渲染不再一页触发一串无意义小查询。

## Chunk 7: 验证与回归基线

### Task 14: 建立最小验证矩阵

**Files:**
- Modify: `docs/plans/2026-03-18-data-layer-performance-optimization-plan.md`

- [ ] 每完成一个 chunk 都执行：
  - `uv run ruff check <modified-files>`
  - `TMPDIR=/tmp pyright --level error <modified-files>`
- [ ] 每完成核心数据层改造后执行：
  - `PYTHONPATH=src uv run python main_v2.py --list-plans`
  - `PYTHONPATH=src uv run python main_v2.py --list-accounts`
- [ ] 每完成调度器改造后执行：
  - `PYTHONPATH=src uv run python main_v2.py --daemon --help`
  - 在本地已有数据上做一次最小启动 smoke check。
- [ ] 每完成 Web 查询改造后执行：
  - `PYTHONPATH=src uv run python src/ptcgp_auto_v2/web/app.py` 的最小导入验证
  - 打开关键页面做手动 smoke check。

**验收标准**

- 每个阶段都有最小可运行证据，而不是最后一起赌。

### Task 15: 用指标确认收益

**Files:**
- Modify: `docs/plans/2026-03-18-data-layer-performance-optimization-plan.md`

- [ ] 记录改造前后指标：
  - 单次调度 loop 的 SQL 次数
  - 单次任务完成路径的 SQL 次数
  - `owned_cards` / `records` / `metadata` 页面请求的 SQL 次数
- [ ] 若某阶段代码变复杂但 SQL 次数没有明显下降，停止继续堆代码，先回头重构方案。

**验收标准**

- 本次优化以“实际查询次数下降”为完成标准，不以“接口更优雅”自我感动。

## 优先级与里程碑

### P0

- Task 3
- Task 4
- Task 6
- Task 8
- Task 9

### P1

- Task 10
- Task 11
- Task 12

### P2

- Task 13
- Task 15

## 回滚原则

- 若 `Scheduler` 重写后出现任务派发顺序变化，先回滚该 chunk，不连带回滚 repo 基线。
- 若 Web 查询优化引入页面语义变化，先回滚页面层改动，不回滚数据层 session 改造。
- 禁止整仓回滚，按 chunk 回滚。

## 完成定义

- `src/ptcgp_auto_v2/db/repositories/` 核心 repo 不再出现 `with Session(get_engine())`。
- `src/ptcgp_auto_v2/db/models/` 不再出现模型层持久化入口。
- `Scheduler` 派发和任务生成不再按账号做多轮 N+1 查询。
- 关键 Web 列表页的已知 N+1 被收掉。
- 所有改动文件通过 `uv run ruff check`，核心文件通过 `pyright --level error`。

Plan complete and saved to `docs/plans/2026-03-18-data-layer-performance-optimization-plan.md`. Ready to execute?
