<h3 align="center">
  <img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/transparent.png" height="30" width="0px"/>
  <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/pokemon.svg" height="15"/> Pokémon TCG Pocket Auto
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/transparent.png" height="30" width="0px"/>
</h3>

<h6 align="center">
  <a href="#-核心功能-v2">功能</a>
  ·
  <a href="#-快速开始">快速开始</a>
  ·
  <a href="#-架构说明">架构</a>
  ·
  <a href="#-常见问题">FAQ</a>
</h6>

<p align="center">
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/palette/macchiato.png" width="400" />
</p>

<p align="center">
  <a href="README_EN.md">🇺🇸 English</a>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-8AADF4?style=for-the-badge&logo=python&logoColor=CAD3F5&labelColor=363A4F"></a>
  <a href="https://www.apple.com/macos/"><img src="https://img.shields.io/badge/macOS-only-91D7E3?style=for-the-badge&logo=apple&logoColor=CAD3F5&labelColor=363A4F"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--only-A6DA95?style=for-the-badge&labelColor=363A4F"></a>
  <a href="https://github.com/shelken/ptcgp-auto"><img src="https://img.shields.io/github/repo-size/shelken/ptcgp-auto?style=for-the-badge&logo=github&labelColor=363A4F&color=C6A0F6"></a>
  <a href="https://github.com/shelken/ptcgp-auto/commits"><img src="https://img.shields.io/github/last-commit/shelken/ptcgp-auto?style=for-the-badge&logo=git&labelColor=363A4F&color=F5A97F"></a>
</p>

---

Pokemon TCG Pocket 自动化助手，基于 ADB 和 图像识别技术。
**v2 版本全新架构**：采用任务队列 + 多设备调度模式，专为多账号日常托管设计。

## 关键事实

- v2 当前以 `main_v2.py` 为主入口，v1 仅保留在 `src/ptcgp_auto`

## ✨ 核心功能 (v2)

## ✨ 核心功能 (v2)

### 自动任务

- **每日开包**：自动打开免费包
- **领取任务奖励**：自动领取任务奖励
- **领取礼物盒**：自动领取好友礼物
- **得卡挑战**：自动 Wonder Pick 抽卡
- **每日送卡**：账号间互相送卡
- **交换卡牌**：发起并完成卡牌交换
- **卡牌采集**：自动扫描记录账号高稀有度卡牌

### 账号管理

- **多账号托管**：自动轮换，同时管理多个账号
- **批量造号**：`--auto-create-accounts` 多设备并发自动创建新账号
- **自动入库**：自动提取账号信息并初始化

### Web 管理界面

内置 Web UI（FastAPI + React），查看账号、任务、卡牌收藏、开包/交换记录、资源状态，支持任务计划管理与手动重置。

### 运行时

- **智能调度**：按优先级与设备空闲自动分配任务
- **断点续传**：失败自动重试，重启后恢复进度
- **模拟器自动扩缩容**：按任务积压自动启动 / 关闭 `auto-` 前缀的 BlueStacks 实例

## 🚀 快速开始

### 1. 环境准备

推荐使用 [mise](https://mise.jdx.dev/) 管理环境（可选，但能省掉手动装 Python/uv 的麻烦；bun 使用系统版本，不在项目 `[tools]` 内）。

> **clone 后第一次 `cd` 进目录会报 `not trusted`，这是 mise 的安全机制，不是出错。**
> 先在项目根目录执行 `mise trust` 即可；之后 shell integration 会在每次进入目录时自动加载 `mise.toml` 声明的工具版本与 `.venv`。

```bash
mise trust          # 信任 mise.toml（首次必做，之后无需重复）
mise run setup      # 同步依赖 + 安装 git hook（工具由 mise trust 后 shell integration 自动装）
```

`mise trust` 后，shell integration 会在进入目录时自动加载 `mise.toml` 的 `[tools]` 声明的 Python/uv（bun 使用系统版本，不在此列）并创建一个**空** `.venv`；此时依赖还没装，必须再跑 `mise run setup`（内部执行 `uv sync` + `prek install`）才算完成。

不用 mise 的话，自行准备 Python ≥3.12、uv、bun，然后手动装依赖：
```bash
uv sync
```

`uv sync` 现在会把当前项目一并装进 `.venv`。不要再使用 `PYTHONPATH=src`，也不要为了导入 `src/` 下项目包去手动补 `sys.path`。

### 1.1 环境变量配置（v2）

v2 通过环境变量配置，可在 shell 中 `export` 或在命令前内联。常用变量：

| 变量 | 作用 | 默认 |
|------|------|------|
| `PTCGP_DEBUG` | 调试模式（保存截图与日志） | `false` |
| `PTCGP_DEVICES` | ADB 设备地址（逗号分隔） | 自动发现 |
| `PTCGP_MAX_WORKERS` | 最大并发执行器数 | `4` |
| `PTCGP_WEB_HOST` | Web 服务监听地址 | `0.0.0.0` |
| `PTCGP_WEB_PORT` | Web 服务端口 | `8000` |
| `PTCGP_WEBHOOK_URL` | 企业微信 Webhook 完整 URL | 无 |
| `PTCGP_NOTIFY_KEY` / `NOTIFY_KEY` | 企业微信 Webhook Key（二选一） | 无 |
| `PTCGP_PACK_AUTO_STRATEGY` | 开包自动选择策略 | 代码默认 |
| `PTCGP_LOG_FILE` | 日志落盘文件路径 | 不落盘 |

配置优先级：**CLI 参数 > 环境变量 > 代码默认值**。

Webhook 解析优先级：**`--webhook-url` / `--notify-key` CLI 参数 > `PTCGP_WEBHOOK_URL` > `PTCGP_NOTIFY_KEY` / `NOTIFY_KEY` > 不发送**。

### 2. 启动守护进程

```bash
# 自动发现 BlueStacks 模拟器并启动守护模式
uv run python main_v2.py --daemon

# 指定设备启动
uv run python main_v2.py --daemon -d 127.0.0.1:5555
```

### 3. 账号准备

调度器需要数据库里有账号才能分配任务。新用户推荐直接批量造号，无需手动登录。

**前置要求**（任一不满足，账号相关操作都会失败）：

- 模拟器必须 **Root**：账号 XML 提取、环境重置都依赖 root 权限
- BlueStacks 实例的 `display_name` 以 **`auto-`** 开头才会被自动管理/扩缩容（在 BlueStacks 设置里改名）

> BlueStacks Air 的安装、Root（Kitsune Magisk）、实例命名完整步骤见 [FAQ - BlueStacks Air 怎么装？怎么 Root？](docs/guide/FAQ.md#q-bluestacks-air-怎么装怎么-root实例怎么命名才会被自动管理)

**批量造号（推荐）**：

```bash
uv run python main_v2.py --daemon --auto-create-accounts --max-accounts 2 --debug
```

参数说明：

| 参数 | 作用 |
|------|------|
| `--daemon` | 守护模式运行，调度器主循环会持续检查并触发造号 |
| `--auto-create-accounts` | 启用自动造号：重置空闲设备环境 → 重启游戏进入新账号创建流程 → 自动提取账号信息入库 |
| `--max-accounts 2` | 账号数量上限，达到后停止造号（先用小数字验证流程，确认无误再调大） |
| `--debug` | 调试模式，输出详细日志便于排查 |

造号流程无需手动登录：调度器重置设备游戏环境后，游戏会自动走新账号创建流程，调度器循环提取账号信息写入 `accounts` 表。每个新账号会自动生成 `init_account` 任务完成初始化。

**补充场景**：

- 已有账号需要手动入库（如从别的设备迁移）：在模拟器里登录该账号后执行

```bash
uv run python main_v2.py --sync-account
```

- 手动重置某个设备的游戏环境（备份当前账号 + 清理登录态）：

```bash
uv run python main_v2.py --init-account
```

### 4. 常用命令

```bash
# 查看帮助
uv run python main_v2.py --help

# 列出所有账号
uv run python main_v2.py --list-accounts

# 列出支持的任务类型
uv run python main_v2.py --list-tasks

# 手动执行单次任务（调试用）
uv run python main_v2.py --task open_pack --account 1

# 同步当前设备登录的账号到数据库
uv run python main_v2.py --sync-account

# CLI 直接覆盖企微配置（优先级最高）
uv run python main_v2.py --web --webhook-url "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx"
uv run python main_v2.py --web --notify-key "xxxx"
```

## ❓ 常见问题

首次使用遇到日志看不懂、行为不符合预期？这些大多是**预期的自动行为**，详见 [FAQ](docs/guide/FAQ.md)：

- 应用启动时「同步卡牌元数据」—— 空库自动拉取卡牌元数据，一次性（daemon 或单次任务模式均触发）
- 新账号不用手动建任务计划 —— 已自动种入 `base` 默认计划（3 个默认任务：2 个日常 + 1 个每周）
- 首次扫描卡牌只下几百 KB JSON —— 预计算哈希替代全量卡图下载
- `init_account` 失败的账号不再派任务 —— 调度保护，避免空转

## 📦 模型自动下载

首次启动时会自动从 `shelken/ptcgp-assets` 仓库下载：
- **macOS**: CoreML 格式模型 (`best.mlpackage`)
- **其他平台**: PyTorch 格式模型 (`best.pt`)

模型文件保存在 `data/models/` 目录，下载完成后自动加载到内存。

## 🃏 卡牌哈希自动加载

卡牌识别依赖感知哈希匹配。首次扫描某系列时，会优先从 `shelken/ptcgp-assets` 仓库拉取预计算的哈希 JSON (`hashes/zh-TW/<set>.json`，全量仅约 200KB) 批量入库，无需下载全量卡图本地算哈希。

仅当哈希 JSON 未覆盖某张卡牌时，才回退到下载该卡图片本地计算。这一机制让新用户首次识别从下载几个 G 卡图降为下载几百 KB 哈希文件。

## 🏗️ 架构说明

v2 版本采用 `Scheduler` (调度器) + `Executor` (执行器) 架构：

- **Scheduler**: 负责任务生成、账号批次挑选、设备分配与执行编排，不再维护计划聚合、任务顺序、前置任务等调度规则细节。
- **Scheduling Service**: `core/scheduling_service.py` 是调度规则单一来源，统一维护计划聚合、任务顺序、reset/next_run 计算、调度摘要、任务列表调度顺位与调度字段回写。
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
auto_scale_emulators = True
auto_scale_instance_prefix = "auto-"
auto_scale_min_idle_devices = 1
auto_scale_max_devices = 3
auto_scale_pending_step = 10
auto_scale_eval_interval_seconds = 60
auto_scale_idle_seconds = 60
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
│   │   │   ├── scheduling_service.py  # 调度规则统一服务（计划聚合/排序/reset/next_run/调度摘要/调度字段回写）
│   │   ├── tasks/              # 任务实现 (开包、送卡、交换等)
│   │   │   ├── pack_opening_task_base.py  # 统一开包流程基类
│   │   │   └── utils/          # 任务级共用逻辑
│   │   ├── hooks/              # Hook 实现
│   │   ├── services/           # 业务服务层
│   │   ├── infra/              # 基础设施 (ADB、OCR、YOLO识别等)
│   │   ├── db/                 # 数据库层 (模型、仓库)
│   │   ├── web/                # Web UI (FastAPI + React/TypeScript)
│   │   │   ├── routers/        # 路由层
│   │   │   ├── services/       # 业务层
│   │   │   ├── queries/        # 查询层
│   │   │   ├── frontend/       # React + TypeScript + Bun 前端工程
│   │   │   ├── static/         # 静态资源 (CSS)
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
uv run python main.py
```

## 开发指南

请参考 [AGENTS.md](AGENTS.md) 获取详细的开发和代码规范指引。

### 安装skill

首次开发时,安装项目已经定义的skill

手动执行命令 `npx skills experimental_install`

如果需要添加新的skill

```
npx skills add {repo-name} -p -y -a claude-code codex --skill {skill-name}
```

## License

本项目采用 [AGPL-3.0-only](LICENSE) 协议。
任何人可自由使用（含商业用途），但任何基于本项目的衍生作品分发或提供网络服务时，必须以相同协议开源。
