# PTCGP Auto - AI 助手指引

## 最高原则

- 不要寻找`CLAUDE.md`, 使用 `AGENTS.md`
- 提交代码时，标题使用英文，内容使用 **中文**，按照`Conventional Commits`格式提交
- 使用 **中文** 回复问题，思考使用 **中文** ，不要忘记使用 **中文** 回复
- 不要随便清除原先代码中的中文注释
- 方法/函数/类 必须带有简要中文注释，重要/复杂的逻辑需要大致描述流程
- 使用 **中文** 描述所有 文档/注释/日志输出 方便开发人员理解
- 重构时，如果被修改的文件有未提交的代码，务必先提问是否先提交代码才往下进行（防止被改变功能逻辑）
- 解决问题时，执行命令前，思考当前的命令是否需要声明式配置以保证后续不再犯错，而不是直接执行
- 编写代码前，永远不重复造轮子，永远要能够编写代码前 从以往读到的代码 尝试复用相同逻辑，而不是在各个文件写相同的代码逻辑而使程序完全不可维护
- 简化代码时，一定要检查是否有测试代码，没有的话必须先写测试代码，防止错误回归。
- 思考每个变量的实际作用，在变更代码后，检查所有无用代码、变量、常量、函数，没有作用的代码不要留在代码中，直接移除；但是如果是注释的代码，那说明不要移除。
- 必要时直接通过 `python debug_tool.py -a 127.0.0.1:[PORT] --template [template_name]` 查看当前页面的ocr内容和是否出现相应模板文件
- add代码时，必须检查与本次有关的文件，不允许`add -A`
- 在coding阶段，一定要懂得模块化设计，高内聚低耦合原则，单代码文件原则上最多不要超过500行
- 在变更代码逻辑时，同时检查 方法/类/文件开头 的注释，避免逻辑与 **中文** 注释完全不一致
- **当代码结构变更时，对应更新 README 和 CLAUDE.md（本文件）**
- 当在对话中第一次提到某个代码问题时，应直接给出源代码问题部分的代码块作为引用展示
- 不准硬编码ocr出来的文字内容，要考虑 locales 配置，可以只优先配置zh_hant不处理其他语言，但是不能硬编码
- 涉及像素的代码，使用基准像素值（基于 1080x1920）+ `adb.scaled_x/scaled_y` 缩放方法，不允许直接写死当前分辨率像素或使用比例常量；基准像素常量应提前到代码开头，并写明注释说明来源
- **数据库时间字段统一使用本地时间（localtime）**：
  - Schema 默认值使用 `DEFAULT (datetime('now', 'localtime'))` 而非 `CURRENT_TIMESTAMP`
  - Python 代码使用 `datetime.now()` 获取本地时间
  - SQL 查询中时间比较使用 `datetime('now', 'localtime', ...)` 格式
  - 禁止混用 UTC 和本地时间，避免时区转换问题
- 在执行复杂计划前，把本次计划持久化文档到目录`docs/plans/`下，并在阶段性完成后更新进度，文档中要把用户最开始的诉求写明，原文保存（简单的小改动可以不需要）
- 出现`No module named 'xxx'`时要设置`PYTHONPATH=src`
- 长时间的任务不应该自己执行而是请求人工接管，除非自身支持后台运行
- 不允许随便 checkout 某个代码文件，你自己改了哪些内容，回退时必须使用编辑工具回退自己增加的部分，不允许使用checkout

## 知识获取与整理原则

- 使用 **中文** 书写所有文档
- 优先使用`fetcher-mcp`获取网页内容
- 调研资料时，不定时（分阶段）将获取的知识按照`[两位数字]-[主题].md`格式放入docs/refs文件夹中，方便后续重新阅读.
- 每次进行资料搜集时先列出目录已经获取的知识
- 知识不要详尽，应当大部分用一句话来总结结论，然后用具体来源的URL链接指向，尽量简洁凝练总结所有知识点，除非很重要必须详细说明。
- 知识获取来源必须用链接直接写出，方便用户和agents直接跳转获取，链接应该是具体的，而不是笼统的域名或者路径。

## 项目概述

这是一个用于 PTCGP（Pokemon TCG Pocket）的 Python 自动化框架。
**v2 版本 (当前主版本)** 采用任务队列 + 调度器架构，支持多账号、多设备、原子任务（开包、领奖等）。
**v1 版本 (Legacy)** 仅用于单人对战刷经验，保留在 `src/ptcgp_auto` 中。

## 核心架构 (v2)

源代码位于 `src/ptcgp_auto_v2/` 目录下：

- `main_v2.py` - v2 入口文件
- `src/ptcgp_auto_v2/`
  - `core/` - 核心调度模块
    - `scheduler.py` - 任务调度器 (Scheduler)
    - `executor.py` - 任务执行器 (Executor)
    - `task_base.py` - 任务基类 (Task) 和注册表
    - `device_pool.py` - 设备池管理
  - `tasks/` - 具体任务实现
    - `open_pack.py` - 开包任务
    - `claim_rewards.py` - 领取奖励任务
    - `fetch_account_info.py` - 账号信息同步任务
    - `collect_account_cards.py` - 账号高稀有度卡牌采集任务
    - `wonder_pick.py` - 得卡挑战任务
  - `infra/` - 基础设施层
    - `adb.py` - ADB 控制封装
    - `ocr.py` - OCR 引擎封装
    - `model_manager.py` - [新增] YOLO模型管理（全局单例，异步加载）
    - `card_hash_manager.py` - [新增] 卡牌Hash索引管理（内存缓存）
    - `yolo_card_recognizer.py` - [新增] YOLO+Hash卡牌识别器
    - `icon_group_detector.py` - 稀有度图标分组检测
    - `page_detector.py` - 页面检测器
    - `account_switcher.py` - 账号切换逻辑
  - `db/` - 数据库层
    - `models/` - 数据模型 (Account, TaskInstance)
      - `account_card.py` - 账号卡牌关联表
    - `repositories.py` - 数据访问对象 (DAO)
  - `config/` - 配置管理
    - `rarity_icons.py` - 稀有度图标与映射配置
  - `locales/` - 多语言配置

### 调度流程

```
Main (Daemon)
  ↓
Scheduler (Loop)
  ├── 1. Generate Tasks (检查 AccountPlan 生成 TaskInstance)
  ├── 2. Check Devices (获取空闲 Device)
  └── 3. Dispatch (将 Task 分配给 Executor)
         ↓
      Executor (Thread)
         ├── Bind Device & Task
         ├── Switch Account (if needed)
         └── Run Task Logic (OCR -> Action -> Loop)
```

## 文件结构概览

```
ptcgp-auto/
├── main_v2.py                  # [v2] 主入口
├── main.py                     # [v1] 旧版入口 (Legacy)
├── debug_tool.py               # 调试工具
├── src/
│   ├── ptcgp_auto_v2/          # [v2] 核心代码
│   │   ├── core/               # 核心框架
│   │   ├── tasks/              # 任务实现
│   │   │   └── utils/           # 任务级共用逻辑
│   │   ├── db/                 # 数据库
│   │   │   └── models/
│   │   │       └── card.py     # 新增 perceptual_hash 字段
│   │   ├── infra/              # 基础设施
│   │   │   ├── model_manager.py       # [新增] 模型管理
│   │   │   ├── card_hash_manager.py   # [新增] Hash管理
│   │   │   └── yolo_card_recognizer.py # [新增] YOLO识别
│   │   ├── config/             # 配置
│   │   ├── web/                # Web UI (FastAPI/HTMX)
│   │   │   ├── app.py           # Web 入口（初始化与路由挂载）
│   │   │   ├── routers/         # 路由层
│   │   │   ├── services/        # 业务层
│   │   │   ├── queries/         # 查询层
│   │   │   ├── utils/           # i18n/模板/视图辅助
│   │   │   └── static/js/       # 前端模块化入口
│   │   └── utils/              # 工具
│   │       ├── action_result.py    # 动作结果数据结构
│   │       └── perceptual_hash.py    # [新增] 哈希计算
│   └── ptcgp_auto/             # [v1] 旧版代码
└── docs/                       # 文档
```

## 常用命令

```bash
# v2 守护模式 (推荐)
python main_v2.py --daemon

# 调试工具
python debug_tool.py
```

## 调试与开发

1. **新增任务**: 在 `src/ptcgp_auto_v2/tasks/` 创建新文件，继承 `Task` 类并使用 `@TaskRegistry.register` 装饰器。
2. **页面定义**: 在 `src/ptcgp_auto_v2/config/pages/` 中定义页面识别规则。
3. **本地测试**: 使用 `python main_v2.py --task <task_name> --account <id>` 单独测试任务。
4. **卡牌识别配置**: 在 `src/ptcgp_auto_v2/config/constants.py` 中调整 YOLO 和 Hash 阈值
   - `YOLO_OBB_THRESHOLD` - YOLO检测置信度阈值
   - `HASH_SIMILARITY_THRESHOLD` - Hash匹配相似度阈值

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **新增依赖**: 需要安装 `ultralytics>=8.3.0` 和 `scipy>=1.17.0`
- **模型来源**: YOLO模型从 `shelken/ptcgp-assets` 自动下载
- **Hash计算**: 使用 scipy DCT 实现，比纯Python快 100-1000 倍
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)
  - **重要**: 为保持灵活性，**所有物理外键 (Foreign Key) 约束已被移除**。表之间的关系由 SQLAlchemy/SQLModel 的逻辑外键 (`Relationship` with `primaryjoin`) 维护。
  - 修改模型后无需迁移（目前自动初始化，复杂变更需手动处理）
  - 数据迁移：如需变更 Schema，请参考 `scripts/migration_v2_remove_fks.py` 编写类似的迁移脚本。目前不依赖 Alembic 进行自动迁移。
- **时间处理**: 统一使用 `localtime`，禁止使用 UTC

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
