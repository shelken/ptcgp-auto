# PTCGP Auto v2 架构设计

## 概述

v2 采用**任务队列架构**，解决 v1 的核心痛点：
- 缺乏任务编排能力
- 多账号状态混乱
- 代码结构难以扩展

## 核心概念

| 概念 | 说明 |
|------|------|
| **Device** | 设备资源（模拟器 ADB 地址），可被分配执行任务 |
| **Account** | 账号实体，任务状态的主体，存储在数据库 |
| **TaskPlan** | 任务计划模板，定义账号应执行的任务类型列表 |
| **TaskInstance** | 具体的任务实例（账号A的今日开包），有状态追踪 |
| **Task** | 任务类型定义，实现具体的执行逻辑 |

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Scheduler (调度器)                      │
│  - 管理设备池 DevicePool                                     │
│  - 生成任务实例（每日/每周重置逻辑）                          │
│  - 分配任务到空闲设备                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    TaskExecutor (任务执行器)                 │
│  - 绑定到一个设备                                            │
│  - 执行流程：账号切换 → 任务执行 → 状态更新                  │
│  - 错误重试和恢复机制                                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Task (任务基类)                         │
│  - 目标驱动 + 页面响应的混合执行模式                         │
│  - 定义完成条件 is_completed()                               │
│  - 处理页面响应 handle_page()                                │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
        OpenPackTask    SendGiftTask    BattleTask
           (已实现)        (待实现)        (待实现)
```

## 目录结构

```
src/ptcgp_auto_v2/                  # v2 代码目录 (6038 行)
├── __init__.py
├── main.py                         # CLI 入口 (338 行)
│
├── core/                           # 核心框架
│   ├── scheduler.py                # 调度器 (396 行)
│   ├── executor.py                 # 任务执行器 (282 行)
│   ├── device_pool.py              # 设备池 (196 行)
│   └── task_base.py                # 任务基类 + 注册表 (340 行)
│
├── tasks/                          # 任务实现（可插拔）
│   └── open_pack.py                # 开包任务 (700 行) ✓
│
├── infra/                          # 基础设施
│   ├── adb.py                      # ADB 控制 (367 行)
│   ├── ocr.py                      # OCR - Apple Vision (245 行)
│   ├── template.py                 # 模板匹配 (392 行)
│   ├── page_detector.py            # 页面检测 (354 行)
│   ├── account_switcher.py         # 账号切换 - XML 注入 (243 行)
│   └── account_syncer.py           # 账号同步 - 从设备提取 (275 行)
│
├── db/                             # 数据库层
│   ├── connection.py               # SQLite 连接 (245 行)
│   ├── models.py                   # 数据模型 (288 行)
│   └── repositories.py             # 数据访问层 (562 行)
│
├── config/                         # 配置
│   ├── settings.py                 # 运行时配置 (136 行)
│   └── pages/common.py             # 公共页面规则 (53 行)
│
├── locales/                        # 多语言
│   └── zh_Hant.py                  # 繁体中文 (47 行)
│
└── utils/                          # 工具函数
    ├── logger.py                   # 日志 (52 行)
    ├── device_discovery.py         # 设备发现 (46 行)
    ├── gesture.py                  # 手势操作 (222 行)
    ├── packs.py                    # 卡包配置 (54 行)
    └── common_handlers.py          # 通用页面处理 (63 行)
```

## 数据模型

详见 `db/models.py`：

| 模型 | 说明 |
|------|------|
| `Account` | 账号（game_id, friend_id, nintendo_id, nickname, xml_content 等） |
| `TaskPlan` | 任务计划（name, task_types JSON 数组） |
| `TaskInstance` | 任务实例（account_id, task_type, status, reset_type） |
| `PackRecord` | 开包记录（account_id, pack_code, booster_name） |

数据库表结构由 `db/connection.py` 的 `_init_schema()` 创建。

## 错误处理

三层错误处理机制（详见 `core/executor.py`）：

1. **页面级**：连续未知页面 → 尝试返回键
2. **任务级**：任务失败 → 重试 N 次，每次重启应用
3. **设备级**：设备不健康 → 从设备池移除

## CLI 用法

```bash
# 守护模式
python main_v2.py --daemon

# 列出任务/账号
python main_v2.py --list-tasks
python main_v2.py --list-accounts

# 同步当前设备账号到数据库
python main_v2.py --sync-account
python main_v2.py --sync-account -d 127.0.0.1:5556

# 单任务调试
python main_v2.py --task open_pack --account 1
python main_v2.py --task open_pack --disable-switch  # 使用设备当前账号

# 重置卡住的任务
python main_v2.py --reset-running
```

## 添加新任务

1. 在 `tasks/` 创建新文件
2. 继承 `Task` 基类，实现 `is_completed()` 和 `handle_page()`
3. 使用 `@TaskRegistry.register("task_type")` 注册
4. 在 `TaskPlan` 中配置该任务类型

参考 `tasks/open_pack.py` 的实现。

## 与 v1 的关系

- v1 (`src/ptcgp_auto/`) 保持独立，继续可用
- v2 (`src/ptcgp_auto_v2/`) 独立实现
- 共享 `templates/` 和 `data/` 目录
- 入口分离：`main.py` (v1) vs `main_v2.py` (v2)
