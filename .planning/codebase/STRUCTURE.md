# Codebase Structure

**Analysis Date:** 2026-02-23

## Directory Layout

```
ptcgp-auto/
├── main_v2.py                     # v2 入口脚本
├── main.py                        # v1 入口脚本 (Legacy)
├── debug_tool.py                  # 调试工具
├── config_cli.py                  # 配置命令行工具
├── src/                           # 源代码目录
│   ├── ptcgp_auto/               # v1 代码 (Legacy)
│   └── ptcgp_auto_v2/            # v2 主版本代码
├── data/                          # 数据目录
│   └── ptcgp_v2.db               # SQLite 数据库
├── docs/                          # 文档目录
├── scripts/                       # 脚本目录
├── tests/                         # v1 测试目录 (Legacy)
└── .planning/                     # 规划文档目录
```

## v2 源代码目录结构

```
src/ptcgp_auto_v2/
├── __init__.py                    # 包初始化
├── main.py                        # 主入口逻辑
├── config/                        # 配置层
│   ├── __init__.py
│   ├── assets.py                  # 资源路径配置
│   ├── constants.py               # 常量定义
│   ├── notification.py            # 通知配置
│   ├── rarity_icons.py            # 稀有度图标配置
│   ├── settings.py                # 运行时配置
│   ├── wonder_pick.py             # 得卡挑战配置
│   └── pages/                     # 页面规则配置
│       ├── __init__.py
│       └── common.py              # 公共页面规则
├── core/                          # 核心调度层
│   ├── __init__.py
│   ├── account_creation.py        # 自动创建账号逻辑
│   ├── device_pool.py             # 设备池管理
│   ├── executor.py                # 任务执行器
│   ├── hooks.py                   # Hook 基础定义
│   ├── scheduler.py               # 任务调度器
│   ├── task_base.py               # 任务基类与注册表
│   ├── task_ordering.py           # 任务排序逻辑
│   ├── task_plan_utils.py         # 任务计划工具
│   ├── task_schedule.py           # 任务调度工具
│   └── task_status.py             # 任务状态定义
├── db/                            # 数据访问层
│   ├── __init__.py
│   ├── connection.py              # 数据库连接管理
│   ├── engine.py                  # SQLModel 引擎
│   ├── models/                    # 数据模型 (17个)
│   │   ├── __init__.py
│   │   ├── base.py                # 基础混入类
│   │   ├── account.py             # 账号模型
│   │   ├── account_card.py        # 账号卡牌关联
│   │   ├── account_friend_request.py  # 好友请求
│   │   ├── account_friendship.py  # 好友关系
│   │   ├── account_gift_pair.py   # 送卡配对
│   │   ├── account_gift_record.py # 送卡记录
│   │   ├── account_pack_config.py # 开包配置
│   │   ├── account_pack_point.py  # 系列点数
│   │   ├── account_stat.py        # 账号资源统计
│   │   ├── account_task_plan.py   # 账号任务计划关联
│   │   ├── card.py                # 卡牌/系列/子包模型
│   │   ├── exchange_card_request.py  # 交换请求
│   │   ├── notification.py        # 通知记录
│   │   ├── notification_config.py # 通知配置
│   │   ├── pack_card.py           # 开包记录卡牌
│   │   ├── pack_record.py         # 开包记录
│   │   ├── task_instance.py       # 任务实例
│   │   └── task_plan.py           # 任务计划
│   └── repositories/              # 数据访问对象 (14个)
│       ├── __init__.py
│       ├── account_card_repository.py
│       ├── account_gift_pair_repository.py
│       ├── account_gift_record_repository.py
│       ├── account_pack_config_repository.py
│       ├── account_pack_point_repository.py
│       ├── account_repository.py
│       ├── account_stat_repository.py
│       ├── card_repository.py
│       ├── exchange_card_request_repository.py
│       ├── friend_request_repository.py
│       ├── friendship_repository.py
│       ├── notification_config_repository.py
│       ├── notification_repository.py
│       ├── pack_record_repository.py
│       ├── task_instance_repository.py
│       └── task_plan_repository.py
├── hooks/                         # Hook 实现
│   ├── __init__.py
│   ├── exchange_hooks.py          # 交换卡牌 Hook
│   ├── friend_hooks.py            # 好友关系 Hook
│   └── gift_hooks.py              # 送卡 Hook
├── infra/                         # 基础设施层
│   ├── __init__.py
│   ├── account_switcher.py        # 账号切换逻辑
│   ├── account_syncer.py          # 账号同步逻辑
│   ├── adb.py                     # ADB 控制封装
│   ├── card_hash_manager.py       # 卡牌 Hash 索引管理
│   ├── icon_group_detector.py     # 稀有度图标分组检测
│   ├── model_manager.py           # YOLO 模型管理
│   ├── notifier.py                # 通知发送器
│   ├── ocr.py                     # OCR 引擎封装
│   ├── page_detector.py           # 页面检测器
│   ├── template.py                # 模板匹配器
│   └── yolo_card_recognizer.py    # YOLO + Hash 卡牌识别器
├── locales/                       # 任务用多语言配置
│   ├── __init__.py
│   ├── en_US.py                   # 英文
│   └── zh_Hant.py                 # 繁体中文
├── scripts/                       # 脚本
│   └── sync_metadata.py           # 元数据同步脚本
├── services/                      # 业务服务层
│   ├── __init__.py
│   ├── exchange_card_service.py   # 交换卡牌服务
│   ├── friendship_service.py      # 好友关系服务
│   ├── gift_pairing_service.py    # 送卡配对服务
│   └── gift_record_service.py     # 送卡记录服务
├── tasks/                         # 任务实现层 (10个任务)
│   ├── __init__.py
│   ├── claim_gifts.py             # 领取礼物盒
│   ├── claim_rewards.py           # 领取任务奖励
│   ├── collect_account_cards.py   # 卡牌采集
│   ├── exchange_cards.py          # 交换卡牌
│   ├── fetch_account_info.py      # 账号信息同步
│   ├── init_account.py            # 新账号初始化
│   ├── manage_friendship.py       # 好友管理
│   ├── open_pack.py               # 每日开包
│   ├── send_card_daily.py         # 每日送卡
│   ├── wonder_pick.py             # 得卡挑战
│   └── utils/                     # 任务级共用逻辑
│       ├── __init__.py
│       ├── card_pick.py           # 卡牌选择逻辑
│       ├── constants.py           # 常量定义
│       ├── friend_card_flow.py    # 好友卡牌检测
│       ├── friend_id_utils.py     # 朋友ID工具
│       ├── friend_selection_flow.py  # 好友选择流程
│       ├── high_rarity_saver.py   # 高稀有度卡牌保存
│       ├── nickname_utils.py      # 昵称工具
│       ├── pack_opening_flow.py   # 开包流程共用
│       ├── pack_result_mapper.py  # 开包结果映射
│       └── rarity_filter.py       # 稀有度筛选面板
├── tests/                         # 测试目录
│   ├── conftest.py                # pytest 配置
│   ├── fake_adb.py                # Fake ADB 实现
│   ├── config/                    # 配置测试
│   ├── core/                      # 核心层测试
│   ├── db/                        # 数据层测试
│   ├── hooks/                     # Hook 测试
│   ├── infra/                     # 基础设施测试
│   ├── locales/                   # 多语言测试
│   ├── services/                  # 服务层测试
│   ├── tasks/                     # 任务测试
│   ├── utils/                     # 工具测试
│   └── web/                       # Web 测试
├── utils/                         # 工具函数
│   ├── __init__.py
│   ├── account_cooldown.py        # 账号冷却
│   ├── action_result.py           # 动作结果数据结构
│   ├── bluestacks_manager.py      # BlueStacks 管理
│   ├── card_name_resolver.py      # 卡牌名称解析
│   ├── card_naming.py             # 卡牌命名工具
│   ├── color.py                   # 颜色工具
│   ├── common_handlers.py         # 通用页面处理器
│   ├── debug_visualizer.py        # 调试可视化
│   ├── device_discovery.py        # 设备发现
│   ├── game_time.py               # 游戏时间
│   ├── gesture.py                 # 手势操作
│   ├── image_manager.py           # 图片管理
│   ├── logger.py                  # 日志工具
│   ├── pack_auto_selector.py      # 自动选择卡包
│   ├── pack_image_manager.py      # 卡包图片管理
│   ├── packs.py                   # 卡包工具
│   ├── perceptual_hash.py         # 感知哈希计算
│   └── terminal_preview.py        # 终端预览
└── web/                           # Web UI 层
    ├── app.py                     # FastAPI 主应用
    ├── locales/                   # Web 多语言配置
    ├── queries/                   # 查询层
    │   ├── daily_gift_queries.py
    │   ├── exchange_card_queries.py
    │   ├── friendship_queries.py
    │   ├── metadata_queries.py
    │   ├── notification_queries.py
    │   ├── owned_card_queries.py
    │   ├── record_queries.py
    │   └── task_queries.py
    ├── routers/                   # 路由层 (13个路由)
    │   ├── daily_gift.py
    │   ├── exchange_card.py
    │   ├── friendship.py
    │   ├── index.py
    │   ├── management.py
    │   ├── metadata.py
    │   ├── notifications.py
    │   ├── owned_cards.py
    │   ├── pack_config.py
    │   ├── plans.py
    │   ├── records.py
    │   └── tasks.py
    ├── services/                  # Web 业务层
    │   ├── account_service.py
    │   ├── daily_gift_service.py
    │   ├── exchange_card_service.py
    │   ├── friendship_service.py
    │   ├── index_service.py
    │   ├── metadata_service.py
    │   ├── notification_service.py
    │   ├── owned_card_service.py
    │   ├── pack_config_service.py
    │   ├── plan_service.py
    │   ├── record_service.py
    │   └── task_service.py
    ├── static/                    # 静态资源
    │   ├── css/                   # 样式
    │   │   ├── main.css           # 主样式
    │   │   ├── base/              # 基础样式
    │   │   ├── components/        # 组件样式
    │   │   ├── themes/            # 主题样式
    │   │   └── utilities/         # 工具类
    │   └── js/                    # JavaScript
    │       ├── main.js            # 主入口
    │       └── modules/           # ES6 模块
    │           ├── bootstrap.js
    │           ├── event_bindings.js
    │           ├── action_handlers.js
    │           └── features/      # 功能模块
    ├── templates/                  # Jinja2 模板
    │   ├── index.html             # 主页面
    │   └── partials/              # 局部模板
    │       ├── macros/            # 宏定义
    │       └── modals/            # 模态框
    ├── tests/                     # Web 测试
    ├── utils/                     # Web 工具
    │   ├── element_utils.py
    │   ├── form_utils.py
    │   ├── i18n.py
    │   ├── template_env.py
    │   └── view_helpers.py
    └── AGENTS.md                  # Web 模块开发指引
```

## Directory Purposes

**config/ (配置层):**
- Purpose: 存放所有配置相关代码
- Contains: 常量、设置、页面规则、多语言配置
- Key files: `constants.py` (像素常量), `settings.py` (运行时配置)

**core/ (核心调度层):**
- Purpose: 任务调度与执行的核心逻辑
- Contains: Scheduler, Executor, DevicePool, Hooks
- Key files: `scheduler.py` (调度器), `executor.py` (执行器), `task_base.py` (任务基类)

**db/ (数据访问层):**
- Purpose: 数据模型定义与持久化
- Contains: SQLModel 模型、Repository 数据访问对象
- Key files: `connection.py` (数据库连接), `models/account.py` (账号模型)

**infra/ (基础设施层):**
- Purpose: 设备控制、识别、页面检测等基础能力
- Contains: ADB 控制、OCR、模板匹配、页面检测
- Key files: `adb.py` (ADB 控制), `page_detector.py` (页面检测)

**tasks/ (任务实现层):**
- Purpose: 具体自动化任务的业务逻辑
- Contains: 10 个任务实现 + utils 工具函数
- Key files: `open_pack.py` (开包任务), `utils/` (共用逻辑)

**services/ (业务服务层):**
- Purpose: 跨任务的业务逻辑封装
- Contains: 交换卡牌、好友关系、送卡等服务
- Key files: `exchange_card_service.py`, `friendship_service.py`

**hooks/ (Hook 实现):**
- Purpose: 任务执行前后的钩子逻辑
- Contains: 交换卡牌、好友关系、送卡等 Hook
- Key files: `exchange_hooks.py`, `gift_hooks.py`

**web/ (Web 服务层):**
- Purpose: 管理界面与 REST API
- Contains: FastAPI 应用、路由、服务、模板、静态资源
- Key files: `app.py` (应用入口), `routers/` (路由)

## Key File Locations

**Entry Points:**
- `main_v2.py`: CLI 入口脚本
- `src/ptcgp_auto_v2/main.py`: 主入口逻辑
- `src/ptcgp_auto_v2/web/app.py`: Web 服务入口

**Configuration:**
- `src/ptcgp_auto_v2/config/settings.py`: 运行时配置
- `src/ptcgp_auto_v2/config/constants.py`: 常量定义

**Core Logic:**
- `src/ptcgp_auto_v2/core/scheduler.py`: 任务调度器
- `src/ptcgp_auto_v2/core/executor.py`: 任务执行器
- `src/ptcgp_auto_v2/core/task_base.py`: 任务基类

**Infrastructure:**
- `src/ptcgp_auto_v2/infra/adb.py`: ADB 控制封装
- `src/ptcgp_auto_v2/infra/page_detector.py`: 页面检测器
- `src/ptcgp_auto_v2/infra/ocr.py`: OCR 引擎

**Database:**
- `src/ptcgp_auto_v2/db/connection.py`: 数据库连接
- `src/ptcgp_auto_v2/db/models/`: 数据模型
- `src/ptcgp_auto_v2/db/repositories/`: 数据访问对象

**Testing:**
- `src/ptcgp_auto_v2/tests/`: 单元测试与集成测试
- `src/ptcgp_auto_v2/tests/conftest.py`: pytest 配置

## Naming Conventions

**Files:**
- Python 模块: `snake_case.py` (如 `open_pack.py`, `task_base.py`)
- 测试文件: `test_<module_name>.py` (如 `test_open_pack.py`)
- 模板文件: `snake_case.html` (如 `index.html`, `account_list.html`)

**Directories:**
- Python 包: `snake_case/` (如 `tasks/`, `services/`)
- 静态资源: 按类型分 (如 `css/`, `js/`, `images/`)

**Classes:**
- 任务类: `<Action>Task` (如 `OpenPackTask`, `ClaimRewardsTask`)
- Repository: `<Entity>Repository` (如 `AccountRepository`, `TaskInstanceRepository`)
- Service: `<Domain>Service` (如 `ExchangeCardService`, `FriendshipService`)

## Where to Add New Code

**New Task:**
- Implementation: `src/ptcgp_auto_v2/tasks/<task_name>.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_<task_name>.py`
- Register: 使用 `@TaskRegistry.register("task_type")` 装饰器

**New Data Model:**
- Model definition: `src/ptcgp_auto_v2/db/models/<model_name>.py`
- Repository: `src/ptcgp_auto_v2/db/repositories/<model_name>_repository.py`
- Export: 更新 `db/models/__init__.py` 和 `db/repositories/__init__.py`

**New Web Route:**
- Router: `src/ptcgp_auto_v2/web/routers/<route_name>.py`
- Service: `src/ptcgp_auto_v2/web/services/<service_name>.py`
- Template: `src/ptcgp_auto_v2/web/templates/partials/<template_name>.html`
- Register: 在 `web/app.py` 中添加 `app.include_router()`

**New Hook:**
- Implementation: `src/ptcgp_auto_v2/hooks/<hook_name>.py`
- Test: `src/ptcgp_auto_v2/tests/hooks/test_<hook_name>.py`

**Shared Task Utilities:**
- Implementation: `src/ptcgp_auto_v2/tasks/utils/<utility_name>.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/utils/test_<utility_name>.py`

**Configuration:**
- Constants: `src/ptcgp_auto_v2/config/constants.py`
- Settings: `src/ptcgp_auto_v2/config/settings.py`
- Page rules: 任务内定义或 `config/pages/common.py`

## Special Directories

**data/ (数据目录):**
- Purpose: 存放数据库文件、模型文件、图片缓存
- Generated: 运行时自动创建
- Committed: 否 (应在 `.gitignore` 中排除)

**locales/ (多语言配置):**
- Purpose: 任务 OCR 文本的多语言支持
- Contains: `zh_Hant.py`, `en_US.py`
- Generated: 否
- Committed: 是

**web/locales/ (Web 多语言配置):**
- Purpose: Web 界面的多语言支持
- Contains: `zh_CN.json`, `en.json`
- Generated: 否
- Committed: 是

**.planning/ (规划文档):**
- Purpose: 存放规划、分析文档
- Contains: `codebase/`, `plans/` 等子目录
- Generated: 由 AI 助手生成
- Committed: 是

---

*Structure analysis: 2026-02-23*
