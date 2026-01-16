"""
PTCGP 自动化脚本 - 交互式调试工具
"""

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from ptcgp_auto.debug_tools import context
from ptcgp_auto.debug_tools.cli import run_cli
from ptcgp_auto.debug_tools.non_interactive import run_non_interactive


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PTCGP 调试工具")
    parser.add_argument(
        "-a",
        "--address",
        type=str,
        default=None,
        help="ADB 连接地址，格式: host:port 或 port (默认: 127.0.0.1:5555)",
    )
    parser.add_argument(
        "--ocr", action="store_true", help="非交互模式：截图并输出 OCR 结果"
    )
    parser.add_argument(
        "--template",
        type=str,
        metavar="NAME",
        help="非交互模式：查找指定模板并输出位置",
    )
    parser.add_argument(
        "--screenshot", action="store_true", help="非交互模式：截图并输出保存路径"
    )
    parser.add_argument(
        "--all-templates",
        type=str,
        metavar="NAME",
        help="非交互模式：查找所有匹配的模板并输出位置列表",
    )
    args = parser.parse_args()

    host = None
    port = None
    if args.address:
        if ":" in args.address:
            parts = args.address.split(":")
            host = parts[0]
            port = int(parts[1])
        else:
            port = int(args.address)

    context.set_current_address(host, port)

    if args.ocr or args.template or args.screenshot or args.all_templates:
        run_non_interactive(args)
        return

    run_cli()


if __name__ == "__main__":
    main()
