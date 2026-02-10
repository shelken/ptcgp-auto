<h3 align="center">
<img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
PTCGP Auto
</h3>

<p align="center">
  🇨🇳 中文 | <a href="README_EN.md">🇺🇸 English</a>
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-8AADF4?style=for-the-badge&logo=python&logoColor=white&labelColor=363a4f)]()
[![macOS](https://img.shields.io/badge/macOS-only-CAD3F5?style=for-the-badge&logo=apple&logoColor=white&labelColor=363a4f)]()
[![License](https://img.shields.io/badge/License-MIT-A6DA95?style=for-the-badge&labelColor=363a4f)]()

</div>

---

Pokemon TCG Pocket 自动化助手，基于 ADB 和 图像识别技术。
**v2 版本全新架构**：采用任务队列 + 多设备调度模式，专为多账号日常托管设计。

## ✨ 核心功能 (v2)

- **多账号管理**：自动轮换账号，支持数十个账号托管
- **任务队列架构**：支持 `每日开包`、`领取奖励`、`领取礼物`、`得卡挑战` 等原子任务
- **智能调度**：根据任务优先级和设备空闲状态自动分配任务
- **数据持久化**：使用 SQLite 记录账号信息、任务状态和开包历史
- **Web 可视化界面**：内置现代化 Web UI，支持开包记录查看、高级筛选（稀有度/类型）、多视图切换及移动端适配
- **断点续传**：任务执行失败自动重试，进程重启后自动恢复进度
- **YOLO+感知哈希卡牌识别**：使用 YOLO 检测+感知哈希匹配自动识别开包结果，替代传统模板匹配
- **账号卡牌采集**：在卡牌列表页筛选高稀有度并写入账号卡牌关联表

## 🚀 快速开始

### 1. 环境准备

推荐使用 [Nix](https://nixos.org/) 管理环境（可选）：

```bash
nix develop
# 或
direnv allow
```

手动安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 启动 v2 守护进程

```bash
# 自动发现 BlueStacks 模拟器并启动守护模式
python main_v2.py --daemon

# 指定设备启动
python main_v2.py --daemon -d 127.0.0.1:5555
```

## 📦 模型自动下载

首次启动时会自动从 `shelken/ptcgp-assets` 仓库下载：
- **macOS**: CoreML 格式模型 (`best.mlpackage`)
- **其他平台**: PyTorch 格式模型 (`best.pt`)

模型文件保存在 `data/models/` 目录，下载完成后自动加载到内存。

### 3. 常用命令

```bash
# 查看帮助
python main_v2.py --help

# 列出所有账号
python main_v2.py --list-accounts

# 列出支持的任务类型
python main_v2.py --list-tasks

# 手动执行单次任务（调试用）
python main_v2.py --task open_pack --account 1

# 同步当前设备登录的账号到数据库
python main_v2.py --sync-account
```

## 🏗️ 架构说明

v2 版本采用 `Scheduler` (调度器) + `Executor` (执行器) 架构：

- **Scheduler**: 负责生成任务、监控设备状态、分发任务。
- **Executor**: 运行在具体设备线程中，负责执行原子任务逻辑（如 OCR 识别、点击操作）。
- **Database**: SQLite (`data/ptcgp_v2.db`) 存储所有状态，确保数据安全。

## ⚙️ 自动扩缩容（BlueStacks）

系统支持根据任务积压自动启动/关闭 BlueStacks 实例，仅管理配置文件中以 `auto-` 开头的实例：

- 实例来源：`/Users/Shared/Library/Application Support/BlueStacks/bluestacks.conf`
- 实例筛选：仅 `auto-` 前缀
- 扩容逻辑：`pending` 达到阶梯阈值后按需启动实例
- 缩容逻辑：空闲设备数超过最小值且空闲时间超过阈值时关闭实例

可在 `Settings` 中配置：

```
auto_scale_emulators = False
auto_scale_instance_prefix = "auto-"
auto_scale_min_idle_devices = 1
auto_scale_max_devices = 2
auto_scale_pending_step = 10
auto_scale_eval_interval_seconds = 60
auto_scale_idle_seconds = 180
```

## 📂 文件结构

```
ptcgp-auto/
├── main_v2.py                  # v2 入口（推荐）
├── main.py                     # v1 入口（旧版对战，即将在 v2 中重构）
├── debug_tool.py               # 调试工具
├── src/
│   ├── ptcgp_auto_v2/          # v2 核心代码
│   │   ├── core/               # 调度核心 (Scheduler, Executor, TaskSchedule, Hooks)
│   │   │   ├── task_status.py  # 任务状态定义
│   │   ├── tasks/              # 任务实现 (OpenPack, CollectAccountCards...)
│   │   ├── db/                 # 数据库层 (SQLAlchemy/SQLite)
│   │   ├── hooks/              # Hook 实现
│   │   ├── infra/              # 基础设施层
│   │   │   ├── adb.py          # ADB 控制封装
│   │   │   ├── ocr.py          # OCR 引擎封装
│   │   │   ├── model_manager.py    # [新增] YOLO模型管理
│   │   │   ├── card_hash_manager.py # [新增] 卡牌Hash索引管理
│   │   │   ├── yolo_card_recognizer.py # [新增] YOLO+Hash识别器
│   │   │   └── icon_group_detector.py # 稀有度图标分组检测
│   │   │   ├── page_detector.py  # 页面检测器
│   │   │   └── account_switcher.py # 账号切换逻辑
│   │   ├── web/                # Web UI (FastAPI/HTMX)
│   │   │   ├── app.py           # Web 入口（初始化与路由挂载）
│   │   │   ├── routers/         # 路由层
│   │   │   ├── services/        # 业务层
│   │   │   ├── queries/         # 查询层
│   │   │   ├── utils/           # i18n/模板/视图辅助
│   │   │   └── static/js/       # 前端模块化入口
│   │   ├── config/             # 配置文件
│   │   ├── services/           # 业务服务层
│   │   └── utils/              # 工具函数
│   │       └── action_result.py # 动作结果数据结构
│   └── ptcgp_auto/             # v1 旧版代码 (Legacy)
└── docs/                       # 文档
```

## ⚠️ v1 旧版功能 (Legacy)

v1 版本主要用于单人对战刷经验，目前作为遗留模块存在，后续将被迁移至 v2 架构的任务体系中。

```bash
# 启动 v1 自动对战
python main.py
```

## 开发指南

请参考 [AGENTS.md](AGENTS.md) 获取详细的开发和代码规范指引。

## License

MIT
