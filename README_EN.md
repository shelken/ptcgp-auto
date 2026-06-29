<h3 align="center">
<img src="https://wsrv.nl?url=https://avatars.githubusercontent.com/u/33972006?fit=cover&mask=circle&maxage=7d" width="100" alt="Logo"/><br/>
PTCGP Auto
</h3>

<p align="center">
  <a href="README.md">🇨🇳 中文</a> | 🇺🇸 English
</p>

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10+-8AADF4?style=for-the-badge&logo=python&logoColor=white&labelColor=363a4f)]()
[![macOS](https://img.shields.io/badge/macOS-only-CAD3F5?style=for-the-badge&logo=apple&logoColor=white&labelColor=363a4f)]()
[![License](https://img.shields.io/badge/License-MIT-A6DA95?style=for-the-badge&labelColor=363a4f)]()

</div>

---

Pokemon TCG Pocket automation assistant based on ADB and image recognition.
**v2 architecture**: task queue + multi-device scheduler designed for multi-account daily automation.

## ✨ Core Features (v2)

- **Multi-account management**: auto-rotate accounts, supports dozens of accounts
- **Task queue architecture**: atomic tasks like `daily pack`, `claim rewards`, `claim gifts`, `wonder pick`
- **Smart scheduling**: dispatches tasks by priority and device availability
- **Data persistence**: SQLite stores account info, task status, and pack history
- **Web UI**: modern Web UI with pack history, advanced filters (rarity/type), multiple views, and mobile support
- **Resume on failure**: auto retry and resume after process restarts
- **YOLO + perceptual-hash card recognition**: replaces template matching for pack results
- **Account card collection**: filters high-rarity cards on list pages and writes to account-card table

## 🚀 Quick Start

### 1. Environment

Recommended: manage environment with [mise](https://mise.jdx.dev/) (optional):

```bash
mise trust          # trust config on first run
mise run setup      # install tools + sync deps + install git hook
```

With shell integration configured, entering the project directory auto-loads the tool versions and `.venv` declared in `mise.toml`.

Manual dependencies:
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

## 📦 Model Auto-Download

On first launch, models are downloaded from `shelken/ptcgp-assets`:
- **macOS**: CoreML model (`best.mlpackage`)
- **Other platforms**: PyTorch model (`best.pt`)

Models are stored under `data/models/` and loaded into memory automatically.

### 3. Common Commands

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

## 🏗️ Architecture

v2 uses a `Scheduler` + `Executor` architecture:

- **Scheduler**: generates tasks, monitors devices, dispatches work.
- **Executor**: runs inside device threads, executes atomic task logic (OCR, taps).
- **Database**: SQLite (`data/ptcgp_v2.db`) for durable state.

## 📂 File Structure

```
ptcgp-auto/
├── main_v2.py                  # v2 entry (recommended)
├── main.py                     # v1 entry (legacy battles, migrating to v2)
├── debug_tool.py               # Debug tool
├── src/
│   ├── ptcgp_auto_v2/          # v2 core
│   │   ├── core/               # scheduler core (Scheduler, Executor, TaskSchedule)
│   │   ├── tasks/              # task implementations (OpenPack, CollectAccountCards...)
│   │   ├── db/                 # database layer (SQLAlchemy/SQLite)
│   │   ├── infra/              # infra layer
│   │   │   ├── adb.py          # ADB controller wrapper
│   │   │   ├── ocr.py          # OCR wrapper
│   │   │   ├── model_manager.py    # [new] YOLO model manager
│   │   │   ├── card_hash_manager.py # [new] hash index manager
│   │   │   ├── yolo_card_recognizer.py # [new] YOLO+hash recognizer
│   │   │   └── icon_group_detector.py # rarity icon grouping
│   │   │   ├── page_detector.py  # page detector
│   │   │   └── account_switcher.py # account switching
│   │   ├── web/                # Web UI (FastAPI/HTMX)
│   │   │   ├── app.py           # Web entry (init + routes)
│   │   │   ├── routers/         # routes
│   │   │   ├── services/        # services
│   │   │   ├── queries/         # queries
│   │   │   ├── utils/           # i18n/templates/view helpers
│   │   │   └── static/js/       # frontend entry
│   │   ├── config/             # config files
│   │   └── utils/              # utilities
│   │       └── action_result.py # action result struct
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

MIT
