## 运行

- 语法检查用`uv run ruff check`
- 用 uv/bun；Python 命令统一用 uv
- 工作目录出错后用`direnv exec . [cmd]`；目录不能执行时先`direnv allow`；不需要每条命令都执行`direnv exec`
- Python 导入规则：根目录必须有 `[build-system]`；进入环境先 `uv sync` 或 `direnv reload`；禁止`PYTHONPATH=src`
- 缺调试数据时，在当前 worktree 非 main 可执行`cp -r ~/Code/active/ptcgp-auto/data ./`；web 没启动时先跑`./scripts/web_dev.sh`；然后用`playwright-cli`自测 web 变更
- 新增功能/重构/性能优化遵循下方`开发/重构/优化 Workflow`；执行前在根目录`TODO.md`写待测清单，在根目录`PLAN.md`写当前 plan
- 新函数/新文件/新变量 先问：是否必须；是否已有相似实现；是否适合复用或基于旧实现调整；然后选最简路径

## 子代理使用原则

- 相同任务复用同一个子代理
- 审查代码必须用独立子代理；给足需求、上下文、相关代码、风险点、踩过哪些坑、做过哪些尝试

## 开发/重构/优化 Workflow

- 功能开发、重构、性能优化统一遵循本节
- 先读完相关代码、注释、计划文档，明确需求、边界、影响范围。
- 把当前任务 plan 写入项目根目录`PLAN.md`，写新计划前先清空旧内容
- 主代理使用子代理做完整审阅
- 子代理报问题后先复核再修；修完后由**同一个**子代理复审
- 全部完成后统一执行 lint、unused 检查、测试、`pre-commit run`，然后提交

## 重构原则

- 优雅、精巧
- 避免补丁式和膨胀式修改
- 功能保持一致
- 重构时，目标文件若有未提交代码，先问是否先提交
- 代码增减都看质量；优雅合理优先

## 审查代码原则

- 先全部改完，再统一审
- 审查原功能实现，也审查改动对使用方和关联代码的影响，识别风险
- 代码符合代码质量原则
- 遇到重构或优化时，评估功能影响、优化证据、优化幅度、兼容性、旧代码去除情况、实现优雅度
- 没问题时直接说`All OK`
- 审查范围只限本次相关代码

## 语言与文档规范

- 文档、注释、日志输出统一 **中文**
- 保留原有 **中文** 注释

## Git 工作流

- 提交前检查所有函数/常量/变量，清理未使用代码；Python 用 vulture/ruff(uv)，TS/JS 用 knip/ESLint(bun)；必须`pre-commit run`

## **代码质量原则**

**写代码前重读一次代码质量原则**

- 简洁优先；默认走简洁单一
- 遵守FAILFAST；少写兼容、防御、补丁式代码
- 新增方法前优先找旧方法，复用或重写；先复用已有逻辑，避免重复造轮子
- 复杂功能做模块化设计，控制设计规模

## 技术实现重要细节

- 像素相关代码用基准像素值（基于 1080x1920）+ `adb.scaled_x/scaled_y` 缩放；基准像素常量提前到文件开头，并写明来源和作用
- 出现 `No module named 'xxx'` 时，直接按项目导入规则处理
- 语言配置单一来源：`src/ptcgp_auto_v2/config/lang.py`

## 数据库规范

- **数据库时间字段统一使用本地时间（localtime）**：
- **v2 数据访问统一规则**：
  - 高层业务动作统一使用 `session_scope()` 作为事务边界
  - 所有 Repository 构造显式传入 `Session`
  - 同一动作需要多个 Repository 时，统一使用 `RepositoryFactory(session)`
  - Repository 内部禁止自建 `Session`、禁止自行 `commit`
  - 模型层禁止 `save()/update()/delete()` 写库入口
  - 事务外只传标量、`dataclass` 纯数据或视图 `dict`
  - 日志、通知、Webhook 等次要副作用放到主数据提交之后单独执行

## 调试与运维

- 必要时直接通过 `uv run python debug_tool.py -a [ADB_PORT] --template [template_name]` 查看当前页面 OCR 和模板命中
- 长时间任务优先请求人工接管；支持后台运行的命令除外

## 项目概述

PTCGP（Pokemon TCG Pocket）Python 自动化框架。
**v2 版本 (当前主版本)**：任务队列 + 调度器架构，支持多账号、多设备、原子任务。
**v1 版本 (Legacy)**：单人对战刷经验，保留在 `src/ptcgp_auto`。

## 核心架构 (v2)

源代码位于 `src/ptcgp_auto_v2/`。

## 常用命令

```bash
# v2 守护模式
uv run python main_v2.py --daemon --debug

# 调试工具
uv run python debug_tool.py

# 手动执行单次任务
uv run python main_v2.py --task open_pack --account 1 --debug
```

## 调试与开发

- **新增任务**: 在 `src/ptcgp_auto_v2/tasks/` 创建新文件，继承 `Task` 类并使用 `@TaskRegistry.register` 装饰器。
- **页面定义**: 在各自 task 中定义页面识别规则。
- **本地测试**: 使用 `uv run python main_v2.py --task <task_name> --account <id> --debug` 单独测试任务。

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)
  - **重要**: 所有物理外键 (Foreign Key) 约束已移除；表关系由 SQLAlchemy/SQLModel 逻辑外键 (`Relationship` with `primaryjoin`) 维护
  - 修改模型后无需迁移；当前自动初始化；复杂变更手动处理
