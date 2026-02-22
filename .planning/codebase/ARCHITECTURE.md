# Architecture

**Analysis Date:** 2026-02-23

## Pattern Overview

**Overall:** 任务队列 + 调度器架构 (Task Queue + Scheduler Pattern)

**Key Characteristics:**
- 目标驱动 + 页面响应的自动化执行模式
- 多账号、多设备并发调度
- Hook 机制实现任务间依赖与条件执行
- Web UI (FastAPI + HTMX) 提供管理界面

## Layers

**核心调度层 (Core Layer):**
- Purpose: 任务调度、执行、状态管理
- Location: `src/ptcgp_auto_v2/core/`
- Contains: Scheduler, Executor, TaskBase, DevicePool, Hooks
- Depends on: infra 层、db 层、config 层
- Used by: main.py 入口

**基础设施层 (Infrastructure Layer):**
- Purpose: 设备控制、识别、页面检测
- Location: `src/ptcgp_auto_v2/infra/`
- Contains: AdbController, OcrEngine, TemplateMatcher, PageDetector, AccountSwitcher
- Depends on: config 层、外部库 (uiautomator2, vision)
- Used by: core 层、tasks 层

**任务实现层 (Tasks Layer):**
- Purpose: 具体自动化任务的业务逻辑
- Location: `src/ptcgp_auto_v2/tasks/`
- Contains: 10 个任务实现 + utils 工具
- Depends on: core 层、infra 层、db 层、services 层
- Used by: Executor 调度执行

**业务服务层 (Services Layer):**
- Purpose: 跨任务的业务逻辑封装
- Location: `src/ptcgp_auto_v2/services/`
- Contains: ExchangeCardService, FriendshipService, GiftPairingService, GiftRecordService
- Depends on: db 层
- Used by: tasks 层、hooks 层

**数据访问层 (Database Layer):**
- Purpose: 数据模型定义与持久化
- Location: `src/ptcgp_auto_v2/db/`
- Contains: 17 个 SQLModel 模型 + 14 个 Repository
- Depends on: SQLModel、SQLite
- Used by: core 层、tasks 层、services 层、web 层

**Web 服务层 (Web Layer):**
- Purpose: 管理界面与 REST API
- Location: `src/ptcgp_auto_v2/web/`
- Contains: FastAPI app, routers, services, queries, templates
- Depends on: db 层、config 层
- Used by: 用户通过浏览器访问

**配置层 (Config Layer):**
- Purpose: 运行时配置与常量定义
- Location: `src/ptcgp_auto_v2/config/`
- Contains: settings, constants, pages, rarity_icons
- Depends on: 无
- Used by: 所有层

## Data Flow

**任务调度流程:**

1. Scheduler 主循环轮询 (`_main_loop`)
2. 检查任务计划，生成 TaskInstance (`_generate_pending_tasks`)
3. 获取空闲设备 (`DevicePool.acquire_for_account`)
4. 分配任务到 AccountBatchExecutor (`_dispatch_account_batch`)
5. Executor 初始化组件、切换账号、执行任务
6. 任务执行采用页面响应模式 (`Task.execute`)
7. 状态更新与结果持久化

**页面响应流程:**

1. 调用 `PageDetector.detect()` 识别当前页面
2. 根据 page_name 路由到对应 handler
3. Handler 执行操作 (点击、滑动等)
4. 返回 ActionResult (成功/失败/等待时间)
5. 循环直到 `is_completed()` 返回 True

**Hook 执行流程:**

1. 任务执行前调用 `_run_pre_hooks()`
2. Hook 返回 HookResult (CONTINUE/ABORT/INSERT_TASK/DELAY/SKIP)
3. INSERT_TASK: 递归执行前置任务
4. DELAY: 重排任务到指定时间
5. 任务完成后调用 `_run_post_hooks()`

## Key Abstractions

**Task (任务基类):**
- Purpose: 定义可插拔任务的接口规范
- Examples: `src/ptcgp_auto_v2/tasks/open_pack.py`, `src/ptcgp_auto_v2/tasks/claim_rewards.py`
- Pattern: 模板方法模式 + 注册表模式
- 核心方法: `is_completed()`, `handle_page()`, `execute()`
- 使用 `@TaskRegistry.register("task_type")` 装饰器注册

**Scheduler (调度器):**
- Purpose: 管理设备池、生成任务、分配执行
- Examples: `src/ptcgp_auto_v2/core/scheduler.py`
- Pattern: 生产者-消费者模式
- 关键职责: 任务生成、设备管理、异常恢复、自动扩缩容

**Executor (执行器):**
- Purpose: 在设备上执行任务
- Examples: `src/ptcgp_auto_v2/core/executor.py`
- Pattern: 策略模式 (TaskExecutor vs AccountBatchExecutor)
- 关键职责: 组件初始化、账号切换、任务执行、状态更新

**Hook (钩子):**
- Purpose: 在任务执行前后插入自定义逻辑
- Examples: `src/ptcgp_auto_v2/hooks/exchange_hooks.py`, `src/ptcgp_auto_v2/hooks/gift_hooks.py`
- Pattern: 责任链模式
- 核心方法: `run(context) -> (HookResult, data)`

**Repository (仓储):**
- Purpose: 数据访问抽象
- Examples: `src/ptcgp_auto_v2/db/repositories/account_repository.py`
- Pattern: Repository 模式
- 关键方法: `get_by_id()`, `get_all()`, `save()`, 自定义查询方法

## Entry Points

**CLI 入口:**
- Location: `main_v2.py`
- Triggers: 用户命令行调用
- Responsibilities: 解析参数、初始化配置、启动调度器或 Web 服务

**调度器入口:**
- Location: `src/ptcgp_auto_v2/main.py::main()`
- Triggers: CLI 入口调用
- Responsibilities: 设备发现、数据库初始化、启动守护模式或单任务

**Web 入口:**
- Location: `src/ptcgp_auto_v2/web/app.py`
- Triggers: uvicorn 启动
- Responsibilities: FastAPI 应用初始化、路由挂载、静态资源服务

## Error Handling

**Strategy:** 重试 + 恢复 + 通知

**Patterns:**
- 任务级重试: `ExecutorConfig.max_retries` 控制最大重试次数
- 恢复机制: 重试前调用 `_try_recover()` 重启应用
- 状态持久化: 失败任务记录 `error_message` 字段
- 通知机制: 任务失败时通过 `Notifier` 发送企业微信通知
- 异常任务检测: `Scheduler._check_and_reset_stale_tasks()` 重置超时任务

## Cross-Cutting Concerns

**Logging:** 使用 Python logging 模块，支持上下文信息 (端口、账号、任务)
- 配置: `src/ptcgp_auto_v2/config/settings.py::Settings.configure_logging()`
- 上下文: `src/ptcgp_auto_v2/utils/logger.py::set_context()`

**Validation:**
- 页面识别验证: PageDetector 返回匹配度与置信度
- 参数验证: FastAPI 通过 Pydantic 进行请求参数验证

**Authentication:**
- 游戏账号认证: 通过 XML 文件切换账号
- Web 界面: 无认证（本地使用）

**多语言支持:**
- 任务 OCR: `src/ptcgp_auto_v2/locales/` (zh_Hant, en_US)
- Web 界面: `src/ptcgp_auto_v2/web/locales/` (zh_CN, en)

---

*Architecture analysis: 2026-02-23*
