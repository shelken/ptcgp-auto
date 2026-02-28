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

### 日常任务

- **每日开包**：自动打开免费包
- **领取任务奖励**：自动领取任务完成的奖励
- **领取礼物盒**：自动领取好友送的礼物
- **得卡挑战**：自动进行 Wonder Pick 抽卡

### 账号管理

- **多账号托管**：自动轮换账号，支持多账号同时管理
- **账号自动入库**：自动跑新账号创建并入库
- **账号信息同步**：定期同步昵称、等级、资源等数据

### 社交功能

- **每日送卡**：自动系统账号互相送卡，支持稳定配对策略
- **交换卡牌**：支持发起和完成卡牌交换请求
- **好友管理**：自动添加好友、清理好友关系

### 数据与识别

- **卡牌采集**：自动扫描并记录账号拥有的高稀有度卡牌
- **YOLO + 感知哈希识别**：使用深度学习检测 + 哈希匹配识别卡牌，替代传统模板匹配
- **子包智能推断**：开包时自动识别子包（模板优先+卡牌兜底），支持排除 PROMO 干扰
- **数据持久化**：使用 SQLite 记录账号信息、任务状态、开包历史、卡牌收藏

### Web 管理界面

内置现代化 Web UI，支持：

- **开包记录**：查看历史开包记录，支持稀有度/类型/系列筛选，网格/列表双视图
- **卡牌收藏**：查看所有账号拥有的卡牌，支持多列布局切换
- **账号管理**：配置开包目标、任务计划，查看账号资源状态
- **元数据同步控制台**：支持检查 -> 预览 -> 确认执行（快照驱动，先预览再写库）
- **任务监控**：实时查看任务执行状态，支持手动重置
- **好友管理**：查看好友关系、配对状态
- **交换记录**：查看交换请求状态，支持取消操作
- **多主题切换**：支持 8 种主题风格，亮色/暗色模式自适应

### 系统特性

- **智能调度**：根据任务优先级和设备空闲状态自动分配任务
- **断点续传**：任务执行失败自动重试，进程重启后自动恢复进度
- **模拟器自动扩缩容**：根据任务积压自动启动/关闭 BlueStacks 实例

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

### 1.1 使用 `.env` 配置（v2）

v2 现已支持读取项目根目录 `.env`（与 v1 一致，且不覆盖已存在的环境变量）。

示例：

```bash
PTCGP_WEB_PORT=8000
PTCGP_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
PTCGP_DEBUG=true
```

Webhook 也支持仅配置 key（兼容 v1）：

```bash
NOTIFY_KEY=xxxx
# 或
PTCGP_NOTIFY_KEY=xxxx
```

配置优先级：**CLI 参数 > 环境变量 > `.env` > 代码默认值**。

Webhook 解析优先级：**显式 URL 参数 > `PTCGP_WEBHOOK_URL` > `PTCGP_NOTIFY_KEY`/`NOTIFY_KEY` > 不发送**。

### 2. 启动守护进程

```bash
# 自动发现 BlueStacks 模拟器并启动守护模式
python main_v2.py --daemon

# 指定设备启动
python main_v2.py --daemon -d 127.0.0.1:5555
```

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

# CLI 直接覆盖企微配置（优先级最高）
python main_v2.py --web --webhook-url "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx"
python main_v2.py --web --notify-key "xxxx"
```

## 📦 模型自动下载

首次启动时会自动从 `shelken/ptcgp-assets` 仓库下载：
- **macOS**: CoreML 格式模型 (`best.mlpackage`)
- **其他平台**: PyTorch 格式模型 (`best.pt`)

模型文件保存在 `data/models/` 目录，下载完成后自动加载到内存。

## 🏗️ 架构说明

v2 版本采用 `Scheduler` (调度器) + `Executor` (执行器) 架构：

- **Scheduler**: 负责生成任务、监控设备状态、分发任务。
- **Executor**: 运行在具体设备线程中，负责执行原子任务逻辑（如 OCR 识别、点击操作）。
- **Database**: SQLite (`data/ptcgp_v2.db`) 存储所有状态，确保数据安全。

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

## ⚙️ 模拟器自动扩缩容

系统支持根据任务积压自动启动/关闭 BlueStacks 实例，仅管理配置文件中以 `auto-` 开头的实例。

可在 Settings 中配置：

```bash
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
├── main_v2.py                  # v2 主入口
├── main.py                     # v1 旧版入口 (Legacy)
├── debug_tool.py               # 调试工具
├── src/
│   ├── ptcgp_auto_v2/          # v2 核心代码
│   │   ├── core/               # 核心框架 (调度器、执行器、任务基类)
│   │   ├── tasks/              # 任务实现 (开包、送卡、交换等)
│   │   │   ├── pack_opening_task_base.py  # 统一开包流程基类
│   │   │   └── utils/          # 任务级共用逻辑
│   │   ├── hooks/              # Hook 实现
│   │   ├── services/           # 业务服务层
│   │   ├── infra/              # 基础设施 (ADB、OCR、YOLO识别等)
│   │   ├── db/                 # 数据库层 (模型、仓库)
│   │   ├── web/                # Web UI (FastAPI + HTMX)
│   │   │   ├── routers/        # 路由层
│   │   │   ├── services/       # 业务层
│   │   │   ├── queries/        # 查询层
│   │   │   ├── templates/      # Jinja2 模板
│   │   │   ├── static/         # 静态资源 (CSS/JS)
│   │   │   └── locales/        # 多语言配置
│   │   ├── config/             # 配置管理
│   │   ├── locales/            # 任务用多语言配置
│   │   └── utils/              # 工具函数
│   └── ptcgp_auto/             # v1 旧版代码 (Legacy)
└── docs/                       # 文档
```

## ⚠️ v1 旧版功能 (Legacy)

v1 版本主要用于单人对战刷经验，目前作为遗留模块存在。

```bash
# 启动 v1 自动对战
python main.py
```

## 开发指南

请参考 [AGENTS.md](AGENTS.md) 获取详细的开发和代码规范指引。

## License

MIT
