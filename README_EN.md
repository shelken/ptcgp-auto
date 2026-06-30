<h3 align="center">
  <img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/transparent.png" height="30" width="0px"/>
  <img src="https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/svg/pokemon.svg" height="15"/> Pokémon TCG Pocket Auto
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/misc/transparent.png" height="30" width="0px"/>
</h3>

<h6 align="center">
  <a href="#-core-features-v2">Features</a>
  ·
  <a href="#-quick-start">Quick Start</a>
  ·
  <a href="#-architecture">Architecture</a>
  ·
  <a href="#-faq">FAQ</a>
</h6>

<p align="center">
  <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/palette/macchiato.png" width="400" />
</p>

<p align="center">
  <a href="README.md">🇨🇳 中文</a>
</p>

<p align="center">
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Python-3.12+-8AADF4?style=for-the-badge&logo=python&logoColor=CAD3F5&labelColor=363A4F"></a>
  <a href="https://www.apple.com/macos/"><img src="https://img.shields.io/badge/macOS-only-91D7E3?style=for-the-badge&logo=apple&logoColor=CAD3F5&labelColor=363A4F"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-AGPL--3.0--only-A6DA95?style=for-the-badge&labelColor=363A4F"></a>
  <a href="https://github.com/shelken/ptcgp-auto"><img src="https://img.shields.io/github/repo-size/shelken/ptcgp-auto?style=for-the-badge&logo=github&labelColor=363A4F&color=C6A0F6"></a>
  <a href="https://github.com/shelken/ptcgp-auto/commits"><img src="https://img.shields.io/github/last-commit/shelken/ptcgp-auto?style=for-the-badge&logo=git&labelColor=363A4F&color=F5A97F"></a>
</p>

---

Pokemon TCG Pocket automation assistant based on ADB and image recognition.
**v2 architecture**: task queue + multi-device scheduler designed for multi-account daily automation.

## ✨ Core Features (v2)

### Automation Tasks

- **Daily pack opening**: auto open free packs
- **Claim mission rewards**: auto claim mission rewards
- **Claim gift boxes**: auto claim friend gifts
- **Wonder Pick**: auto Wonder Pick draws
- **Daily card gifting**: accounts send cards to each other
- **Card exchange**: initiate and complete card exchanges
- **Card collection**: auto scan and record high-rarity cards

### Account Management

- **Multi-account hosting**: auto-rotate, manage many accounts at once
- **Batch creation**: `--auto-create-accounts` creates new accounts concurrently across devices
- **Auto onboarding**: auto extract account info and initialize

### Web UI

Built-in Web UI (FastAPI + React) to view accounts, tasks, card collection, pack/exchange records, resource status, with task plan management and manual reset.

### Runtime

- **Smart scheduling**: dispatch tasks by priority and device availability
- **Resume on failure**: auto retry on failure, resume after restart
- **Emulator auto-scaling**: auto start / stop `auto-` prefixed BlueStacks instances based on task backlog

## 🚀 Quick Start

### 1. Environment

Recommended: manage environment with [mise](https://mise.jdx.dev/) (optional, but saves you from manually installing Python/uv/bun).

> **The first `cd` after clone will fail with `not trusted` — this is mise's security mechanism, not an error.**
> Run `mise trust` in the project root; after that, shell integration auto-loads the tool versions and `.venv` declared in `mise.toml` on every entry.

```bash
mise trust          # trust mise.toml (required once, no need to repeat)
mise run setup      # sync deps + install git hook (tools are auto-installed by shell integration after `mise trust`)
```

After `mise trust`, shell integration auto-loads the Python/uv/bun declared in `mise.toml` `[tools]` and creates an **empty** `.venv` on every directory entry; dependencies aren't installed yet — you must run `mise run setup` (which runs `uv sync` + `pre-commit install`) to complete setup.

If not using mise, prepare Python ≥3.12, uv, and bun yourself, then install deps manually:
```bash
uv sync
```

`uv sync` now installs the current project into `.venv` too. Do not use `PYTHONPATH=src`, and do not patch `sys.path` just to import packages from `src/`.

### 1.1 Use `.env` for v2

v2 now supports loading `.env` from project root (same behavior as v1, and existing environment variables are not overridden).

Example:

```bash
PTCGP_WEB_PORT=8000
PTCGP_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx
PTCGP_DEBUG=true
```

Webhook also supports key-only mode (v1 compatible):

```bash
NOTIFY_KEY=xxxx
# or
PTCGP_NOTIFY_KEY=xxxx
```

Priority: **CLI Args > Environment Variables > `.env` > Default Values**.

Webhook resolution priority: **Explicit URL arg > `PTCGP_WEBHOOK_URL` > `PTCGP_NOTIFY_KEY`/`NOTIFY_KEY` > disabled**.

### 2. Start v2 daemon

```bash
# Auto-discover BlueStacks and run daemon mode
uv run python main_v2.py --daemon

# Run with a specific device
uv run python main_v2.py --daemon -d 127.0.0.1:5555
```

## ❓ FAQ

Confused by startup logs or unexpected behavior? Most are **expected automatic behaviors** — see [FAQ](docs/guide/FAQ.md):

- "Syncing card metadata" on app startup — one-time pull into an empty DB (triggered by daemon or single-task mode)
- New accounts need no manual task plan — a `base` plan (3 default tasks: 2 daily + 1 weekly) is auto-seeded
- First card scan downloads only a few hundred KB of JSON — precomputed hashes replace full card-image download
- Accounts with failed `init_account` stop receiving tasks — scheduler protection against idle spinning

## 📦 Model Auto-Download

On first launch, models are downloaded from `shelken/ptcgp-assets`:
- **macOS**: CoreML model (`best.mlpackage`)
- **Other platforms**: PyTorch model (`best.pt`)

Models are stored under `data/models/` and loaded into memory automatically.

### 3. Account Setup

The scheduler needs accounts in the database before it can assign tasks. For new users, bulk account creation is recommended — no manual login required.

**Prerequisites** (account operations will fail if any is missing):

- The emulator must be **rooted**: account XML extraction and environment reset both require root
- BlueStacks instances are auto-managed/scaled only when their `display_name` starts with **`auto-`** (rename in BlueStacks settings)

> Full steps for installing BlueStacks Air, rooting it (Kitsune Magisk), and naming instances: see [FAQ - How to install/root BlueStacks Air?](docs/guide/FAQ.md#q-bluestacks-air-怎么装怎么-root实例怎么命名才会被自动管理)

**Bulk account creation (recommended)**:

```bash
uv run python main_v2.py --daemon --auto-create-accounts --max-accounts 2 --debug
```

Parameter reference:

| Flag | Purpose |
|------|---------|
| `--daemon` | Run in daemon mode; the scheduler loop continuously checks and triggers creation |
| `--auto-create-accounts` | Enable auto-creation: reset an idle device's environment → restart the game into the new-account flow → extract account info and insert into DB automatically |
| `--max-accounts 2` | Account count cap; creation stops when reached (start with a small number to verify the flow, then increase) |
| `--debug` | Debug mode with verbose logs for troubleshooting |

No manual login is needed: after the scheduler resets the device's game environment, the game enters the new-account creation flow automatically, and the scheduler repeatedly extracts account info into the `accounts` table. Each new account gets an `init_account` task to complete initialization.

**Supplementary scenarios**:

- Importing an existing account manually (e.g., migrated from another device): log into it in the emulator, then run

```bash
uv run python main_v2.py --sync-account
```

- Manually reset a device's game environment (backs up the current account + clears login state):

```bash
uv run python main_v2.py --init-account
```

### 4. Common Commands

```bash
# Help
uv run python main_v2.py --help

# List accounts
uv run python main_v2.py --list-accounts

# List supported tasks
uv run python main_v2.py --list-tasks

# Run a single task (debug)
uv run python main_v2.py --task open_pack --account 1

# Sync currently logged-in account into DB
uv run python main_v2.py --sync-account

# Override WeCom config by CLI (highest priority)
uv run python main_v2.py --web --webhook-url "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx"
uv run python main_v2.py --web --notify-key "xxxx"
```

## 🃏 Card Hash Auto-Load

Card recognition relies on perceptual-hash matching. On first scan of a set, precomputed hash JSON (`hashes/zh-TW/<set>.json`, ~200KB total) is fetched from `shelken/ptcgp-assets` and bulk-inserted — no need to download all card images to compute hashes locally.

Only cards not covered by the hash JSON fall back to downloading that single image and computing locally. This reduces first-time recognition from downloading gigabytes of images to a few hundred KB of hash files.

## 🏗️ Architecture

v2 uses a `Scheduler` + `Executor` architecture:

- **Scheduler**: generates tasks, picks account batches, allocates devices and orchestrates execution; no longer holds scheduling-rule details like plan aggregation, task order, or prerequisites.
- **Scheduling Service**: `core/scheduling_service.py` is the single source of scheduling rules — plan aggregation, task order, reset/next_run calculation, scheduling summary, task-list dispatch order, and scheduling-field writeback.
- **Executor**: runs inside device threads, executes atomic task logic (OCR, taps).
- **Database**: SQLite (`data/ptcgp_v2.db`) for durable state.

## 📂 File Structure

```
ptcgp-auto/
├── main_v2.py                  # v2 entry
├── main.py                     # v1 legacy entry
├── debug_tool.py               # debug tool
├── src/
│   ├── ptcgp_auto_v2/          # v2 core
│   │   ├── core/               # core framework (Scheduler, Executor, task base)
│   │   │   ├── scheduling_service.py  # single source of scheduling rules (aggregation/order/reset/next_run/summary/writeback)
│   │   ├── tasks/              # task implementations (open pack, send card, exchange, etc.)
│   │   │   ├── pack_opening_task_base.py  # unified pack-opening base
│   │   │   └── utils/          # task-level shared logic
│   │   ├── hooks/              # hook implementations
│   │   ├── services/           # business service layer
│   │   ├── infra/              # infrastructure (ADB, OCR, YOLO recognition, etc.)
│   │   ├── db/                 # database layer (models, repositories)
│   │   ├── web/                # Web UI (FastAPI + React/TypeScript)
│   │   │   ├── routers/        # routes
│   │   │   ├── services/       # services
│   │   │   ├── queries/        # queries
│   │   │   ├── frontend/       # React + TypeScript + Bun frontend
│   │   │   ├── static/         # static assets (CSS)
│   │   │   └── locales/        # i18n config
│   │   ├── config/             # config management
│   │   ├── locales/            # task i18n config
│   │   └── utils/              # utilities
│   └── ptcgp_auto/             # v1 legacy
└── docs/                       # docs
```

## ⚠️ v1 Legacy

v1 focuses on solo battle grinding and remains as a legacy module. It will be migrated into v2's task system.

```bash
# Start v1 automated battles
uv run python main.py
```

## Development

See [AGENTS.md](AGENTS.md) for detailed development and coding guidelines.

## License

This project is licensed under [AGPL-3.0-only](LICENSE).
Anyone is free to use it (including commercially), but any derivative work that is distributed or provided as a network service must be open-sourced under the same license.
