#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTCGP 调试工具 - 精简版

用于调试和测试的 CLI 工具，支持模板匹配、OCR识别、区域截取等功能。

基本用法:
    python debug_tool.py -a 5555 --ocr
    python debug_tool.py -a 5555 --template icon_yes --scale 0.67
    python debug_tool.py -a 5555 --test-pack match --booster Charizard
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# 添加项目路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from ptcgp_auto import config
from ptcgp_auto.recognizer import get_recognizer
from ptcgp_auto_v2.tools.context import get_adb, set_current_address
from ptcgp_auto_v2.tools.template_loader import (
    load_system_template,
    load_template_from_path,
)

if TYPE_CHECKING:
    from typing import Optional, Tuple
    from PIL import Image
    from ptcgp_auto.adb_controller import AdbController
    from ptcgp_auto.recognizer import Recognizer


# =============================================================================
# 常量定义
# =============================================================================

# 卡包测试支持的动作列表
PACK_TEST_ACTIONS = ["download", "compare", "match", "batch", "roi", "list", "clear"]

# 不需要 ADB 连接的命令
NO_ADB_COMMANDS = {"list", "clear", "download", "compare"}


# =============================================================================
# 工具函数
# =============================================================================

def parse_address(address: str | None) -> Tuple[Optional[str], Optional[int]]:
    """
    解析 ADB 地址字符串

    Args:
        address: 地址字符串，格式为 "host:port" 或 "port"

    Returns:
        (host, port) 元组，如果解析失败返回 (None, None)
    """
    if not address:
        return None, None

    if ":" in address:
        parts = address.split(":")
        return parts[0], int(parts[1])
    return None, int(address)


def take_screenshot(adb: AdbController) -> Optional[Image.Image]:
    """
    截图并返回图像对象

    Args:
        adb: ADB 控制器实例

    Returns:
        PIL Image 对象，失败返回 None
    """
    img = adb.screenshot()
    if img is None:
        print("ERROR: 截图失败")
    return img


def save_screenshot(img: Image.Image, filename: str = "screenshot.png") -> Path:
    """
    保存截图到调试目录

    Args:
        img: PIL Image 对象
        filename: 保存文件名

    Returns:
        保存的文件路径
    """
    from ptcgp_auto_v2.tools.context import get_debug_dir

    debug_dir = get_debug_dir()
    filepath = debug_dir / filename
    img.save(filepath)
    return filepath


def parse_roi(roi_str: str) -> Optional[Tuple[int, int, int, int]]:
    """
    解析 ROI 字符串

    Args:
        roi_str: ROI 字符串，格式为 "x,y,w,h"

    Returns:
        (x, y, w, h) 元组，解析失败返回 None
    """
    try:
        parts = roi_str.split(",")
        if len(parts) != 4:
            return None
        return tuple(int(p.strip()) for p in parts)
    except (ValueError, AttributeError):
        return None


def crop_image(
    img: Image.Image, roi: Tuple[int, int, int, int]
) -> Tuple[Image.Image, Tuple[int, int]]:
    """
    裁剪图像

    Args:
        img: 原始图像
        roi: (x, y, w, h) 裁剪区域

    Returns:
        (裁剪后的图像, (offset_x, offset_y)) 元组
    """
    x, y, w, h = roi
    cropped = img.crop((x, y, x + w, y + h))
    return cropped, (x, y)


# =============================================================================
# 命令处理函数
# =============================================================================

def handle_screenshot(adb: AdbController) -> None:
    """处理 --screenshot 命令"""
    img = take_screenshot(adb)
    if img is None:
        return

    filepath = save_screenshot(img)
    print(f"SCREENSHOT: {filepath}")


def handle_ocr(adb: AdbController, recognizer: Recognizer) -> None:
    """处理 --ocr 命令"""
    img = take_screenshot(adb)
    if img is None:
        return

    results = recognizer.ocr_full_screen(img)

    items = []
    for item in results:
        text = item["text"]
        box = item["box"]
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        items.append(f'"{text}"@({cx},{cy})')

    print(f"OCR({len(results)}): {', '.join(items)}")


def handle_template(
    adb: AdbController,
    recognizer: Recognizer,
    template_name: str,
    scale: float | None,
    threshold: float | None,
    all_matches: bool,
    roi_str: str | None,
) -> None:
    """处理 --template 命令"""
    from ptcgp_auto_v2.tools.card_matcher import scan_best_scale

    img = take_screenshot(adb)
    if img is None:
        return

    # 加载模板
    if template_name.startswith("/") or template_name.startswith("~"):
        loaded_name = load_template_from_path(recognizer, template_name)
        if loaded_name is None:
            return
        template_name = loaded_name
    else:
        found_name = load_system_template(recognizer, template_name)
        if found_name:
            template_name = found_name

    # ROI 处理
    roi_offset = (0, 0)
    if roi_str:
        roi = parse_roi(roi_str)
        if roi is None:
            print(f"Invalid ROI format: {roi_str}")
            return
        img, roi_offset = crop_image(img, roi)
        print(f"ROI enabled: region={roi}")

    threshold = threshold or config.TEMPLATE_THRESHOLD

    if all_matches:
        _print_all_matches(recognizer, img, template_name, roi_offset)
    else:
        _print_single_match(recognizer, img, template_name, scale, threshold, roi_offset)


def _print_all_matches(
    recognizer: Recognizer,
    img: Image.Image,
    template_name: str,
    roi_offset: Tuple[int, int],
) -> None:
    """打印所有匹配位置"""
    boxes = recognizer.find_all_templates(img, template_name)

    if not boxes:
        print(f"TEMPLATES: {template_name} NOT_FOUND")
        return

    print(f"TEMPLATES({len(boxes)}): {template_name}")
    offset_x, offset_y = roi_offset

    for i, box in enumerate(boxes, 1):
        x1, y1, x2, y2 = box
        cx, cy = (x1 + x2) // 2 + offset_x, (y1 + y2) // 2 + offset_y
        print(
            f"  {i}: ({x1 + offset_x},{y1 + offset_y})-({x2 + offset_x},{y2 + offset_y}) "
            f"center=({cx},{cy})"
        )


def _print_single_match(
    recognizer: Recognizer,
    img: Image.Image,
    template_name: str,
    scale: float | None,
    threshold: float,
    roi_offset: Tuple[int, int],
) -> None:
    """打印单个匹配位置"""
    from ptcgp_auto_v2.tools.card_matcher import scan_best_scale

    if scale:
        confidence = recognizer.get_template_confidence_at_scale(img, template_name, scale)
        box = recognizer.find_template_at_scale(img, template_name, scale)
    else:
        confidence = recognizer.get_template_confidence(img, template_name)
        box = recognizer.find_template(img, template_name)

    print(f"CONFIDENCE: {confidence:.4f} threshold={threshold}")

    offset_x, offset_y = roi_offset

    if box:
        cx = (box[0] + box[2]) // 2 + offset_x
        cy = (box[1] + box[3]) // 2 + offset_y
        print(
            f"TEMPLATE: {template_name} @ "
            f"({box[0] + offset_x},{box[1] + offset_y})-({box[2] + offset_x},{box[3] + offset_y}) "
            f"center=({cx},{cy})"
        )
    else:
        print(f"TEMPLATE: {template_name} NOT_FOUND")
        if scale is None:
            _suggest_best_scale(recognizer, img, template_name, threshold)


def _suggest_best_scale(
    recognizer: Recognizer, img: Image.Image, template_name: str, threshold: float
) -> None:
    """扫描并建议最佳缩放比例"""
    from ptcgp_auto_v2.tools.card_matcher import scan_best_scale

    print("\nAUTO_SCALE: 扫描...")
    best_scale, best_conf = scan_best_scale(recognizer, img, template_name)
    print(f"BEST_SCALE: {best_scale} confidence={best_conf:.4f}")

    if best_conf >= threshold:
        print(
            f"✓ 推荐使用: python debug_tool.py --template {template_name} --scale {best_scale}"
        )


def handle_crop(adb: AdbController) -> None:
    """处理 --crop 命令"""
    from ptcgp_auto_v2.tools.region_selector import select_and_save_template

    img = take_screenshot(adb)
    if img is None:
        return

    print("正在打开区域选择器...")
    print("操作说明：拖拽框选区域 → 回车/空格确认 → 在终端输入模板名称")
    select_and_save_template(img)


def handle_pack_test(args: argparse.Namespace) -> None:
    """处理 --test-pack 命令"""
    from ptcgp_auto_v2.tools.pack_tester import (
        clear_packs,
        list_all_packs,
        test_batch,
        test_compare,
        test_download,
        test_match,
        test_quick_match,
        test_roi_interactive,
    )

    action = args.test_pack
    booster = args.booster
    scale = args.scale
    threshold = args.threshold or 0.8

    # 不需要 ADB 的命令
    if action == "list":
        list_all_packs()
        return

    if action == "clear":
        clear_packs(booster)
        return

    if action == "download":
        if not booster:
            print("错误: download 需要指定 --booster 参数")
            print("示例: python debug_tool.py --test-pack download --booster Charizard,Mewtwo")
            return
        test_download([b.strip() for b in booster.split(",")])
        return

    if action == "compare":
        if not booster:
            print("错误: compare 需要指定 --booster 参数")
            print("示例: python debug_tool.py --test-pack compare --booster Charizard")
            return
        test_compare(booster)
        return

    # 需要 ADB 的命令
    adb = get_adb()
    if not adb.connect():
        print("ERROR: ADB 连接失败")
        return

    if action == "match":
        if not booster:
            print("错误: match 需要指定 --booster 参数")
            print("示例: python debug_tool.py -a PORT --test-pack match --booster Charizard")
            return
        test_match(adb, booster, scale=scale, threshold=threshold)

    elif action == "batch":
        boosters = [b.strip() for b in booster.split(",")] if booster else None
        test_batch(adb, boosters=boosters, scale=scale, threshold=threshold)

    elif action == "roi":
        if args.quick:
            test_quick_match(adb, threshold=threshold)
        elif booster:
            test_roi_interactive(adb, booster, threshold=threshold, scale=scale)
        else:
            print("错误: roi 需要指定 --booster 或使用 --quick")


# =============================================================================
# 参数解析
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="debug_tool.py",
        description="PTCGP 调试工具 - 用于模板匹配、OCR识别、区域截取等调试功能",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s -a 5555 --ocr                    # OCR识别
  %(prog)s -a 5555 --template icon_yes      # 模板匹配
  %(prog)s -a 5555 --template icon_yes --all    # 查找所有匹配位置
  %(prog)s -a 5555 --crop                   # 交互式截取模板
  %(prog)s --test-pack list                 # 列出已下载卡包
        """,
    )

    # 通用参数
    general = parser.add_argument_group("通用参数")
    general.add_argument(
        "-a", "--address",
        type=str,
        default=None,
        metavar="ADDR",
        help="ADB 连接地址，格式: host:port 或 port (默认: 127.0.0.1:5555)"
    )

    # 基础功能（互斥）
    basic = parser.add_argument_group("基础功能（互斥）")
    basic.add_argument(
        "--screenshot",
        action="store_true",
        help="截图并保存到调试目录"
    )
    basic.add_argument(
        "--ocr",
        action="store_true",
        help="截图并输出 OCR 识别结果"
    )
    basic.add_argument(
        "--crop",
        action="store_true",
        help="截图并打开区域选择器，框选区域保存为模板"
    )

    # 模板匹配参数
    template = parser.add_argument_group("模板匹配参数（--template）")
    template.add_argument(
        "--template",
        type=str,
        metavar="NAME",
        help="查找指定模板名称或路径（如 icon_yes 或 /path/to/template.png）"
    )
    template.add_argument(
        "--all",
        action="store_true",
        dest="all_matches",
        help="【--template专用】查找并输出所有匹配位置"
    )
    template.add_argument(
        "--scale",
        type=float,
        default=None,
        metavar="RATIO",
        help="【--template专用】模板匹配缩放比例（如 0.22, 0.81, 1.0）"
    )
    template.add_argument(
        "--threshold",
        type=float,
        default=None,
        metavar="VAL",
        help="【--template专用】匹配置信度阈值（0-1，默认 0.8）"
    )
    template.add_argument(
        "--roi",
        type=str,
        default=None,
        metavar="X,Y,W,H",
        help="【--template专用】限制匹配区域，格式: '100,200,500,500'"
    )

    # 卡包测试参数
    pack = parser.add_argument_group("卡包测试参数（--test-pack）")
    pack.add_argument(
        "--test-pack",
        type=str,
        metavar="ACTION",
        choices=PACK_TEST_ACTIONS,
        help=f"卡包测试动作: {', '.join(PACK_TEST_ACTIONS)}"
    )
    pack.add_argument(
        "--booster",
        type=str,
        metavar="NAME",
        help="【--test-pack专用】指定子包名称（多个用逗号分隔，如 Charizard,Mewtwo）"
    )
    pack.add_argument(
        "--quick",
        action="store_true",
        help="【--test-pack roi专用】快速测试模式，交互式选择卡包"
    )

    return parser


# =============================================================================
# 主函数
# =============================================================================

def main() -> None:
    """主入口函数"""
    parser = create_parser()
    args = parser.parse_args()

    # 解析并设置 ADB 地址
    host, port = parse_address(args.address)
    set_current_address(host, port)

    # 处理卡包测试命令
    if args.test_pack:
        handle_pack_test(args)
        return

    # 需要 ADB 连接的基础功能
    adb = get_adb()
    if not adb.connect():
        print("ERROR: ADB 连接失败")
        return

    # 分发到对应处理函数
    if args.screenshot:
        handle_screenshot(adb)
    elif args.ocr:
        handle_ocr(adb, get_recognizer())
    elif args.template:
        handle_template(
            adb,
            get_recognizer(),
            args.template,
            scale=args.scale,
            threshold=args.threshold,
            all_matches=args.all_matches,
            roi_str=args.roi,
        )
    elif args.crop:
        handle_crop(adb)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
