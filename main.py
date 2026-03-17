"""
PTCGP 单人对战自动化脚本 - 主入口
"""

# ruff: noqa: E402
import sys
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from ptcgp_auto import config
from ptcgp_auto.device_discovery import discover_devices
from ptcgp_auto.logger import setup_logging, get_logger, allocate_colors
from ptcgp_auto.runner import PTCGPAuto
from ptcgp_auto.settings import load_settings, apply_settings_to_config, print_active_settings

logger = get_logger(__name__)


def get_target_devices(settings: dict, allow_fallback: bool) -> list[str]:
    """根据配置获取目标设备列表"""
    if settings.get("address"):
        devices = [f"{config.ADB_HOST}:{config.ADB_PORT}"]
    else:
        devices = discover_devices()

    # 处理排除端口
    exclude_str = settings.get("exclude", "")
    if exclude_str:
        exclude_ports = set(p.strip() for p in exclude_str.split(",") if p.strip())
        devices = [d for d in devices if d.split(":")[1] not in exclude_ports]
        if exclude_ports:
            logger.info(f"排除端口: {', '.join(sorted(exclude_ports))}")

    if not devices and allow_fallback:
        devices = [f"{config.ADB_HOST}:{config.ADB_PORT}"]

    return devices


def run_mode(settings: dict):
    """统一入口：根据模式选择执行器"""
    apply_settings_to_config(settings)

    if settings.get("tutorial"):
        config.load_mode("tutorial")
    else:
        config.load_mode("battle")

    devices = get_target_devices(settings, allow_fallback=True)
    if not devices:
        setup_logging_for_devices([], settings)
        logger.error("未发现运行中的 BlueStacks 设备")
        return

    port_colors = setup_logging_for_devices(devices, settings)
    print_active_settings(settings)

    logger.info(f"发现 {len(devices)} 个设备:")
    for addr in devices:
        logger.info(f"  - {addr}")

    # 子进程入口：指定 address 时直接运行
    if settings.get("address"):
        host, port = devices[0].split(":")
        auto = PTCGPAuto(host, int(port))
        auto.start(tutorial_mode=settings.get("tutorial", False))
        return

    # 启动子进程
    processes = []
    for addr in devices:
        port = addr.split(":")[1]
        color = port_colors.get(port)
        base_args = build_base_args(settings, color=color)
        cmd = [sys.executable, __file__, "-a", addr] + base_args
        p = subprocess.Popen(cmd)
        processes.append((addr, p))
        logger.info(f"[{port}] 已启动 (颜色: {color})")

    try:
        for addr, p in processes:
            p.wait()
    except KeyboardInterrupt:
        logger.info("正在终止所有子进程...")
        for addr, p in processes:
            p.terminate()
        for addr, p in processes:
            p.wait()


def build_base_args(settings: dict, color: str | None = None) -> list:
    """从 settings 构建子进程参数（排除 all 和 address）

    Args:
        settings: 配置字典
        color: 分配给此设备的日志颜色
    """
    args = []
    if settings.get("language"):
        args.extend(["-l", settings["language"]])
    if settings.get("tutorial"):
        args.append("-t")
    if settings.get("log_level"):
        args.extend(["--log-level", settings["log_level"]])
    if color:
        args.extend(["--log-color", color])
    if settings.get("no_auto_battle"):
        args.append("--no-auto-battle")
    if settings.get("notify_key"):
        args.extend(["--notify-key", settings["notify_key"]])
    if settings.get("no_notify_sound"):
        args.append("--no-notify-sound")
    if settings.get("allow_restart"):
        args.append("--allow-restart")
    if settings.get("allow_non_root"):
        args.append("--allow-non-root")
    return args


def setup_logging_for_devices(devices: list[str], settings: dict) -> dict:
    """统一初始化日志上下文并返回端口颜色映射"""
    log_level = settings.get("log_level", "INFO")
    log_color = settings.get("log_color")

    if not devices:
        setup_logging(port=0, level=log_level, color=log_color)
        return {}

    ports = [addr.split(":")[1] for addr in devices]
    port_colors = allocate_colors(ports)

    first_port = ports[0]
    color = log_color if log_color else port_colors[first_port]
    setup_logging(port=int(first_port), level=log_level, color=color)

    return port_colors


def main():
    """主入口"""
    # 加载配置（CLI > 环境变量 > .env > 默认值）
    settings = load_settings()

    run_mode(settings)


if __name__ == "__main__":
    main()
