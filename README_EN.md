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

Automation script for Pokemon TCG Pocket solo battles, supporting any Android device or emulator connected via ADB.

## Features

- Automated solo battles (ranked battles)
- Auto-traverse levels and card packs by priority
- Multi-device support
- **Daily Pack Mode** (in development) - Auto-rotate accounts for free packs

## Run Modes

| Mode | Command | Description |
|------|---------|-------------|
| Battle Mode | `python main.py` | Default mode, automated solo battles |
| Tutorial Mode | `python main.py -t` | Unlock solo battle tutorial flow |
| Daily Pack | `python main.py --daily` | Rotate accounts for free packs (requires root) |

## Tech Stack

- **ADB Control**: adbutils
- **OCR**: Apple Vision Framework (GPU accelerated)
- **Template Matching**: OpenCV
- **State Management**: JSON

## Prerequisites

- ADB debugging enabled on device
- Game language set to **Traditional Chinese** (or configure accordingly)
- **Manually navigate to the battle menu before starting** (the screen showing "單人對戰" button)

## Installation

### Using Nix (Recommended)

```bash
nix develop
# or
direnv allow
```

### Manual Installation

```bash
pip install -r requirements.txt
```

Dependencies:
- Python 3.10+
- adbutils
- opencv-python
- Pillow
- pyobjc-framework-Vision (macOS)

## Usage

```bash
# Default connection to 127.0.0.1:5555
python main.py

# Specify ADB address
python main.py -a 5556
python main.py -a 192.168.1.100:5555

# v2: auto-discover BlueStacks devices when -d omitted
python main_v2.py --daemon

# Debug tool
python debug_tool.py
python debug_tool.py -a 5556
```

## Configuration

Edit `config.py` to view and modify all settings, including:
- `LANGUAGE` - Language setting (options: "zh_Hant", "en_US")
- `WAIT_BATTLE_CHECK_INTERVAL` - Battle check interval
- `DEBUG` - Debug mode

## Multi-Device

Each device uses an independent temp directory:

```
/tmp/ptcgp_auto_5555/state.json
/tmp/ptcgp_auto_5556/state.json
```

Reset progress:
```bash
rm /tmp/ptcgp_auto_5555/state.json
```

## File Structure

```
ptcgp-auto/
├── main.py                 # Main entry point
├── debug_tool.py           # Debug tool entry
├── src/
│   └── ptcgp_auto/
│       ├── __init__.py
│       ├── runner.py       # Main automation loop
│       ├── actions/        # Action handler module
│       │   ├── __init__.py     # Exports ActionHandler
│       │   ├── handler.py      # Facade class
│       │   ├── base.py         # Base actions
│       │   ├── battle.py       # Battle actions
│       │   ├── level.py        # Level selection
│       │   ├── deck.py         # Deck list
│       │   ├── expansion.py    # Expansion selection
│       │   ├── home.py         # Home actions
│       │   └── utils/          # Utility modules
│       │       ├── scroll.py       # Scroll helper
│       │       ├── ocr_helpers.py  # OCR utilities
│       │       └── navigation.py   # Navigation utilities
│       ├── adb_controller.py   # ADB controller
│       ├── config.py           # Configuration (with mode loading)
│       ├── daily/              # Daily pack module
│       │   ├── __init__.py
│       │   ├── runner.py       # Daily mode runner
│       │   └── pack_opener.py  # Pack opening logic
│       ├── db/                 # Database module
│       │   ├── __init__.py
│       │   └── account_db.py   # Account database
│       ├── debug_tools/        # Debug tool modules
│       ├── device_discovery.py # Device discovery
│       ├── locales/            # Multi-language configs
│       │   ├── zh_Hant.py          # Traditional Chinese main config
│       │   ├── zh_Hant_pages/      # Traditional Chinese page configs
│       │   │   ├── __init__.py     # Exports all page groups
│       │   │   ├── common.py       # Common pages
│       │   │   ├── user_info.py    # User info pages
│       │   │   ├── battle.py       # Battle mode pages
│       │   │   ├── tutorial.py     # Tutorial mode pages
│       │   │   └── daily.py        # Daily pack mode pages
│       │   └── en_US.py            # English config
│       ├── logger.py           # Logging
│       ├── notifier.py         # Notifications
│       ├── page_detector.py    # Page detector
│       ├── recognizer.py       # OCR + template matching
│       ├── recognizer_parts/   # Recognizer components
│       ├── settings.py         # Runtime settings
│       ├── state_manager.py    # State management
│       └── utils.py            # Utilities
├── templates/              # Template images
└── docs/                   # Documentation
```

## Notes

- Currently macOS only (depends on Apple Vision Framework), other platforms planned
- Game language must match `LANGUAGE` setting in `config.py`
- Make sure the game is on the battle menu before starting the script
- **Template images must be captured at 1080p resolution** (the script auto-scales templates based on actual resolution)

## License

MIT
