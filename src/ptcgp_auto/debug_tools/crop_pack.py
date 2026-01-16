"""
卡包模板截取工具

交互式截取卡包封面模板，支持循环操作和模板匹配验证。
"""

from pathlib import Path
from typing import Optional

from .region_selector import select_region, get_cached_roi
from .terminal_preview import preview_image_inline, get_terminal_support


def _calculate_scale(adb_controller, pack_code, booster_choices, get_template_path, templates_dir):
    """
    自动计算缩放比例：通过框选屏幕上的目标与已有模板对比

    Returns:
        计算出的缩放比例，失败返回 None
    """
    from PIL import Image

    # 找到第一个存在的模板
    template_path = None
    template_name = None
    for name, display in booster_choices:
        path = templates_dir / get_template_path(pack_code, name)
        if path.exists():
            template_path = path
            template_name = display
            break

    if not template_path:
        print("错误: 当前扩充包没有已存在的模板，请先截取至少一个模板")
        return None

    # 获取模板尺寸
    template_img = Image.open(template_path)
    template_w, template_h = template_img.width, template_img.height
    print(f"\n参考模板: {template_name}")
    print(f"模板尺寸: {template_w}x{template_h}")

    # 截图
    print("\n正在截图...")
    screenshot = adb_controller.screenshot()
    if not screenshot:
        print("截图失败")
        return None

    # 框选目标区域
    print("请框选屏幕上的卡包封面（与模板对应的区域）...")
    roi = select_region(screenshot)
    if roi is None:
        print("取消选择")
        return None

    x, y, w, h = roi
    print(f"选区尺寸: {w}x{h}")

    # 计算缩放比例（取宽高平均值）
    scale_w = w / template_w
    scale_h = h / template_h
    scale = (scale_w + scale_h) / 2

    print(f"\n计算结果:")
    print(f"  宽度比: {w}/{template_w} = {scale_w:.3f}")
    print(f"  高度比: {h}/{template_h} = {scale_h:.3f}")
    print(f"  平均值: {scale:.3f}")

    if abs(scale_w - scale_h) > 0.05:
        print(f"  ⚠️ 宽高比差异较大，可能框选不准确")

    return scale


def _run_detect_mode(adb_controller, pack_code, booster_choices, get_template_path, templates_dir, scale: float = None):
    """
    检测模式：截图后批量匹配所有子包

    Args:
        adb_controller: ADB 控制器
        pack_code: 扩充包代码
        booster_choices: 子包选择列表
        get_template_path: 获取模板路径的函数
        templates_dir: 模板目录
        scale: 缩放比例（None 表示使用原始尺寸）
    """
    from ..recognizer import Recognizer
    from .. import config

    # 截图
    print("\n正在截图...")
    screenshot = adb_controller.screenshot()
    if not screenshot:
        print("截图失败")
        return

    # 初始化识别器
    recognizer = Recognizer()
    recognizer.reload_templates()
    threshold = config.TEMPLATE_THRESHOLD

    # 批量匹配所有子包
    scale_info = f" @{scale:.2f}x" if scale else ""
    print(f"\n=== 检测全部子包 ({pack_code}){scale_info} ===")
    print()

    for i, (name, display) in enumerate(booster_choices, 1):
        template_rel_path = get_template_path(pack_code, name)
        template_path = templates_dir / template_rel_path

        if not template_path.exists():
            print(f"  {i}. [✗] {display:<20} 模板不存在")
            continue

        # 根据是否指定缩放比例选择匹配方法
        if scale:
            confidence = recognizer.get_template_confidence_at_scale(screenshot, template_rel_path, scale)
        else:
            confidence = recognizer.get_template_confidence(screenshot, template_rel_path)

        if confidence >= threshold:
            if scale:
                match_result = recognizer.find_template_at_scale(screenshot, template_rel_path, scale)
            else:
                match_result = recognizer.find_template(screenshot, template_rel_path)
            if match_result:
                x1, y1, x2, y2 = match_result
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                print(f"  {i}. [✓] {display:<20} 置信度: {confidence:.3f}  位置: ({cx}, {cy})")
            else:
                print(f"  {i}. [?] {display:<20} 置信度: {confidence:.3f}  匹配异常")
        else:
            print(f"  {i}. [✗] {display:<20} 置信度: {confidence:.3f}  未匹配")

    print()
    input("按回车返回...")


def run_crop_pack(adb_controller, templates_dir: Path):
    """
    运行卡包模板截取工具（循环模式）

    Args:
        adb_controller: ADB 控制器实例
        templates_dir: 模板保存根目录
    """
    from ..constants.packs import (
        get_pack_choices,
        get_booster_choices,
        get_template_path,
    )
    from .. import config

    recognizer = None  # 延迟加载
    current_scale = None  # 当前缩放比例（None 表示原始尺寸）

    pack_choices = get_pack_choices()

    while True:
        # 1. 选择扩充包
        print("\n=== 选择扩充包 ===")
        for i, (code, display) in enumerate(pack_choices, 1):
            print(f"  {i}. {display}")
        print("  0. 退出")
        print()

        try:
            pack_input = input("请输入扩充包编号: ").strip()
            if pack_input == "0" or pack_input.lower() == "q":
                print("退出")
                return
            pack_idx = int(pack_input) - 1
            if pack_idx < 0 or pack_idx >= len(pack_choices):
                print("无效的编号")
                continue
        except ValueError:
            print("请输入数字")
            continue

        pack_code = pack_choices[pack_idx][0]

        # 子包选择循环
        while True:
            booster_choices = get_booster_choices(pack_code)
            scale_display = f"{current_scale:.2f}" if current_scale else "原始"
            print(f"\n=== 选择子包 ({pack_code}) ===")
            for i, (name, display) in enumerate(booster_choices, 1):
                # 检查模板文件是否存在
                template_rel_path = get_template_path(pack_code, name)
                template_path = templates_dir / template_rel_path
                exists = "✓" if template_path.exists() else "✗"
                print(f"  {i}. [{exists}] {display}")
            print("  d. 检测全部（截图匹配）")
            print(f"  s. 设置缩放比例 [当前: {scale_display}]")
            print("  0. 返回上一级")
            print()

            try:
                booster_input = input("请输入子包编号: ").strip()
                if booster_input == "0" or booster_input.lower() == "b":
                    break  # 返回扩充包选择

                # 检测模式
                if booster_input.lower() == "d":
                    _run_detect_mode(
                        adb_controller, pack_code, booster_choices,
                        get_template_path, templates_dir, current_scale
                    )
                    continue

                # 设置缩放比例
                if booster_input.lower() == "s":
                    print("\n=== 设置缩放比例 ===")
                    print("预设值:")
                    for key, value in config.PACK_TEMPLATE_SCALES.items():
                        print(f"  {key}: {value}")
                    print()
                    print("输入 c 自动计算（框选屏幕上的目标）")
                    scale_input = input("输入缩放比例 (0.01-2.0, c=计算, 留空恢复原始): ").strip()
                    if not scale_input:
                        current_scale = None
                        print("已恢复原始尺寸")
                    elif scale_input.lower() == "c":
                        # 自动计算缩放比例
                        calculated_scale = _calculate_scale(
                            adb_controller, pack_code, booster_choices,
                            get_template_path, templates_dir
                        )
                        if calculated_scale:
                            current_scale = calculated_scale
                            print(f"缩放比例已设置为 {current_scale:.3f}")
                    else:
                        try:
                            new_scale = float(scale_input)
                            if 0.01 <= new_scale <= 2.0:
                                current_scale = new_scale
                                print(f"缩放比例已设置为 {current_scale:.2f}")
                            else:
                                print("缩放比例需在 0.01-2.0 范围内")
                        except ValueError:
                            print("请输入有效数字")
                    continue

                booster_idx = int(booster_input) - 1
                if booster_idx < 0 or booster_idx >= len(booster_choices):
                    print("无效的编号")
                    continue
            except ValueError:
                print("请输入数字")
                continue

            booster_name = booster_choices[booster_idx][0]

            # 截图
            screenshot = adb_controller.screenshot()
            if not screenshot:
                print("截图失败")
                continue

            # 检查是否有缓存的 ROI
            cached_roi = get_cached_roi()
            roi = None

            if cached_roi:
                x, y, w, h = cached_roi
                print(f"\n上次选区: ({x}, {y}) - ({x+w}, {y+h})  尺寸: {w}x{h}")
                choice = input("复用上次选区? [Y/n]: ").strip().lower()
                if choice != "n":
                    roi = cached_roi
                    print("使用上次选区")

            if roi is None:
                print("\n正在打开区域选择器...")
                print("操作说明：拖拽框选卡包封面特征区域 → 回车/空格确认")
                roi = select_region(screenshot)
                if roi is None:
                    continue

            x, y, w, h = roi
            cropped = screenshot.crop((x, y, x + w, y + h))

            # 保存到指定路径
            template_rel_path = get_template_path(pack_code, booster_name)
            template_path = templates_dir / template_rel_path

            template_path.parent.mkdir(parents=True, exist_ok=True)
            cropped.save(template_path)

            print(f"\n模板已保存: {template_path}")
            print(f"区域坐标: ({x}, {y}) - ({x+w}, {y+h})")
            print(f"尺寸: {w}x{h}")

            # 终端预览
            print("\n=== 模板预览 ===")
            preview_image_inline(cropped)

            # 验证模板匹配
            print("\n=== 验证模板匹配 ===")
            if recognizer is None:
                from ..recognizer import Recognizer
                from .. import config
                recognizer = Recognizer()

            # 重新加载模板（包含刚保存的）
            recognizer.reload_templates()

            # 获取置信度
            threshold = config.TEMPLATE_THRESHOLD
            confidence = recognizer.get_template_confidence(screenshot, template_rel_path)
            print(f"置信度: {confidence:.3f} (阈值: {threshold})")

            if confidence >= threshold:
                match_result = recognizer.find_template(screenshot, template_rel_path)
                if match_result:
                    mx, my = match_result[:2]
                    print(f"✅ 匹配成功! 位置: ({mx}, {my})")
            else:
                print("❌ 匹配失败，置信度过低")
                if confidence < 0.5:
                    print("   提示: 可能截取区域不正确，建议重新选择")
                elif confidence < threshold - 0.1:
                    print("   提示: 可能需要调整截取区域大小")

            # 继续留在子包选择
