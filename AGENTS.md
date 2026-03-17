# PTCGP Auto - AI 助手指引

## 最高原则

### 运行

- 修复bug时不要写任何测试，直接修改代码。
- 不允许使用`py_compile`来检查语法，使用`uv run ruff check`
- 如果在工作目录出错后，使用direnv exec运行（目录无法执行时先`direnv allow`）,任何python命令，使用uv跑
- 如果没有数据调试，尝试`cp -r ~/Code/MyRepo/ptcgp-auto/data ./`, 没有启动web时启动`./scripts/web_dev.sh`，然后使用`devtools`自己调试web变更。

### 对话规则

- 不要有各种互联网「黑话」。不要出现「稳稳接住」、「打通」「你说得对」「这点我改」「收口」「砍一刀」等。

### 语言与文档规范

- 使用 **中文** 回复问题，思考使用 **中文** ，不要忘记使用 **中文** 回复
- 使用 **中文** 描述所有 文档/注释/日志输出 方便开发人员理解
- 任何关键常量变量必须带上注释说明，方法/函数/类 必须带有简要中文注释，重要/复杂的逻辑需要大致描述流程
- 不要随便清除原先代码中的 **中文** 注释
- 不要寻找 `CLAUDE.md`，使用 `AGENTS.md`

### Git 工作流

- 提交代码时，标题使用英文，内容使用 **中文**，按照 `Conventional Commits` 格式提交
- add 代码时，必须检查与本次有关的文件，不允许 `add -A`
- **不允许使用 checkout** ，你自己改了哪些内容，回退时必须使用`编辑工具`回退自己增加的部分。

### **代码质量原则**

**每次编写代码前，重读一次代码质量原则**

- 代码永远要以简洁优先，指的是不写大量的兼容代码，当无其他特殊情况时，简洁单一是首要原则
- 在原有方法上修改，需要更改调用的地方，让其保持一致性，而不是考虑兼容旧代码而牺牲方法的简洁优雅
- 新增新方法时，需要清理带有大量重复逻辑的旧代码，防止代码膨胀
- 每次编写代码前，永远不重复造轮子，永远要能够编写代码前 从以往读到的代码 尝试复用相同逻辑，而不是在各个文件写相同的代码逻辑而使程序完全不可维护
- 编写代码时，一定要懂得模块化设计，高内聚低耦合原则
- 重构代码时，不要给我写任何所谓「兼容」代码，必须将所有旧代码清理，必须将所有调用的地方改成新函数或者新调用。不准留下任何旧代码，不准使代码膨胀。必须测试每个新函数与新调用是否生效，直到和原先功能没有差异。
- 每一次重构代码，如果删除的代码少于新增的代码行数（排除测试代码/文档等非主逻辑代码）（也就是越变越复杂），那么本次的重构为不合格重构，必须重新审视代码。
- 提交代码前，检查所有变更的文件，将没有使用的 函数/常量/变量 删除
- 入口脚本需先改 `sys.path` 时，用文件顶部 `# ruff: noqa: E402` 一次性抑制
- 类型比较优先使用 `is/is not`（例如 `typ is bool`），避免 E721

### 变更与维护规范

- 在变更代码逻辑时，同时检查 方法/类/文件开头 的注释，避免逻辑与注释不完全一致
- **当代码结构变更时，对应更新 README 和 AGENTS.md（本文件）**
- 重构时，如果被修改的文件有未提交的代码，务必先提问是否先提交代码才往下进行（防止被改变功能逻辑）
- 如果 plan 文档与实际代码不一样，则有可能 plan 文档相比代码是过时的，如果要变更一定要先询问开发者

### 代码清理与优化

- 思考每个变量的实际作用，在变更代码后，检查所有无用代码、变量、常量、函数，没有作用的代码不要留在代码中，直接移除；但是如果是注释的代码，那说明不要移除

### 技术实现细节

- 涉及像素的代码，使用基准像素值（基于 1080x1920）+ `adb.scaled_x/scaled_y` 缩放方法，不允许直接写死当前分辨率像素或使用比例常量；基准像素常量应提前到代码开头，并写明注释说明来源和作用
- 出现 `No module named 'xxx'` 时要设置 `PYTHONPATH=src`
- 不准硬编码 ocr 出来的文字内容，要考虑 locales 配置，可以只优先配置 zh_hant 不处理其他语言，但是不能硬编码
- ** 不要他妈的往`core/`或者`infra/`里面加任何 涉及业务细节的东西，你他妈给我看清楚这两个目录是干什么的 **
- 自动选包策略与调参脚本必须共享同一套常量配置（`config/constants.py`），禁止脚本私有参数与正式策略漂移

### 语言/本地化（强制）

- 语言配置单一来源：`src/ptcgp_auto_v2/config/lang.py`
- 禁止任何“推断/归一化/兼容”逻辑（例如 `startswith("zh")`、`en-US -> en`、alias 映射、遍历 keys 自动回退等）；调用方必须显式传入标准键值
- 禁止通过推导式/派生生成映射与常量（如 dict comprehension 反向映射、`list(dict.keys())`、运行时校验等）；需要的映射全部用确定的字面量 map 写死
- 禁止引入项目原本不存在的新 locale/web_lang 变体（例如为了“兼容”新增 `zh_hant_hk` 之类）；要支持就先改数据模型/调用链，不准在底层偷加
- Web i18n 只接受 `web/locales/*.json` 文件名作为语言键；`Accept-Language` 只做精确命中，不做任何映射推断
- OCR 语言使用确定的 `DEFAULT_OCR_LANGUAGES`；需要变更 OCR 识别语言只能改 `config/lang.py` 的该常量，不准在业务层硬编码

### 数据库规范

- **数据库时间字段统一使用本地时间（localtime）**：
  - Schema 默认值使用 `DEFAULT (datetime('now', 'localtime'))` 而非 `CURRENT_TIMESTAMP`
  - Python 代码使用 `datetime.now()` 获取本地时间
  - SQL 查询中时间比较使用 `datetime('now', 'localtime', ...)` 格式
  - 禁止混用 UTC 和本地时间，避免时区转换问题

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
5. **子包推断**: `PackOpeningTaskBase` 已集成两阶段子包推断（滑动页模板优先 + 结果页卡牌兜底），支持 `exclude_promo` 排除 PROMO 干扰。动态模板在会话结束后自动清理。

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **模型来源**: YOLO 模型从 `shelken/ptcgp-assets` 自动下载
- **Hash 计算**: 使用 scipy DCT 实现，比纯 Python 快 100-1000 倍
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)
  - **重要**: 为保持灵活性，**所有物理外键 (Foreign Key) 约束已被移除**。表之间的关系由 SQLAlchemy/SQLModel 的逻辑外键 (`Relationship` with `primaryjoin`) 维护。
  - 修改模型后无需迁移（目前自动初始化，复杂变更需手动处理）
  - 数据迁移：如需变更 Schema，请参考 `scripts/migration_v2_remove_fks.py` 编写类似的迁移脚本。目前不依赖 Alembic 进行自动迁移。
- **时间处理**: 统一使用 `localtime`，禁止使用 UTC
