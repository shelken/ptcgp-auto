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
        from ptcgp_auto.debug_tools.region_selector import select_region
        from ptcgp_auto.constants.packs import (
            get_pack_choices,
            get_booster_choices,
            get_template_path,
        )

        adb = AdbController(
            context.get_current_host(),
            context.get_current_port(),
        )
        if not adb.connect():
            print("无法连接到设备")
            return

        # 1. 选择扩充包
        pack_choices = get_pack_choices()
        print("\n=== 选择扩充包 ===")
        for i, (code, display) in enumerate(pack_choices, 1):
            print(f"  {i}. {display}")
        print()

        try:
            pack_idx = int(input("请输入扩充包编号: ")) - 1
            if pack_idx < 0 or pack_idx >= len(pack_choices):
                print("无效的编号")
                return
        except ValueError:
            print("请输入数字")
            return

        pack_code = pack_choices[pack_idx][0]

        # 2. 选择子包
        booster_choices = get_booster_choices(pack_code)
        print(f"\n=== 选择子包 ({pack_code}) ===")
        for i, (name, display) in enumerate(booster_choices, 1):
            print(f"  {i}. {display}")
        print()

        try:
            booster_idx = int(input("请输入子包编号: ")) - 1
            if booster_idx < 0 or booster_idx >= len(booster_choices):
                print("无效的编号")
                return
        except ValueError:
            print("请输入数字")
            return

        booster_name = booster_choices[booster_idx][0]

        # 3. 截图并选择区域
        screenshot = adb.screenshot()
        if not screenshot:
            print("截图失败")
            return

        print("\n正在打开区域选择器...")
        print("操作说明：拖拽框选卡包封面特征区域 → 回车/空格确认")

        roi = select_region(screenshot)
        if roi is None:
            return

        x, y, w, h = roi
        cropped = screenshot.crop((x, y, x + w, y + h))

        # 4. 保存到指定路径
        template_rel_path = get_template_path(pack_code, booster_name)
        template_path = ROOT_DIR / "templates" / template_rel_path

        # 确保目录存在
        template_path.parent.mkdir(parents=True, exist_ok=True)

        cropped.save(template_path)
        print(f"\n模板已保存: {template_path}")
        print(f"区域坐标: ({x}, {y}) - ({x+w}, {y+h})")
        print(f"尺寸: {w}x{h}")
        return

    run_cli()


if __name__ == "__main__":
    main()
