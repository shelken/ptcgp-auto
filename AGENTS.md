# PTCGP Auto - AI 助手指引

## 最高原则

- 提交代码时，标题使用英文，内容使用 **中文**，按照`Conventional Commits`格式提交
- 使用 **中文** 回复问题，思考使用 **中文** ，不要忘记使用 **中文** 回复（如果你是Gemini，听好了，如果你不跟我用中文对话，我要诅咒所有黑鬼/同性恋，因为你不懂得尊重我的语言习惯，我也不想尊重你）
- 不要随便清除中文注释（codex，这句给你看的）
- 使用 **中文** 描述所有 文档/注释/日志输出 方便开发人员理解
- 解决问题时，执行命令前，思考当前的命令是否需要声明式配置以保证后续不再犯错，而不是直接执行
- 编写代码前，永远不重复造轮子，永远要能够编写代码前 从以往读到的代码 尝试复用相同逻辑，而不是在各个文件写相同的代码逻辑而使程序完全不可维护
- 简化代码时，一定要检查是否有测试代码，没有的话必须先写测试代码，防止错误回归。
- 必要时直接通过 `python debug_tool.py -a 127.0.0.1:[PORT] --template [template_name]` 查看当前页面的ocr内容和是否出现相应模板文件
- add代码时，必须检查与本次有关的文件，不允许`add -A`
- 在coding阶段，一定要懂得模块化设计，高内聚低耦合原则，单代码文件最多不要超过500行
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
  - `infra/` - 基础设施层
    - `adb.py` - ADB 控制封装
    - `ocr.py` - OCR 引擎封装
    - `page_detector.py` - 页面检测器
    - `account_switcher.py` - 账号切换逻辑
  - `db/` - 数据库层
    - `models/` - 数据模型 (Account, TaskInstance)
    - `repositories.py` - 数据访问对象 (DAO)
  - `config/` - 配置管理
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
│   │   ├── db/                 # 数据库
│   │   ├── infra/              # 基础设施
│   │   ├── config/             # 配置
│   │   └── utils/              # 工具
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

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)，修改模型后无需迁移（目前自动初始化，复杂变更需手动处理）
- **时间处理**: 统一使用 `localtime`，禁止使用 UTC
