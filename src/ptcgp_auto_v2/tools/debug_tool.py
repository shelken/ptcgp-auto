#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PTCGP 调试工具 - 精简版

保留功能：
- --screenshot: 截图并保存
- --ocr: OCR识别
- --template: 模板匹配（支持 --all 输出所有匹配位置）
- --crop: 交互式区域截取
- --test-pack: 卡包测试功能
"""

import argparse
import sys
from pathlib import Path

# 添加项目路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from ptcgp_auto import config
from ptcgp_auto.recognizer import get_recognizer
from ptcgp_auto_v2.tools.context import get_adb, set_current_address


def run_screenshot(adb):
    """截图并保存"""
    img = adb.screenshot()
    if not img:
        print("ERROR: 截图失败")
        return

    from ptcgp_auto_v2.tools.context import get_debug_dir
    debug_dir = get_debug_dir()
    filepath = debug_dir / "screenshot.png"
    img.save(filepath)
    print(f"SCREENSHOT: {filepath}")


def run_ocr(adb, recognizer):
    """OCR识别"""
    img = adb.screenshot()
    if not img:
        print("ERROR: 截图失败")
        return

    results = recognizer.ocr_full_screen(img)

    # 打印结果
    items = []
    for item in results:
        text = item["text"]
        box = item["box"]
        cx = (box[0] + box[2]) // 2
        cy = (box[1] + box[3]) // 2
        items.append(f'"{text}"@({cx},{cy})')
    print(f"OCR({len(results)}): {', '.join(items)}")


def run_template(adb, recognizer, template_name, scale=None, threshold=None, all_matches=False, roi=None):
    """
    模板匹配

    Args:
        all_matches: 如果为 True，输出所有匹配位置
    """
    from ptcgp_auto.recognizer_parts.template_matcher import _normalize_template_name
    from ptcgp_auto_v2.tools.card_matcher import scan_best_scale
    from ptcgp_auto_v2.tools.non_interactive import _load_template_from_path, _find_and_load_system_template

    img = adb.screenshot()
    if not img:
        print("ERROR: 截图失败")
        return

    # 加载模板
    if template_name.startswith("/") or template_name.startswith("~"):
        # 绝对路径
        loaded_name = _load_template_from_path(recognizer, template_name)
        if not loaded_name:
            return
        template_name = loaded_name
    else:
        # 系统模板
        found_name = _find_and_load_system_template(recognizer, template_name)
        if found_name:
            template_name = found_name

    # ROI处理
    roi_offset = (0, 0)
    if roi:
        try:
            rx, ry, rw, rh = map(int, roi.split(","))
            img = img.crop((rx, ry, rx + rw, ry + rh))
            roi_offset = (rx, ry)
            print(f"ROI enabled: region=({rx},{ry},{rw},{rh})")
        except Exception as e:
            print(f"Invalid ROI format: {e}")
            return

    threshold = threshold or config.TEMPLATE_THRESHOLD

    # 所有匹配模式
    if all_matches:
        boxes = recognizer.find_all_templates(img, template_name)
        if boxes:
            print(f"TEMPLATES({len(boxes)}): {template_name}")
            for i, box in enumerate(boxes, 1):
                x1, y1, x2, y2 = box
                cx, cy = (x1 + x2) // 2 + roi_offset[0], (y1 + y2) // 2 + roi_offset[1]
                print(f"  {i}: ({x1 + roi_offset[0]},{y1 + roi_offset[1]})-({x2 + roi_offset[0]},{y2 + roi_offset[1]}) center=({cx},{cy})")
        else:
            print(f"TEMPLATES: {template_name} NOT_FOUND")
        return

    # 单匹配模式
    if scale:
        confidence = recognizer.get_template_confidence_at_scale(img, template_name, scale)
        box = recognizer.find_template_at_scale(img, template_name, scale)
    else:
        confidence = recognizer.get_template_confidence(img, template_name)
        box = recognizer.find_template(img, template_name)

    print(f"CONFIDENCE: {confidence:.4f} threshold={threshold}")

    if box:
        cx = (box[0] + box[2]) // 2 + roi_offset[0]
        cy = (box[1] + box[3]) // 2 + roi_offset[1]
        print(f"TEMPLATE: {template_name} @ ({box[0] + roi_offset[0]},{box[1] + roi_offset[1]})-({box[2] + roi_offset[0]},{box[3] + roi_offset[1]}) center=({cx},{cy})")
    else:
        print(f"TEMPLATE: {template_name} NOT_FOUND")
        if not scale:
            print("\nAUTO_SCALE: 扫描...")
            best_scale, best_conf = scan_best_scale(recognizer, img, template_name)
            print(f"BEST_SCALE: {best_scale} confidence={best_conf:.4f}")
            if best_conf >= threshold:
                print(f"✓ 推荐使用: python debug_tool.py --template {template_name} --scale {best_scale}")


def run_crop(adb):
    """交互式区域截取"""
    from ptcgp_auto_v2.tools.region_selector import select_and_save_template

    screenshot = adb.screenshot()
    if not screenshot:
        print("ERROR: 截图失败")
        return

    print("正在打开区域选择器...")
    print("操作说明：拖拽框选区域 → 回车/空格确认 → 在终端输入模板名称")
    select_and_save_template(screenshot)


def run_pack_test(args):
    """运行卡包测试命令"""
    from ptcgp_auto_v2.tools.pack_tester import (
        test_download, test_compare, test_match, test_batch,
        test_roi_interactive, test_quick_match, list_all_packs, clear_packs
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
            print("示例: python debug_tool.py --test-pack download --booster Charizard,Mewtwo")
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
    adb = get_adb()
    if not adb.connect():
        print("ERROR: ADB 连接失败")
        return

    if action == "match":
        if not args.booster:
            print("错误: --match 需要指定 --booster 参数")
            print("示例: python debug_tool.py -a PORT --test-pack match --booster Charizard")
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
            threshold = args.threshold or 0.8
            test_quick_match(adb, threshold=threshold)
            return
        if not args.booster:
            print("错误: --roi 需要指定 --booster 参数或使用 --quick 参数")
            print("示例: python debug_tool.py -a PORT --test-pack roi --booster Charizard")
            print("      python debug_tool.py -a PORT --test-pack roi --quick  # 快速测试模式")
            return
        threshold = args.threshold or 0.8
        test_roi_interactive(adb, args.booster, threshold=threshold, scale=args.scale)
        return


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="PTCGP 调试工具 - 精简版")
    parser.add_argument(
        "-a", "--address",
        type=str,
        default=None,
        help="ADB 连接地址，格式: host:port 或 port (默认: 127.0.0.1:5555)"
    )
    parser.add_argument(
        "--screenshot", action="store_true", help="截图并输出保存路径"
    )
    parser.add_argument(
        "--ocr", action="store_true", help="截图并输出 OCR 结果"
    )
    parser.add_argument(
        "--template",
        type=str,
        metavar="NAME",
        help="查找指定模板并输出位置"
    )
    parser.add_argument(
        "--all", action="store_true", help="配合 --template 使用：查找所有匹配位置"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=None,
        help="模板匹配缩放比例（如 0.22, 0.81, 1.0）"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="模板匹配置信度阈值（0-1，默认 0.8）"
    )
    parser.add_argument(
        "--roi",
        type=str,
        default=None,
        help="匹配区域 (x,y,w,h)，例如: '100,200,500,500'"
    )
    parser.add_argument(
        "--crop", action="store_true", help="截图并打开区域选择器，框选区域保存为模板"
    )
    parser.add_argument(
        "--test-pack",
        type=str,
        metavar="ACTION",
        choices=["download", "compare", "match", "batch", "roi", "list", "clear"],
        help="卡包测试模式: download=下载, compare=对比, match=匹配测试, batch=批量测试, list=列出, clear=清除"
    )
    parser.add_argument(
        "--booster",
        type=str,
        metavar="NAME",
        help="指定子包名称（多个用逗号分隔）"
    )
    parser.add_argument(
        "--quick", action="store_true", help="快速测试模式：与 --test-pack roi 配合"
    )

    args = parser.parse_args()

    # 解析地址
    host = None
    port = None
    if args.address:
        if ":" in args.address:
            parts = args.address.split(":")
            host = parts[0]
            port = int(parts[1])
        else:
            port = int(args.address)

    set_current_address(host, port)

    # 处理卡包测试命令（不需要 ADB 的命令在上面处理）
    if args.test_pack:
        run_pack_test(args)
        return

    # 需要 ADB 的命令
    adb = get_adb()
    if not adb.connect():
        print("ERROR: ADB 连接失败")
        return

    if args.screenshot:
        run_screenshot(adb)
        return

    if args.ocr:
        recognizer = get_recognizer()
        run_ocr(adb, recognizer)
        return

    if args.template:
        recognizer = get_recognizer()
        run_template(
            adb, recognizer, args.template,
            scale=args.scale,
            threshold=args.threshold,
            all_matches=args.all,
            roi=args.roi
        )
        return

    if args.crop:
        run_crop(adb)
        return

    # 如果没有参数，显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()
