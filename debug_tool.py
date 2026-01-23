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
    parser.add_argument(
        "--crop",
        action="store_true",
        help="交互模式：截图并打开区域选择器，框选区域保存为模板",
    )
    parser.add_argument(
        "--crop-pack",
        action="store_true",
        help="交互模式：专用卡包模板截取，选择扩充包和子包后框选区域",
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="模板匹配缩放比例（如 0.22, 0.81, 1.0）",
    )
    parser.add_argument(
        "--cards",
        type=str,
        metavar="TEMPLATE",
        help="非交互模式：匹配卡牌模板（自动下载/缩放），支持路径或模板名，多个用逗号分隔",
    )
    parser.add_argument(
        "--rarity",
        type=str,
        default=None,
        help="配合 --cards 使用：仅匹配指定稀有度的卡牌 (e.g. RR, AR, SAR)",
    )
    parser.add_argument(
        "--select",
        action="store_true",
        help="配合 --cards 使用：交互式选择卡牌",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="模板匹配置信度阈值（0-1，默认 0.8）",
    )

    parser.add_argument(
        "--scale-min",
        type=float,
        default=0.1,
        help="自动缩放扫描：最小缩放比例（默认 0.1）",
    )
    parser.add_argument(
        "--scale-max",
        type=float,
        default=3.0,
        help="自动缩放扫描：最大缩放比例（默认 3.0）",
    )
    parser.add_argument(
        "--scale-step",
        type=float,
        default=0.02,
        help="自动缩放扫描：步进（默认 0.02）",
    )
    parser.add_argument(
        "--roi",
        type=str,
        default=None,
        help="匹配区域 (x,y,w,h)，例如: '100,200,500,500'。仅在指定区域内进行匹配以提升速度。",
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

    if args.ocr or args.template or args.screenshot or args.all_templates or args.cards:
        run_non_interactive(args)
        return

    if args.crop:
        # 交互式区域选择
        from ptcgp_auto.adb_controller import AdbController
        from ptcgp_auto.debug_tools.region_selector import select_and_save_template

        adb = AdbController(
            context.get_current_host(),
            context.get_current_port(),
        )
        if not adb.connect():
            print("无法连接到设备")
            return

        screenshot = adb.screenshot()
        if not screenshot:
            print("截图失败")
            return

        print("正在打开区域选择器...")
        print("操作说明：拖拽框选区域 → 回车/空格确认 → 在终端输入模板名称")
        select_and_save_template(screenshot)
        return

    if args.crop_pack:
        # 专用卡包模板截取
        from ptcgp_auto.adb_controller import AdbController
        from ptcgp_auto.debug_tools.crop_pack import run_crop_pack

        adb = AdbController(
            context.get_current_host(),
            context.get_current_port(),
        )
        if not adb.connect():
            print("无法连接到设备")
            return

        run_crop_pack(adb, ROOT_DIR / "templates")
        return

    run_cli()


if __name__ == "__main__":
    main()
