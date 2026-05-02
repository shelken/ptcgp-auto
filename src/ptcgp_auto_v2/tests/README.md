# 测试目录组织结构

测试按用途组织，不按文件类型组织。新增测试优先放入对应功能域；只有跨设备、跨进程或真实流程编排才放入 `e2e/`。

```text
src/ptcgp_auto_v2/tests/
├── unit/                    # 快速单元/轻量集成测试，不依赖真实设备
│   ├── db/                  # 数据库连接、事务、仓储边界
│   ├── infra/               # ADB、通知、外部基础设施封装
│   ├── scheduler/           # 调度器与任务分配策略
│   └── tasks/               # 单个任务的状态机和页面收尾逻辑
└── e2e/                     # 端到端测试、设备场景、进程级 harness
    └── scenarios/           # 可复用设备场景定义
```

## 放置规则

- `unit/db/`：数据库引擎、事务边界、Repository 组合行为。
- `unit/infra/`：ADB、通知器、外部系统适配层。
- `unit/scheduler/`：调度循环、空闲退避、任务选择。
- `unit/tasks/`：任务内部状态机、页面识别后的动作流、回归测试。
- `e2e/`：需要设备、进程隔离、完整任务链或场景加载器的测试。

## 命令

```bash
uv run pytest src/ptcgp_auto_v2/tests/unit -q
uv run pytest src/ptcgp_auto_v2/tests/e2e -q
uv run pytest src/ptcgp_auto_v2/tests -q
```
