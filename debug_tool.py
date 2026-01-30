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
    parser.add_argument(
        "--test-pack",
        type=str,
        metavar="ACTION",
        choices=["download", "compare", "match", "batch", "roi", "list", "clear"],
        help="卡包测试模式: download=下载, compare=对比, match=匹配测试, batch=批量测试, list=列出, clear=清除",
    )
    parser.add_argument(
        "--booster",
        type=str,
        metavar="NAME",
        help="指定子包名称（多个用逗号分隔，如 Charizard,Mewtwo）",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="快速测试模式：与 --test-pack roi 配合，交互式选择卡包并立即测试匹配",
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

    # 处理卡包测试命令
    if args.test_pack:
        _run_pack_test(args)
        return

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


def _run_pack_test(args):
    """运行卡包测试命令"""
    from ptcgp_auto.debug_tools.pack_tester import (
        test_download,
        test_compare,
        test_match,
        test_batch,
        test_roi_interactive,
        test_quick_match,
        list_all_packs,
        clear_packs,
    )

    action = args.test_pack

    if action == "list":
        list_all_packs()
        return

    if action == "clear":
        clear_packs(args.booster)
        return

    if action == "download":
        if not args.booster:
            print("错误: --download 需要指定 --booster 参数")
            print(
                "示例: python debug_tool.py --test-pack download --booster Charizard,Mewtwo"
            )
            return
        boosters = [b.strip() for b in args.booster.split(",")]
        test_download(boosters)
        return

    if action == "compare":
        if not args.booster:
            print("错误: --compare 需要指定 --booster 参数")
            print("示例: python debug_tool.py --test-pack compare --booster Charizard")
            return
        test_compare(args.booster)
        return

    # 以下命令需要 ADB 连接
    from ptcgp_auto.adb_controller import AdbController
    from ptcgp_auto.debug_tools import context

    adb = AdbController(
        context.get_current_host(),
        context.get_current_port(),
    )
    if not adb.connect():
        print("无法连接到设备")
        return

    if action == "match":
        if not args.booster:
            print("错误: --match 需要指定 --booster 参数")
            print(
                "示例: python debug_tool.py -a 5755 --test-pack match --booster Charizard"
            )
            return
        threshold = args.threshold or 0.8
        test_match(adb, args.booster, scale=args.scale, threshold=threshold)
        return

    if action == "batch":
        threshold = args.threshold or 0.8
        boosters = None
        if args.booster:
            boosters = [b.strip() for b in args.booster.split(",")]
        test_batch(adb, boosters=boosters, scale=args.scale, threshold=threshold)
        return

    if action == "roi":
        if args.quick:
            # 快速测试模式：交互式选择卡包并立即测试匹配
            threshold = args.threshold or 0.8
            test_quick_match(adb, threshold=threshold)
            return
        if not args.booster:
            print("错误: --roi 需要指定 --booster 参数或使用 --quick 参数")
            print(
                "示例: python debug_tool.py -a 5755 --test-pack roi --booster Charizard"
            )
            print(
                "      python debug_tool.py -a 5755 --test-pack roi --quick  # 快速测试模式"
            )
            return
        threshold = args.threshold or 0.8
        test_roi_interactive(adb, args.booster, threshold=threshold, scale=args.scale)
        return


if __name__ == "__main__":
    main()
