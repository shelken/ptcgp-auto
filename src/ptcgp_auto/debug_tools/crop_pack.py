"""
卡包模板截取工具

交互式截取卡包封面模板，支持循环操作和模板匹配验证。
"""

from pathlib import Path
from typing import Optional, List, Tuple

from .region_selector import select_region, get_cached_roi
from .terminal_preview import preview_image_inline, get_terminal_support


def _build_all_boosters(templates_dir: Path) -> List[Tuple[str, str, str, bool]]:
    """
    构建所有子包的扁平列表

    Returns:
        [(pack_code, booster_name, display, exists), ...]
        排序规则：有模板的在前（按系列排序），无模板的在后（按系列排序）
    """
    from ..constants.packs import PACKS, get_template_path

    all_boosters = []

    for pack_code, info in PACKS.items():
        boosters = info.get("boosters", [])
        if not boosters:
            # 无子包时，使用扩充包名称
            name = info["name"].replace(" ", "_")
            display = f"{pack_code} - {info['name']}"
            template_path = templates_dir / get_template_path(pack_code, name)
            exists = template_path.exists()
            all_boosters.append((pack_code, name, display, exists))
        else:
            for booster in boosters:
                name = booster.replace(" ", "_")
                display = f"{pack_code} - {booster}"
                template_path = templates_dir / get_template_path(pack_code, name)
                exists = template_path.exists()
                all_boosters.append((pack_code, name, display, exists))

    # 排序：有模板的在前，无模板的在后；同组内按系列代码排序
    def sort_key(item):
        pack_code, name, display, exists = item
        # 解析系列代码用于排序 (如 A1, A1a, B1, B1a)
        # 字母部分 + 数字部分 + 后缀
        import re

        match = re.match(r"([A-Z])(\d+)([a-z]?)", pack_code)
        if match:
            letter, num, suffix = match.groups()
            sort_tuple = (letter, int(num), suffix)
        else:
            sort_tuple = (pack_code, 0, "")
        # exists=True 排在前面 (0), exists=False 排在后面 (1)
        return (0 if exists else 1, sort_tuple, name)

    all_boosters.sort(key=sort_key)
    return all_boosters


def _calculate_scale_from_list(adb_controller, all_boosters, templates_dir):
    """
    自动计算缩放比例：通过框选屏幕上的目标与已有模板对比

    Returns:
        计算出的缩放比例，失败返回 None
    """
    from PIL import Image
    from ..constants.packs import get_template_path

    # 找到第一个存在的模板
    template_path = None
    template_display = None
    for pack_code, name, display, exists in all_boosters:
        if exists:
            template_path = templates_dir / get_template_path(pack_code, name)
            template_display = display
            break

    if not template_path:
        print("错误: 没有已存在的模板，请先截取至少一个模板")
        return None

    # 获取模板尺寸
    template_img = Image.open(template_path)
    template_w, template_h = template_img.width, template_img.height
    print(f"\n参考模板: {template_display}")
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


def _run_detect_mode(
    adb_controller, selected_items, templates_dir, scale: float = None
):
    """
    检测模式：截图后匹配选中的子包

    Args:
        adb_controller: ADB 控制器
        selected_items: 选中的子包列表 [(pack_code, name, display, exists), ...]
        templates_dir: 模板目录
        scale: 缩放比例（None 表示使用原始尺寸）
    """
    from ..recognizer import Recognizer
    from ..constants.packs import get_template_path
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

    # 批量匹配选中的子包
    scale_info = f" @{scale:.2f}x" if scale else ""
    print(f"\n=== 检测选中的 {len(selected_items)} 个子包{scale_info} ===")
    print()

    for i, (pack_code, name, display, exists) in enumerate(selected_items, 1):
        template_rel_path = get_template_path(pack_code, name)
        template_path = templates_dir / template_rel_path

        if not template_path.exists():
            print(f"  {i}. [✗] {display:<25} 模板不存在")
            continue

        # 根据是否指定缩放比例选择匹配方法
        if scale:
            confidence = recognizer.get_template_confidence_at_scale(
                screenshot, template_rel_path, scale
            )
        else:
            confidence = recognizer.get_template_confidence(
                screenshot, template_rel_path
            )

        if confidence >= threshold:
            if scale:
                match_result = recognizer.find_template_at_scale(
                    screenshot, template_rel_path, scale
                )
            else:
                match_result = recognizer.find_template(screenshot, template_rel_path)
            if match_result:
                x1, y1, x2, y2 = match_result
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                print(
                    f"  {i}. [✓] {display:<25} 置信度: {confidence:.3f}  位置: ({cx}, {cy})"
                )
            else:
                print(f"  {i}. [?] {display:<25} 置信度: {confidence:.3f}  匹配异常")
        else:
            print(f"  {i}. [✗] {display:<25} 置信度: {confidence:.3f}  未匹配")

    print()
    input("按回车返回...")


def run_crop_pack(adb_controller, templates_dir: Path):
    """
    运行卡包模板截取工具（扁平模式）

    Args:
        adb_controller: ADB 控制器实例
        templates_dir: 模板保存根目录
    """
    from ..constants.packs import get_template_path
    from .. import config

    recognizer = None  # 延迟加载
    current_scale = None  # 当前缩放比例（None 表示原始尺寸）

    while True:
        # 构建并刷新列表（每次循环重新检查模板存在状态）
        all_boosters = _build_all_boosters(templates_dir)

        scale_display = f"{current_scale:.2f}" if current_scale else "原始"
        print(f"\n=== 卡包模板截取 [缩放: {scale_display}] ===")

        # 显示列表
        for i, (pack_code, name, display, exists) in enumerate(all_boosters, 1):
            marker = "✓" if exists else "✗"
            print(f"  {i:2}. [{marker}] {display}")

        print()
        print("  d. 检测模式（选择后检测匹配）")
        print("  a. 全部检测（所有已有模板）")
        print(f"  s. 设置缩放比例 [当前: {scale_display}]")
        print("  0. 退出")
        print()

        try:
            user_input = input("请输入编号: ").strip()

            if user_input == "0" or user_input.lower() == "q":
                print("退出")
                return

            # 全部检测
            if user_input.lower() == "a":
                items_to_detect = [b for b in all_boosters if b[3]]
                if not items_to_detect:
                    print("没有可检测的项")
                    continue

                _run_detect_mode(
                    adb_controller, items_to_detect, templates_dir, current_scale
                )
                continue

            # 检测模式 - 进入子菜单选择要检测的项
            if user_input.lower() == "d":
                print(
                    "\n请输入要检测的编号 (可用逗号分隔，如 1,2,3，留空检测全部有模板的):"
                )
                detect_input = input("检测编号: ").strip()

                if not detect_input:
                    # 检测所有有模板的项
                    items_to_detect = [b for b in all_boosters if b[3]]
                else:
                    # 解析输入的编号
                    items_to_detect = []
                    for part in detect_input.split(","):
                        part = part.strip()
                        if part:
                            try:
                                idx = int(part)
                                if 1 <= idx <= len(all_boosters):
                                    items_to_detect.append(all_boosters[idx - 1])
                            except ValueError:
                                pass

                if not items_to_detect:
                    print("没有可检测的项")
                    continue

                _run_detect_mode(
                    adb_controller, items_to_detect, templates_dir, current_scale
                )
                continue

                _run_detect_mode(
                    adb_controller, items_to_detect, templates_dir, current_scale
                )
                continue

            # 设置缩放比例
            if user_input.lower() == "s":
                print("\n=== 设置缩放比例 ===")
                print("预设值:")
                for key, value in config.PACK_TEMPLATE_SCALES.items():
                    print(f"  {key}: {value}")
                print()
                print("输入 c 自动计算（框选屏幕上的目标）")
                scale_input = input(
                    "输入缩放比例 (0.01-2.0, c=计算, 留空恢复原始): "
                ).strip()
                if not scale_input:
                    current_scale = None
                    print("已恢复原始尺寸")
                elif scale_input.lower() == "c":
                    # 自动计算缩放比例
                    calculated_scale = _calculate_scale_from_list(
                        adb_controller, all_boosters, templates_dir
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

            # 解析输入的编号
            try:
                idx = int(user_input)
                if idx < 1 or idx > len(all_boosters):
                    print(f"无效的编号: {idx}")
                    continue
            except ValueError:
                print(f"无效的输入: {user_input}")
                continue

            # 进入截取模式
            pack_code, booster_name, display, exists = all_boosters[idx - 1]

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
                print(f"\n上次选区: ({x}, {y}) - ({x + w}, {y + h})  尺寸: {w}x{h}")
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
            print(f"区域坐标: ({x}, {y}) - ({x + w}, {y + h})")
            print(f"尺寸: {w}x{h}")

            # 终端预览
            print("\n=== 模板预览 ===")
            preview_image_inline(cropped)

            # 验证模板匹配
            print("\n=== 验证模板匹配 ===")
            if recognizer is None:
                from ..recognizer import Recognizer

                recognizer = Recognizer()

            # 重新加载模板（包含刚保存的）
            recognizer.reload_templates()

            # 获取置信度
            threshold = config.TEMPLATE_THRESHOLD
            confidence = recognizer.get_template_confidence(
                screenshot, template_rel_path
            )
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

        except ValueError:
            print("请输入有效的数字")
            continue
