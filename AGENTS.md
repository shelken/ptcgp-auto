## 运行

- 禁止`using-git-worktrees`
- 修复bug时不要写任何测试，直接修改代码。
- 不允许使用`py_compile`来检查语法，使用`uv run ruff check`
- 使用uv/bun，而不是用pip/npm
- 如果在工作目录出错后，使用`direnv exec . [cmd]`运行（目录无法执行时先`direnv allow`）,任何python命令，使用uv跑
- Python 项目导入统一规则：项目根目录必须有 `[build-system]`，进入环境后先 `uv sync` 或 `direnv reload`，禁止使用 `PYTHONPATH=src`
- 禁止为了导入 `src/` 下项目包，在入口脚本、工具脚本、业务代码里手动修改 `sys.path` 来兜底
- 如果没有数据调试，尝试`cp -r ~/Code/active/ptcgp-auto/data ./`(在当前worktree非main时), 没有启动web时启动`./scripts/web_dev.sh`，然后使用`playwright-cli`自己调试web变更

## 语言与文档规范

- 使用 **中文** 描述所有 文档/注释/日志输出 方便开发人员理解
- 不要随便清除原先代码中的 **中文** 注释
- 不要寻找 `CLAUDE.md`，使用 `AGENTS.md`

## Git 工作流

- 提交前，必须检查一遍所有代码的 函数/常量/变量 ，把所有没有使用的代码全部清理掉；python使用vulture/ruff工具检查(uv)，TS/JS使用knip/ESLint检查(bun)；快捷指令`direnv exec . pre-commit run`

## **代码质量原则**

**每次编写代码前，重读一次代码质量原则**

- 代码永远要以简洁优先，当无其他特殊情况时，简洁单一是首要原则
- 遵守FAILFAST原则，不写大量的兼容、防御性、补丁式代码
- 新增新方法时，先检查是否有旧方法并在这个基础上进行重构，防止代码膨胀，简洁优雅依然是第一位
- 每次编写代码前，永远不重复造轮子，尝试复用相同逻辑，而不是在各个文件写相同的代码逻辑
- 编写复杂功能时，一定要懂得模块化设计，但是不过度设计
- 不允许为了导入 `src/` 下项目包去补 `sys.path`；先修项目安装方式，再运行 `uv sync`

## 变更与维护规范

- 在变更代码逻辑时，同时检查 方法/类/文件开头 的注释，避免逻辑与注释不完全一致
- **当代码结构变更时，对应更新 README 和 AGENTS.md（本文件）**
- 重构时，如果被修改的文件有未提交的代码，务必先提问是否先提交代码才往下进行（防止被改变功能逻辑）
- 如果 plan 文档与实际代码不一样，则有可能 plan 文档相比代码是过时的，如果要变更一定要先询问开发者

## 技术实现重要细节

- 涉及像素的代码，使用基准像素值（基于 1080x1920）+ `adb.scaled_x/scaled_y` 缩放方法，不允许直接写死当前分辨率像素或使用比例常量；基准像素常量应提前到代码开头，并写明注释说明来源和作用
- 出现 `No module named 'xxx'` 时，先检查 `pyproject.toml` 是否定义 `[build-system]`，再执行 `uv sync` 或 `direnv reload`；不要设置 `PYTHONPATH=src`
- 不准硬编码 ocr 出来的文字内容，要考虑 locales 配置，可以只优先配置 zh_hant 不处理其他语言，但是不能硬编码
- ** 不要他妈的往`core/`或者`infra/`里面加任何 涉及业务细节的东西，你他妈给我看清楚这两个目录是干什么的 **

## 语言/本地化（强制）

- 语言配置单一来源：`src/ptcgp_auto_v2/config/lang.py`

## 数据库规范

- **数据库时间字段统一使用本地时间（localtime）**：
  - Schema 默认值使用 `DEFAULT (datetime('now', 'localtime'))` 而非 `CURRENT_TIMESTAMP`
  - Python 代码使用 `datetime.now()` 获取本地时间
  - SQL 查询中时间比较使用 `datetime('now', 'localtime', ...)` 格式
  - 禁止混用 UTC 和本地时间，避免时区转换问题
- **v2 数据访问统一规则**：
  - 高层业务动作统一使用 `session_scope()` 作为事务边界
  - 所有 Repository 构造都必须显式传入 `Session`
  - 同一动作需要多个 Repository 时，统一使用 `RepositoryFactory(session)`
  - Repository 内部禁止自建 `Session`、禁止自行 `commit`
  - 模型层禁止 `save()/update()/delete()` 这类写库入口
  - 事务外禁止继续传递 ORM 实体；跨层只允许标量、`dataclass` 纯数据或视图 `dict`
  - 日志、通知、Webhook 这类次要副作用不得与主数据写入共用同一事务；主数据必须先提交，副作用随后单独执行
  - 反例：开包写入 `account_cards` 时，禁止把 `notifications` 插入放在同一个 `session_scope()` 里；否则通知失败会把已识别出的高稀有卡一并回滚

## 调试与运维

- 必要时直接通过 `uv run python debug_tool.py -a [ADB_PORT] --template [template_name]` 查看当前页面的 ocr 内容和是否出现相应模板文件
- 长时间的任务不应该自己执行而是请求人工接管，除非自身支持后台运行命令

## 知识获取与整理原则

- 可以使用`fetcher-mcp`获取网页内容
- 调研资料时，不定时（分阶段）将获取的知识按照`[两位数字]-[主题].md`格式放入docs/refs文件夹中，方便后续重新阅读
- 每次进行资料搜集时先列出目录已经获取的知识
- 知识不要详尽，应当大部分用一句话来总结结论，然后用具体来源的URL链接指向，尽量简洁凝练总结所有知识点，除非很重要必须详细说明。
- 知识获取来源必须用链接直接写出，方便用户和agents直接跳转获取，链接应该是具体的，而不是笼统的域名或者路径。

## 项目概述

这是一个用于 PTCGP（Pokemon TCG Pocket）的 Python 自动化框架。
**v2 版本 (当前主版本)** 采用任务队列 + 调度器架构，支持多账号、多设备、原子任务。
**v1 版本 (Legacy)** 仅用于单人对战刷经验，保留在 `src/ptcgp_auto` 中。

## 核心架构 (v2)

源代码位于 `src/ptcgp_auto_v2/` 目录下：

```
src/ptcgp_auto_v2/
├── main_v2.py              # v2 入口文件（项目根目录）
├── core/                   # 核心调度模块
│   ├── scheduler.py        # 任务调度器（负责任务生成/账号批次挑选/设备分配，不再维护调度规则细节）
│   ├── executor.py         # 任务执行器
│   ├── scheduling_service.py  # 调度规则统一服务（计划聚合/排序/reset/next_run/调度摘要/调度顺位/调度字段回写）
│   ├── task_base.py        # 任务基类与注册表
│   ├── task_status.py      # 任务状态定义
│   ├── hooks.py            # Hook 机制基础定义
│   └── device_pool.py      # 设备池管理
├── tasks/                  # 任务实现（11 个任务）
│   ├── pack_opening_task_base.py  # 统一开包流程基类（open_pack/claim_gifts/init_account 继承）
│   ├── open_pack.py        # 每日开包
│   ├── claim_rewards.py    # 领取任务奖励
│   ├── claim_gifts.py      # 领取礼物盒
│   ├── wonder_pick.py      # 得卡挑战
│   ├── collect_account_cards.py  # 卡牌采集
│   ├── send_card_daily.py  # 每日送卡
│   ├── exchange_cards.py   # 交换卡牌
│   ├── fetch_account_info.py    # 账号信息同步
│   ├── init_account.py     # 新账号初始化入库
│   ├── manage_friendship.py     # 好友管理（添加/删除）
│   └── utils/              # 任务级共用逻辑
│       ├── booster_inference.py  # 子包推断工具（模板优先 + 卡牌兜底）
│       ├── card_pick.py    # 卡牌选择逻辑
│       ├── rarity_filter.py     # 稀有度筛选面板
│       ├── friend_selection_flow.py  # 好友选择流程
│       ├── friend_card_flow.py  # 好友卡牌检测
│       ├── pack_opening_flow.py # 开包流程共用
│       ├── high_rarity_saver.py # 高稀有度卡牌保存
│       └── constants.py    # 常量定义
├── hooks/                  # Hook 实现
│   ├── exchange_hooks.py   # 交换卡牌 Hook
│   ├── friend_hooks.py     # 好友关系 Hook
│   └── gift_hooks.py       # 送卡 Hook
├── services/               # 业务服务层
│   ├── exchange_card_service.py  # 交换卡牌服务
│   ├── friendship_service.py     # 好友关系服务
│   ├── gift_pairing_service.py   # 送卡配对服务
│   └── gift_record_service.py    # 送卡记录服务
├── infra/                  # 基础设施层
│   ├── adb.py              # ADB 控制封装
│   ├── ocr.py              # OCR 引擎封装
│   ├── model_manager.py    # YOLO 模型管理
│   ├── card_hash_manager.py     # 卡牌 Hash 索引管理
│   ├── yolo_card_recognizer.py  # YOLO + Hash 卡牌识别器
│   ├── icon_group_detector.py   # 稀有度图标分组检测
│   ├── page_detector.py    # 页面检测器
│   └── account_switcher.py # 账号切换逻辑
├── db/                     # 数据库层
│   ├── models/             # 数据模型（17 个）
│   │   ├── account.py      # 账号模型
│   │   ├── account_stat.py # 账号资源统计
│   │   ├── account_card.py # 账号卡牌关联
│   │   ├── account_friendship.py  # 好友关系
│   │   ├── account_friend_request.py  # 好友请求
│   │   ├── account_gift_pair.py   # 送卡配对
│   │   ├── account_gift_record.py # 送卡记录
│   │   ├── account_pack_config.py # 开包配置
│   │   ├── account_pack_point.py  # 系列点数
│   │   ├── account_task_plan.py   # 账号任务计划关联
│   │   ├── exchange_card_request.py  # 交换请求
│   │   ├── task_instance.py   # 任务实例
│   │   ├── task_plan.py       # 任务计划
│   │   ├── card.py            # 卡牌/系列/子包模型
│   │   ├── pack_card.py       # 开包记录卡牌
│   │   ├── pack_record.py     # 开包记录
│   │   └── base.py            # 基础模型
│   └── repositories/       # 数据访问对象 (DAO)
├── web/                    # Web UI (FastAPI + HTMX)
│   ├── app.py              # Web 入口
│   ├── routers/            # 路由层（13 个路由）
│   │   ├── index.py        # 首页
│   │   ├── records.py      # 开包记录
│   │   ├── owned_cards.py  # 拥有卡牌
│   │   ├── tasks.py        # 任务状态
│   │   ├── management.py   # 管理中心
│   │   ├── plans.py        # 计划配置
│   │   ├── metadata.py     # 元数据管理
│   │   ├── pack_config.py  # 开包配置
│   │   ├── friendship.py   # 好友关系
│   │   ├── daily_gift.py   # 每日送卡
│   │   └── exchange_card.py  # 交换记录
│   ├── services/           # 业务层
│   ├── queries/            # 查询层
│   ├── utils/              # 工具层
│   ├── templates/          # Jinja2 模板
│   ├── static/             # 静态资源 (CSS/JS)
│   ├── locales/            # 多语言配置
├── config/                 # 配置管理
├── locales/                # 任务用多语言配置
└── utils/                  # 工具函数
    ├── action_result.py    # 动作结果数据结构
    └── perceptual_hash.py  # 感知哈希计算
```

### 调度流程

```
Main (Daemon)
  ↓
Scheduler (Loop)
  ├── 1. Generate Tasks (检查任务计划生成任务实例)
  ├── 2. Check Devices (获取空闲设备)
  └── 3. Dispatch (将任务分配给执行器)
         ↓
      Executor (Thread)
         ├── Bind Device & Task
         ├── Switch Account (if needed)
         └── Run Task Logic (OCR -> Action -> Loop)
```

## 常用命令

```bash
# 首次进入仓库，先同步当前项目和依赖
uv sync

# v2 守护模式
uv run python main_v2.py --daemon

# 调试工具
uv run python debug_tool.py

# Web 入口
./scripts/web_dev.sh

# 手动执行单次任务
uv run python main_v2.py --task open_pack --account 1 --debug
```

## 调试与开发

1. **新增任务**: 在 `src/ptcgp_auto_v2/tasks/` 创建新文件，继承 `Task` 类并使用 `@TaskRegistry.register` 装饰器。
2. **页面定义**: 在各自 task 中定义页面识别规则。
3. **本地测试**: 使用 `uv run python main_v2.py --task <task_name> --account <id> --debug` 单独测试任务。
4. **卡牌识别配置**: 在 `src/ptcgp_auto_v2/config/constants.py` 中调整 YOLO 和 Hash 阈值。
5. **子包推断**: `PackOpeningTaskBase` 已集成两阶段子包推断（滑动页模板优先 + 结果页卡牌兜底），支持 `exclude_promo` 排除 PROMO 干扰。动态模板在会话结束后自动清理。

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **模型来源**: YOLO 模型从 `shelken/ptcgp-assets` 自动下载
- **Hash 计算**: 使用 scipy DCT 实现，比纯 Python 快 100-1000 倍
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)
  - **重要**: 为保持灵活性，**所有物理外键 (Foreign Key) 约束已被移除**。表之间的关系由 SQLAlchemy/SQLModel 的逻辑外键 (`Relationship` with `primaryjoin`) 维护。
  - 修改模型后无需迁移（目前自动初始化，复杂变更需手动处理）
  - 数据迁移：如需变更 Schema，请参考 `scripts/migration_v2_remove_fks.py` 编写类似的迁移脚本。目前不依赖 Alembic 进行自动迁移。
