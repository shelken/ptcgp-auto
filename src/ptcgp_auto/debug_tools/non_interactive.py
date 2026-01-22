"""
非交互模式处理
"""

import os
from pathlib import Path

import cv2

from ptcgp_auto.debug_tools import context
from ptcgp_auto.recognizer import get_recognizer
from ptcgp_auto.recognizer_parts.template_matcher import _normalize_template_name
from ptcgp_auto import config


def _load_template_from_path(recognizer, template_path: str) -> str:
    """
    从绝对路径或 ~ 路径加载模板，返回模板名称

    Args:
        recognizer: 识别器实例
        template_path: 模板文件路径（支持绝对路径和 ~ 路径）

    Returns:
        模板名称（用于后续匹配）
    """
    # 展开 ~ 路径
    path = Path(os.path.expanduser(template_path))

    if not path.exists():
        print(f"ERROR: 模板文件不存在: {path}")
        return None

    if not path.suffix.lower() == ".png":
        print(f"WARNING: 模板文件不是 PNG 格式: {path}")

    # 使用文件名（不含扩展名）作为模板名
    template_name = path.stem

    # 加载模板图片
    img = cv2.imread(str(path))
    if img is None:
        print(f"ERROR: 无法读取模板文件: {path}")
        return None

    # 添加到识别器的模板字典中
    recognizer.templates[template_name] = img
    print(f"LOADED: {template_name} <- {path} ({img.shape[1]}x{img.shape[0]})")

    return template_name


def _is_path(template_name: str) -> bool:
    """判断模板名是否是路径"""
    return template_name.startswith("/") or template_name.startswith("~")


# 缩放扫描常量
MIN_TEMPLATE_SIZE = 16  # 缩放后模板最小边长（像素），避免过小导致误匹配
DEFAULT_MAX_SCALE = 3.0  # 默认最大缩放比例
DEFAULT_STEP = 0.02  # 默认步进


def _calc_valid_scale_range(
    template_shape, screen_shape, min_scale=0.1, max_scale=DEFAULT_MAX_SCALE
):
    """
    计算有效的缩放范围

    Args:
        template_shape: 模板形状 (height, width, ...)
        screen_shape: 截图形状 (height, width, ...)
        min_scale: 用户指定的最小缩放
        max_scale: 用户指定的最大缩放

    Returns:
        (min_valid_scale, max_valid_scale) 或 None（无有效范围）
    """
    orig_h, orig_w = template_shape[:2]
    screen_h, screen_w = screen_shape[:2]

    # 计算最小有效缩放比例（确保缩放后至少 MIN_TEMPLATE_SIZE 像素）
    min_valid_scale = max(
        min_scale,
        MIN_TEMPLATE_SIZE / orig_w,
        MIN_TEMPLATE_SIZE / orig_h,
    )
    # 向上取整到 0.02
    min_valid_scale = round(min_valid_scale + 0.01, 2)

    # 计算最大有效缩放比例（模板不能大于截图）
    max_valid_scale = min(max_scale, screen_w / orig_w, screen_h / orig_h)

    if min_valid_scale > max_valid_scale:
        return None

    return (min_valid_scale, max_valid_scale)


def _scan_best_scale(
    recognizer, img, template_name, min_scale=0.1, max_scale=DEFAULT_MAX_SCALE, step=DEFAULT_STEP
):
    """扫描所有缩放比例，返回最佳匹配的 (scale, confidence)"""
    best_scale = 1.0
    best_confidence = 0.0

    # 获取模板
    template_key = _normalize_template_name(template_name)
    template = recognizer.templates.get(template_key)
    if template is None:
        return best_scale, best_confidence

    orig_h, orig_w = template.shape[:2]

    # 获取截图尺寸
    screen = recognizer.pil_to_cv2(img)

    # 计算有效缩放范围
    scale_range = _calc_valid_scale_range(
        template.shape, screen.shape, min_scale, max_scale
    )
    if scale_range is None:
        print(f"WARNING: 模板尺寸 {orig_w}x{orig_h} 无有效缩放范围")
        return best_scale, best_confidence

    min_valid_scale, max_valid_scale = scale_range
    num_steps = int((max_valid_scale - min_valid_scale) / step) + 1
    print(
        f"  范围 {min_valid_scale:.2f}-{max_valid_scale:.2f} "
        f"(模板 {orig_w}x{orig_h}，步进 {step}，共 {num_steps} 步)"
    )

    # 生成缩放比例列表并逐一测试
    scale = min_valid_scale
    while scale <= max_valid_scale + 0.001:  # 浮点数精度处理
        current_scale = round(scale, 2)
        confidence = recognizer.get_template_confidence_at_scale(
            img, template_name, current_scale
        )
        if confidence > best_confidence:
            best_confidence = confidence
            best_scale = current_scale
        scale += step

    return best_scale, best_confidence


def _find_all_at_scale(recognizer, img, template_name, scale, threshold=None):
    """在指定缩放比例下查找所有匹配的模板"""
    import numpy as np

    threshold = threshold or config.TEMPLATE_THRESHOLD
    template_key = _normalize_template_name(template_name)
    template = recognizer.templates.get(template_key)
    if template is None:
        return []

    # 缩放模板
    if abs(scale - 1.0) > 0.01:
        new_w = int(template.shape[1] * scale)
        new_h = int(template.shape[0] * scale)
        if new_w < 1 or new_h < 1:
            return []
        template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA)

    screen = recognizer.pil_to_cv2(img)

    # 检查模板不能大于截图
    if template.shape[0] > screen.shape[0] or template.shape[1] > screen.shape[1]:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    h, w = template.shape[:2]
    boxes = []
    for pt in zip(*locations[::-1]):
        x1, y1 = pt
        x2, y2 = x1 + w, y1 + h
        boxes.append((x1, y1, x2, y2))

    # 使用 recognizer 的 NMS 方法去重
    boxes = recognizer._non_max_suppression(boxes)
    return boxes


def _cluster_boxes_by_proximity(boxes, gap_threshold, y_tolerance=None):
    """
    将匹配框按位置聚类成组（同一水平线上的相邻匹配）

    Args:
        boxes: 匹配框列表 [(x1, y1, x2, y2), ...]
        gap_threshold: 两个匹配框中心点之间的最大水平距离
        y_tolerance: Y 坐标容差（超过则视为不同行），默认为 gap_threshold

    Returns:
        groups: 分组列表，每组是一个匹配框列表
    """
    if not boxes:
        return []

    if y_tolerance is None:
        y_tolerance = gap_threshold

    # 按 Y 坐标分行，再按 X 坐标排序
    # 先按 Y 排序，将相近 Y 的分为一行
    sorted_by_y = sorted(boxes, key=lambda b: (b[1] + b[3]) / 2)

    rows = []
    current_row = [sorted_by_y[0]]

    for i in range(1, len(sorted_by_y)):
        prev_box = current_row[-1]
        curr_box = sorted_by_y[i]

        prev_cy = (prev_box[1] + prev_box[3]) / 2
        curr_cy = (curr_box[1] + curr_box[3]) / 2

        if abs(curr_cy - prev_cy) <= y_tolerance:
            current_row.append(curr_box)
        else:
            rows.append(current_row)
            current_row = [curr_box]

    rows.append(current_row)

    # 对每一行，按 X 坐标聚类
    groups = []
    for row in rows:
        sorted_by_x = sorted(row, key=lambda b: (b[0] + b[2]) / 2)

        current_group = [sorted_by_x[0]]
        for i in range(1, len(sorted_by_x)):
            prev_box = current_group[-1]
            curr_box = sorted_by_x[i]

            prev_cx = (prev_box[0] + prev_box[2]) / 2
            curr_cx = (curr_box[0] + curr_box[2]) / 2

            if curr_cx - prev_cx <= gap_threshold:
                current_group.append(curr_box)
            else:
                groups.append(current_group)
                current_group = [curr_box]

        groups.append(current_group)

    return groups


def _run_card_level(adb, args):
    """处理 --card-level 参数：检测卡片稀有度"""
    recognizer = get_recognizer()
    img = adb.screenshot()
    if not img:
        print("ERROR: 截图失败")
        return

    template_arg = args.card_level

    # 使用用户指定的阈值或默认值
    threshold = args.threshold if args.threshold is not None else config.TEMPLATE_THRESHOLD

    # 处理路径形式的模板
    if _is_path(template_arg):
        template_name = _load_template_from_path(recognizer, template_arg)
        if template_name is None:
            return
    else:
        template_name = template_arg

    # 确保模板已加载
    template_key = _normalize_template_name(template_name)
    if template_key not in recognizer.templates:
        recognizer._load_templates()
        if template_key not in recognizer.templates:
            print(f"ERROR: 模板不存在: {template_name}")
            return

    # 首先扫描最佳缩放比例
    if args.scale:
        best_scale = args.scale
        best_conf = recognizer.get_template_confidence_at_scale(
            img, template_name, best_scale
        )
    else:
        print("AUTO_SCALE: 扫描最佳缩放比例...")
        best_scale, best_conf = _scan_best_scale(recognizer, img, template_name)

    print(f"SCALE: {best_scale} confidence={best_conf:.4f} (threshold={threshold})")

    # 检查缩放后的模板尺寸
    template = recognizer.templates.get(template_key)
    scaled_w = int(template.shape[1] * best_scale)
    scaled_h = int(template.shape[0] * best_scale)
    print(f"TEMPLATE_SIZE: {template.shape[1]}x{template.shape[0]} -> {scaled_w}x{scaled_h}")

    if scaled_w < 10 or scaled_h < 10:
        print(f"WARNING: 缩放后模板过小 ({scaled_w}x{scaled_h})，可能产生大量误匹配")
        print("建议：从游戏画面重新截取更小的原始模板，或检查模板是否正确")

    if best_conf < threshold:
        print(f"✗ 置信度低于阈值 {threshold}，未找到匹配")
        return

    # 查找所有匹配
    all_boxes = _find_all_at_scale(recognizer, img, template_name, best_scale, threshold)
    print(f"MATCHES: {len(all_boxes)} 个匹配")

    if not all_boxes:
        return

    # 获取模板尺寸用于计算聚类阈值
    template_width = scaled_w
    template_height = scaled_h
    gap_threshold = template_width * args.gap
    y_tolerance = template_height * args.gap  # Y 方向使用相同的容差倍数

    print(f"CLUSTER: x_gap={gap_threshold:.1f}px, y_tolerance={y_tolerance:.1f}px")

    # 聚类（同时考虑 X 和 Y 坐标）
    groups = _cluster_boxes_by_proximity(all_boxes, gap_threshold, y_tolerance)

    print(f"\nGROUPS({len(groups)}):")
    for i, group in enumerate(groups, 1):
        # 计算组的边界
        min_x = min(b[0] for b in group)
        max_x = max(b[2] for b in group)
        min_y = min(b[1] for b in group)
        max_y = max(b[3] for b in group)
        cx = (min_x + max_x) // 2
        cy = (min_y + max_y) // 2

        print(
            f"  Group {i}: {len(group)} 个 @ ({min_x},{min_y})-({max_x},{max_y}) center=({cx},{cy})"
        )

    # 输出总结
    level_counts = {}
    for group in groups:
        count = len(group)
        level_counts[count] = level_counts.get(count, 0) + 1

    print(f"\nSUMMARY:")
    for count, num in sorted(level_counts.items(), reverse=True):
        print(f"  {count}× 模板: {num} 组")

    # 在截图上绘制匹配框并预览
    _preview_matches(img, all_boxes, groups)


def _preview_matches(img, all_boxes, groups):
    """在截图上绘制匹配框并在终端预览"""
    from PIL import ImageDraw
    from ptcgp_auto.debug_tools.terminal_preview import preview_image_inline

    # 复制图片以免修改原图
    preview_img = img.copy()
    draw = ImageDraw.Draw(preview_img)

    # 为每个组分配不同颜色
    colors = [
        (255, 0, 0),    # 红
        (0, 255, 0),    # 绿
        (0, 0, 255),    # 蓝
        (255, 255, 0),  # 黄
        (255, 0, 255),  # 紫
        (0, 255, 255),  # 青
        (255, 128, 0),  # 橙
        (128, 0, 255),  # 紫罗兰
    ]

    # 绘制每个匹配框
    for group_idx, group in enumerate(groups):
        color = colors[group_idx % len(colors)]
        for box in group:
            x1, y1, x2, y2 = box
            # 绘制矩形框（线宽 3）
            for offset in range(3):
                draw.rectangle(
                    [x1 - offset, y1 - offset, x2 + offset, y2 + offset],
                    outline=color
                )

    # 在终端预览
    print("\nPREVIEW:")
    preview_image_inline(preview_img)


def run_non_interactive(args):
    """非交互模式 - 直接执行并输出结果"""
    adb = context.get_adb()
    if not adb.connect():
        print("ERROR: ADB 连接失败")
        return

    recognizer = None

    if args.screenshot:
        img = adb.screenshot()
        if img:
            debug_dir = context.get_debug_dir()
            filepath = debug_dir / "screenshot.png"
            img.save(filepath)
            print(f"SCREENSHOT: {filepath}")
        else:
            print("ERROR: 截图失败")
        return

    if args.ocr:
        recognizer = get_recognizer()
        img = adb.screenshot()
        if not img:
            print("ERROR: 截图失败")
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
        return

    if args.template:
        recognizer = get_recognizer()
        img = adb.screenshot()
        if not img:
            print("ERROR: 截图失败")
            return

        ocr_results = recognizer.ocr_full_screen(img)
        ocr_items = []
        for item in ocr_results:
            text = item["text"]
            box = item["box"]
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            ocr_items.append(f'"{text}"@({cx},{cy})')
        print(f"OCR({len(ocr_results)}): {', '.join(ocr_items)}")

        # 处理路径形式的模板（支持绝对路径和 ~ 路径）
        template_name = args.template
        if _is_path(args.template):
            template_name = _load_template_from_path(recognizer, args.template)
            if template_name is None:
                return

        # 使用缩放参数
        if args.scale:
            box = recognizer.find_template_at_scale(img, template_name, args.scale)
            confidence = recognizer.get_template_confidence_at_scale(
                img, template_name, args.scale
            )
        else:
            box = recognizer.find_template(img, template_name)
            confidence = recognizer.get_template_confidence(img, template_name)

        template_key = _normalize_template_name(template_name)
        template = recognizer.templates.get(template_key)
        if template is not None:
            w, h = template.shape[1], template.shape[0]
            if args.scale:
                sw = int(w * args.scale)
                sh = int(h * args.scale)
                print(f"TEMPLATE_SCALE: {args.scale} {w}x{h} -> {sw}x{sh}")
            else:
                print(f"TEMPLATE_SCALE: 1.0 {w}x{h}")

        print(f"CONFIDENCE: {confidence:.4f} threshold={config.TEMPLATE_THRESHOLD}")

        if box:
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            scale_info = f" scale={args.scale}" if args.scale else ""
            print(
                f"TEMPLATE: {template_name}{scale_info} "
                f"@ ({box[0]},{box[1]})-({box[2]},{box[3]}) center=({cx},{cy})"
            )
        else:
            scale_info = f" scale={args.scale}" if args.scale else ""
            print(f"TEMPLATE: {template_name}{scale_info} NOT_FOUND")

            # 自动扫描最佳缩放比例（仅在未指定 --scale 时）
            if not args.scale:
                print()
                print("AUTO_SCALE: 扫描 0.1-10.0 (步进 0.1)...")
                best_scale, best_conf = _scan_best_scale(recognizer, img, template_name)
                print(f"BEST_SCALE: {best_scale} confidence={best_conf:.4f}")
                if best_conf >= config.TEMPLATE_THRESHOLD:
                    # 使用最佳缩放比例查找位置
                    best_box = recognizer.find_template_at_scale(
                        img, template_name, best_scale
                    )
                    if best_box:
                        cx = (best_box[0] + best_box[2]) // 2
                        cy = (best_box[1] + best_box[3]) // 2
                        print(
                            f"FOUND: @ ({best_box[0]},{best_box[1]})-({best_box[2]},{best_box[3]}) "
                            f"center=({cx},{cy})"
                        )

                    # 查找所有匹配
                    all_boxes = _find_all_at_scale(
                        recognizer, img, template_name, best_scale
                    )
                    if len(all_boxes) > 1:
                        print(f"ALL_MATCHES({len(all_boxes)}):")
                        for i, b in enumerate(all_boxes, 1):
                            cx = (b[0] + b[2]) // 2
                            cy = (b[1] + b[3]) // 2
                            print(f"  {i}. ({b[0]},{b[1]})-({b[2]},{b[3]}) center=({cx},{cy})")

                    print(
                        f"✓ 推荐使用: python debug_tool.py --template {template_name} --scale {best_scale}"
                    )
                else:
                    print(
                        f"✗ 最高置信度仍低于阈值 {config.TEMPLATE_THRESHOLD}，可能模板不匹配"
                    )
        return

    if args.all_templates:
        recognizer = get_recognizer()
        img = adb.screenshot()
        if not img:
            print("ERROR: 截图失败")
            return

        ocr_results = recognizer.ocr_full_screen(img)
        ocr_items = []
        for item in ocr_results:
            text = item["text"]
            box = item["box"]
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            ocr_items.append(f'"{text}"@({cx},{cy})')
        print(f"OCR({len(ocr_results)}): {', '.join(ocr_items)}")

        boxes = recognizer.find_all_templates(img, args.all_templates)
        if boxes:
            items = []
            for box in boxes:
                cx = (box[0] + box[2]) // 2
                cy = (box[1] + box[3]) // 2
                items.append(
                    f"({box[0]},{box[1]})-({box[2]},{box[3]}) center=({cx},{cy})"
                )
            print(f"TEMPLATES({len(boxes)}): {args.all_templates}")
            for i, item in enumerate(items, 1):
                print(f"  {i}. {item}")
        else:
            print(f"TEMPLATES: {args.all_templates} NOT_FOUND")
        return

    if args.card_level:
        _run_card_level(adb, args)
