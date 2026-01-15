"""
Unified settings loader
Priority: CLI args > Environment variables > .env file > defaults
"""

import os
import argparse
from pathlib import Path
from typing import Any, List, Tuple, Optional


# Config definition: (cli_name, env_name, type, default, help, short_flag, choices)
CONFIG_DEFS: List[Tuple[str, str, type, Any, str, Optional[str], Optional[list]]] = [
    ("address", "ADDRESS", str, None, "ADB 连接地址 (host:port 或 port)", "-a", None),
    ("language", "LANGUAGE", str, "zh_Hant", "界面语言", "-l", ["zh_Hant", "en_US"]),
    ("tutorial", "TUTORIAL", bool, False, "教程模式", "-t", None),
    ("debug", "DEBUG", bool, False, "调试模式", None, None),
    ("no_auto_battle", "NO_AUTO_BATTLE", bool, False, "禁用自动对战", None, None),
    ("notify_key", "NOTIFY_KEY", str, "", "企业微信 webhook key", None, None),
    ("no_notify_sound", "NO_NOTIFY_SOUND", bool, False, "禁用通知声音", None, None),
]


def load_dotenv() -> None:
    """
    Load .env file into os.environ.
    Uses setdefault so existing env vars are NOT overridden.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # setdefault: won't override existing env vars
        os.environ.setdefault(key, value)


def get_env_value(env_name: str, typ: type, default: Any) -> Any:
    """Get value from environment with type conversion."""
    value = os.environ.get(env_name)
    if value is None:
        return default
    if typ == bool:
        return value.lower() in ("true", "1", "yes")
    return typ(value)


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser from config definitions."""
    parser = argparse.ArgumentParser(
        description="PTCGP 单人对战自动化脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
配置优先级: CLI 参数 > 环境变量 > .env 文件 > 默认值

示例:
  python main.py -a 5556                    # 指定端口
  python main.py --notify-key YOUR_KEY      # 启用通知
  DEBUG=true python main.py                 # 环境变量启用调试
        """,
    )

    for cli_name, _, typ, _, help_text, short, choices in CONFIG_DEFS:
        flags = [f"--{cli_name.replace('_', '-')}"]
        if short:
            flags.insert(0, short)

        if typ == bool:
            parser.add_argument(*flags, action="store_true", help=help_text)
        else:
            kwargs = {"type": typ, "default": None, "help": help_text}
            if choices:
                kwargs["choices"] = choices
            parser.add_argument(*flags, **kwargs)

    return parser


def load_settings() -> dict:
    """
    Load settings with priority: CLI > env vars > .env > defaults

    Flow:
    1. Load .env into os.environ (won't override existing env vars)
    2. Parse CLI args
    3. For each config: CLI value > env value > default
    """
    load_dotenv()
    parser = create_parser()
    args = parser.parse_args()

    settings = {}
    for cli_name, env_name, typ, default, _, _, _ in CONFIG_DEFS:
        attr_name = cli_name.replace("-", "_")
        cli_value = getattr(args, attr_name, None)

        # CLI args have highest priority (for bool, only when explicitly True)
        if cli_value is not None and (typ != bool or cli_value):
            settings[cli_name] = cli_value
        else:
            # From env vars (including .env loaded) or default
            settings[cli_name] = get_env_value(env_name, typ, default)

    return settings


def apply_settings_to_config(settings: dict) -> None:
    """Apply loaded settings to config module."""
    import config

    # Parse address
    address = settings.get("address")
    if address:
        if ":" in address:
            host, port = address.rsplit(":", 1)
            config.ADB_HOST = host
            config.ADB_PORT = int(port)
        else:
            config.ADB_PORT = int(address)

    # Language
    language = settings.get("language")
    if language:
        config.load_language(language)

    # Debug
    config.DEBUG = settings.get("debug", False)

    # Auto battle
    if settings.get("no_auto_battle"):
        config.AUTO_ENABLE_AUTO_BATTLE = False

    # Notification
    notify_key = settings.get("notify_key", "")
    if notify_key:
        config.NOTIFICATION_ENABLED = True
        config.NOTIFICATION_WEBHOOK_KEY = notify_key

    if settings.get("no_notify_sound"):
        config.NOTIFICATION_SOUND = False


def print_active_settings(settings: dict) -> None:
    """Print non-default settings for user visibility."""
    printed = False
    for cli_name, _, typ, default, _, _, _ in CONFIG_DEFS:
        value = settings.get(cli_name)
        if value != default and value:
            if not printed:
                print("配置:")
                printed = True
            # Mask sensitive values
            if cli_name == "notify_key" and value:
                display = f"{value[:8]}..." if len(value) > 8 else value
            else:
                display = value
            print(f"  {cli_name}: {display}")
