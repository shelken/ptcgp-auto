# External Integrations

**Analysis Date:** 2026-02-23

## APIs & External Services

**GitHub:**
- Repository: `shelken/ptcgp-assets`
- Purpose: YOLO models and card image assets
- SDK: `requests` (HTTP API)
- Auth: Public repository (no auth required)
- Files: `src/ptcgp_auto_v2/infra/model_manager.py`

**jsDelivr CDN:**
- Purpose: Accelerated asset/model downloads (avoids GitHub rate limits)
- Base URL: `https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/`
- Usage: Model files, card images
- Files: `src/ptcgp_auto_v2/infra/model_manager.py`, `src/ptcgp_auto_v2/config/assets.py`

**Enterprise WeChat (WeCom):**
- Purpose: Push notifications for rare cards, task status, system warnings
- Endpoint: `https://qyapi.weixin.qq.com/cgi-bin/webhook/send`
- Auth: Webhook key via `PTCGP_NOTIFY_KEY` or `PTCGP_WEBHOOK_URL` env var
- Format: Markdown / Markdown_v2 (with images)
- Files: `src/ptcgp_auto_v2/infra/notifier.py`

## Data Storage

**Databases:**
- SQLite
  - Connection: Local file `data/ptcgp_v2.db`
  - Client: SQLModel (SQLAlchemy + Pydantic)
  - No foreign key constraints (logical relationships only)
  - Files: `src/ptcgp_auto_v2/db/connection.py`

**File Storage:**
- Local filesystem only
  - `data/models/` - Downloaded YOLO models
  - `data/accounts/` - Account-specific data
  - `templates/` - Image templates for UI matching
  - `debug_output/` - Debug screenshots (gitignored)

**Caching:**
- None (in-memory hash indices loaded on demand)

## Authentication & Identity

**Auth Provider:**
- None (game account management only)

**Game Account Management:**
- Method: ADB file manipulation on emulator
- XML path: `/data/data/jp.pokemon.pokemontcgp/shared_prefs/deviceAccount:.xml`
- Files: `src/ptcgp_auto_v2/infra/account_switcher.py`

**Web UI Auth:**
- None (local development server, no authentication)

## Monitoring & Observability

**Error Tracking:**
- None (local log files only)

**Logs:**
- Framework: Loguru
- Output: Console + file rotation
- Intercept: Standard `logging` redirected to Loguru
- Files: `src/ptcgp_auto_v2/utils/logger.py`

## Device Integration

**Android Emulator:**
- Platform: BlueStacks Air
- Communication: ADB over TCP (default port 5555)
- Discovery: Process-based (pgrep, lsof)
- Auto-restart: On consecutive connection failures
- Files: `src/ptcgp_auto_v2/utils/bluestacks_manager.py`

**ADB Control:**
- Library: uiautomator2
- Capabilities: Screenshot, tap, swipe, long-press, pinch, shell commands
- Files: `src/ptcgp_auto_v2/infra/adb.py`

## ML Model Pipeline

**Model Source:**
- YOLO models hosted on GitHub (`shelken/ptcgp-assets`)
- Auto-download on first use
- macOS: CoreML format (`.mlpackage` directory)
- Other platforms: PyTorch format (`.pt` file)

**Hash Index:**
- Card perceptual hashes pre-computed
- Downloaded from assets repo
- Stored locally for matching
- Files: `src/ptcgp_auto_v2/infra/card_hash_manager.py`

## CI/CD & Deployment

**Hosting:**
- Local macOS machine (no cloud deployment)

**CI Pipeline:**
- None detected

## Environment Configuration

**Required env vars:**
- `PTCGP_DEVICES` - Comma-separated ADB addresses (optional, defaults to 127.0.0.1:5555)
- `PTCGP_DEBUG` - Enable debug mode (optional)
- `PTCGP_MAX_WORKERS` - Max concurrent task executors (optional)
- `PTCGP_WEB_HOST` / `PTCGP_WEB_PORT` - Web server config (optional)
- `PTCGP_NOTIFY_KEY` / `PTCGP_WEBHOOK_URL` - WeCom notification config (optional)
- `NOTIFY_KEY` - Legacy alias for webhook key (optional)

**Secrets location:**
- `.env` file (local, gitignored)

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- WeCom webhook for notifications
  - Triggered on: rare card detection, task failure/timeout, system warnings
  - Configurable per notification scene
  - Files: `src/ptcgp_auto_v2/infra/notifier.py`, `src/ptcgp_auto_v2/config/notification.py`

## CDN & Static Assets

**Card Images:**
- CDN: jsDelivr
- Pattern: `{CDN_BASE}/{set_code}/{card_number}.png`
- Base URL: `https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/zh-TW/cards-by-set`
- Files: `src/ptcgp_auto_v2/config/assets.py`

---

*Integration audit: 2026-02-23*
