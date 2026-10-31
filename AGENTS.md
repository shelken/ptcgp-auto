## 约束

- 用 uv/bun；Python 命令统一用 uv; 不使用pip
- 开发环境由 mise 管理(`mise.toml`),shell integration 自动按目录加载工具与 `.venv`；首次进入执行 `mise trust && mise run setup`
- 禁止python命令使用在前面`PYTHONPATH=src`
- 编写(edit)代码前, 先看`tdd`skill(如果有), 测试驱动开发
- 多worktree开发时先确定主main所在位置
- 代码提交前, 检查关键文档 AGENTS.md/README.md 和 `专题文档`(如果涉及), 修正过时的地方/错误的地方; 新增部分应该用户允许

## 子代理使用原则

- prompt给足需求/目的/目标、上下文、相关代码、风险点、踩过哪些坑、做过哪些尝试

## 重构原则

- 优雅、精巧
- 避免补丁式和膨胀式修改
- 功能保持一致
- 重构时，目标文件若有未提交代码，先问是否先提交

## 审查代码原则

- 先全部改完，再统一审
- 审查原功能实现，也审查改动对使用方和关联代码的影响，识别风险
- 代码符合代码质量原则
- 遇到重构或优化时，评估功能影响、优化证据、优化幅度、兼容性、旧代码去除情况、实现优雅度
- 没问题时直接说`All OK`
- 审查范围只限本次相关代码

## 语言与文档规范

- 文档、注释、日志输出统一 **中文**, 保留原有 **中文** 注释
- 语言配置单一来源：`src/ptcgp_auto_v2/config/lang.py`

## Git 工作流

- 每次代码变更前必须回看相关 `git log` / `git blame` / `git show` 历史，确认现有实现的设计理由；看不懂原意或历史证据不足时，先问用户再改
- 提交前检查所有函数/常量/变量，清理未使用代码；Python 用 vulture/ruff(uv)，TS/JS 用 knip/ESLint(bun)；必须`prek run`
- `Conventional Commits`; 执行commit命令时**必须**使用`Heredoc`语法

## Agents Remind

### 配置优先级

- 配置统一走环境变量与 CLI 参数，**不再支持 `.env`**（已彻底移除自实现的 load_dotenv）
- 优先级固定为 **CLI 参数 > 环境变量 > 代码默认值**
- `main.py` 构造 Settings 必须用 `Settings.from_env()` 先读环境变量，再用 CLI 参数覆盖；禁止回退到裸 `Settings()`，否则环境变量不生效
- argparse 中可被环境变量覆盖的参数（如 `-w/--workers`）default 设为 `None` 以区分「未传」，避免默认值反向覆盖环境变量
- 新增可配置项时，同步在 `Settings.from_env()` 注册环境变量读取，并在 README 配置表登记

### 卡牌哈希跨仓库一致性

- 感知哈希算法在两个仓库各有一份独立拷贝：`ptcgp-assets/scripts/generate_hashes.py`（生成端）与 `ptcgp-auto/src/ptcgp_auto_v2/utils/perceptual_hash.py`（使用端）
- 两端通过 JSON 里的 `_algo_version` 版本号对齐；ptcgp-auto 加载时版本不匹配则忽略 JSON，回退卡图下载
- **修改算法必须同步两端并升级 `_algo_version`**，否则会写入错误哈希导致识别全错
- ptcgp-assets 侧有 `tests/test_hashes.py` 做一致性回归，改算法后必须跑通

## **代码质量原则**

**写代码前重读一次代码质量原则**

- 简洁优先；默认走简洁单一
- 遵守FAILFAST；少写兼容、防御、补丁式代码
- 新增方法前优先找旧方法，复用或重写；先复用已有逻辑，避免重复造轮子
- 新函数/新文件/新变量 先问：是否必须；是否已有相似实现；是否适合复用或基于旧实现调整；然后选最简路径
- 复杂功能做模块化设计，控制设计规模

## 调试与运维

- 必要时直接通过 `uv run python debug_tool.py -a [ADB_PORT] --template [template_name]` 查看当前页面 OCR 和模板命中
- 长时间任务优先请求人工接管；支持后台运行的命令除外
- 缺调试数据时，在当前 worktree 非 主工作区 可执行`cp -r {主工作区}/data ./`；
- web 没启动时先跑`./scripts/web_dev.sh`；然后用`playwright-cli`自测 web 变更
- `rsync -avhP yuuko.local:~/Code/MyRepo/ptcgp-auto/data ./` 当需要最新生产数据进行分析与排查时,把数据拿过来
- E2E device 验证前先做 `adb shell` 和 `uiautomator2 connect` 健康检查，再决定是否重启模拟器
- 同一轮定位里，没有证据证明实例已经失活时，不准反复重启；一次重启后必须先验证恢复结果
- task 成功不等于流程验证成功；必须检查日志，确认当前测试目标确实被执行，不能把跳过/不满足流程当成功
- 每次修复完tasks目录中的bug, 必须e2e device实机验证对应task

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
uv run python main_v2.py --task open_pack --account 300 --debug
```

## 调试与开发

- **新增任务**: 在 `src/ptcgp_auto_v2/tasks/` 创建新文件，继承 `Task` 类并使用 `@TaskRegistry.register` 装饰器。
- **页面定义**: 在各自 task 中定义页面识别规则。
- **本地测试**: 使用 `uv run python main_v2.py --task <task_name> --account <id> --debug` 单独测试任务。

## 注意事项

- **平台限制**: 仅支持 macOS（依赖 Apple Vision Framework）
- **数据库**: 使用 SQLite (`data/ptcgp_v2.db`)

## 专题文档

- [数据库规范](src/ptcgp_auto_v2/db/AGENTS.md)
- [核心任务编写规范](src/ptcgp_auto_v2/tasks/AGENTS.md)
- [前端页面规范](src/ptcgp_auto_v2/web/AGENTS.md)
- [E2E测试规范](src/ptcgp_auto_v2/tests/e2e/AGENTS.md)
