# PTCGP Auto - AI 助手指引

## 最高原则

### 语言与文档规范

- 使用 **中文** 回复问题，思考使用 **中文** ，不要忘记使用 **中文** 回复
- 使用 **中文** 描述所有 文档/注释/日志输出 方便开发人员理解
- 方法/函数/类 必须带有简要中文注释，重要/复杂的逻辑需要大致描述流程
- 不要随便清除原先代码中的 **中文** 注释
- 不要寻找 `CLAUDE.md`，使用 `AGENTS.md`

### Git 工作流

- 提交代码时，标题使用英文，内容使用 **中文**，按照 `Conventional Commits` 格式提交
- add 代码时，必须检查与本次有关的文件，不允许 `add -A`
- **不允许使用 checkout** ，你自己改了哪些内容，回退时必须使用`编辑工具`回退自己增加的部分。

### 代码质量原则

- 代码永远要以简洁优先，指的是不写大量的兼容代码，当无其他特殊情况时，简洁单一是首要原则
- 在原有方法上修改，需要更改调用的地方，让其保持一致性，而不是考虑兼容旧代码而牺牲方法的简洁优雅
- 新增新方法时，需要清理带有大量重复逻辑的旧代码，防止代码膨胀
- 编写代码前，永远不重复造轮子，永远要能够编写代码前 从以往读到的代码 尝试复用相同逻辑，而不是在各个文件写相同的代码逻辑而使程序完全不可维护
- 在 coding 阶段，一定要懂得模块化设计，高内聚低耦合原则，单代码文件原则上最多不要超过 500 行

### 变更与维护规范

- 在变更代码逻辑时，同时检查 方法/类/文件开头 的注释，避免逻辑与注释不完全一致
- **当代码结构变更时，对应更新 README 和 AGENTS.md（本文件）**
- 重构时，如果被修改的文件有未提交的代码，务必先提问是否先提交代码才往下进行（防止被改变功能逻辑）
- 如果 plan 文档与实际代码不一样，则有可能 plan 文档相比代码是过时的，如果要变更一定要先询问开发者
- 每次定位并修复新问题后，必须把问题与正确做法回填到对应模块的 `AGENTS.md`（如 `web/AGENTS.md`、`tasks/AGENTS.md`）的常见问题/注意点中，保持规则持续更新

### 代码清理与优化

- 思考每个变量的实际作用，在变更代码后，检查所有无用代码、变量、常量、函数，没有作用的代码不要留在代码中，直接移除；但是如果是注释的代码，那说明不要移除
- 简化代码时，一定要检查是否有测试代码，没有的话必须先写测试代码，防止错误回归

### 技术实现细节

- 涉及像素的代码，使用基准像素值（基于 1080x1920）+ `adb.scaled_x/scaled_y` 缩放方法，不允许直接写死当前分辨率像素或使用比例常量；基准像素常量应提前到代码开头，并写明注释说明来源和作用
- 出现 `No module named 'xxx'` 时要设置 `PYTHONPATH=src`
- 不准硬编码 ocr 出来的文字内容，要考虑 locales 配置，可以只优先配置 zh_hant 不处理其他语言，但是不能硬编码
- ** 不要他妈的往`core/`或者`infra/`里面加任何 涉及业务细节的东西，你他妈给我看清楚这两个目录是干什么的 **
- 自动选包策略与调参脚本必须共享同一套常量配置（`config/constants.py`），禁止脚本私有参数与正式策略漂移

### 数据库规范

- **数据库时间字段统一使用本地时间（localtime）**：
  - Schema 默认值使用 `DEFAULT (datetime('now', 'localtime'))` 而非 `CURRENT_TIMESTAMP`
  - Python 代码使用 `datetime.now()` 获取本地时间
  - SQL 查询中时间比较使用 `datetime('now', 'localtime', ...)` 格式
  - 禁止混用 UTC 和本地时间，避免时区转换问题

### 计划与流程

- 在执行复杂计划前，把本次计划持久化文档到目录 `docs/plans/` 下，并在阶段性完成后更新进度，文档中要把用户最开始的诉求写明，原文保存（简单的小改动可以不需要）
- 解决问题时，执行命令前，思考当前的命令是否需要通过`声明式配置`以保证后续不再犯错，而不是直接执行

### 调试与运维

- 必要时直接通过 `python debug_tool.py -a [ADB_PORT] --template [template_name]` 查看当前页面的 ocr 内容和是否出现相应模板文件
- 当在对话中某个代码问题第一次出现时，应直接给出`源代码问题部分`的代码块作为引用展示
- 长时间的任务不应该自己执行而是请求人工接管，除非自身支持后台运行或有设置超时时间

## 知识获取与整理原则

- 使用 **中文** 书写所有文档
- 优先使用`fetcher-mcp`获取网页内容
- 调研资料时，不定时（分阶段）将获取的知识按照`[两位数字]-[主题].md`格式放入docs/refs文件夹中，方便后续重新阅读.
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
│   ├── scheduler.py        # 任务调度器
│   ├── executor.py         # 任务执行器
│   ├── task_base.py        # 任务基类与注册表
│   ├── task_status.py      # 任务状态定义
│   ├── hooks.py            # Hook 机制基础定义
│   └── device_pool.py      # 设备池管理
├── tasks/                  # 任务实现（10 个任务）
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
│   └── tests/              # Web 测试
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
# v2 守护模式
python main_v2.py --daemon

# 调试工具
python debug_tool.py

# 手动执行单次任务
python main_v2.py --task open_pack --account 1 --debug
```

## 调试与开发

1. **新增任务**: 在 `src/ptcgp_auto_v2/tasks/` 创建新文件，继承 `Task` 类并使用 `@TaskRegistry.register` 装饰器。
2. **页面定义**: 在各自 task 中定义页面识别规则。
3. **本地测试**: 使用 `python main_v2.py --task <task_name> --account <id> --debug` 单独测试任务。
4. **卡牌识别配置**: 在 `src/ptcgp_auto_v2/config/constants.py` 中调整 YOLO 和 Hash 阈值。

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **模型来源**: YOLO 模型从 `shelken/ptcgp-assets` 自动下载
- **Hash 计算**: 使用 scipy DCT 实现，比纯 Python 快 100-1000 倍
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)
  - **重要**: 为保持灵活性，**所有物理外键 (Foreign Key) 约束已被移除**。表之间的关系由 SQLAlchemy/SQLModel 的逻辑外键 (`Relationship` with `primaryjoin`) 维护。
  - 修改模型后无需迁移（目前自动初始化，复杂变更需手动处理）
  - 数据迁移：如需变更 Schema，请参考 `scripts/migration_v2_remove_fks.py` 编写类似的迁移脚本。目前不依赖 Alembic 进行自动迁移。
- **时间处理**: 统一使用 `localtime`，禁止使用 UTC
