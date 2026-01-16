"""
颜色取样与状态检测
"""

from ptcgp_auto import config
from ptcgp_auto.debug_tools import context
from ptcgp_auto.recognizer import COLORS, COLOR_STATES


def color_picker(adb, recognizer):
    """颜色取样器 - 通过 OCR 定位元素并分析周围颜色"""
    import cv2
    import numpy as np

    print("\n>>> 颜色取样器...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    ocr_results = recognizer.ocr_full_screen(img)
    if not ocr_results:
        print("✗ 未识别到任何文字")
        return

    print(f"\n识别到 {len(ocr_results)} 个文本区域:")
    print("-" * 50)
    for i, item in enumerate(ocr_results, 1):
        text = item["text"]
        box = item["box"]
        print(f'{i:2}. "{text}" @ ({box[0]},{box[1]})-({box[2]},{box[3]})')
    print("-" * 50)

    choice = input("\n选择文字编号作为锚点: ").strip()
    if not choice:
        print("未选择")
        return

    try:
        idx = int(choice) - 1
        if idx < 0 or idx >= len(ocr_results):
            print("无效编号")
            return
    except ValueError:
        print("请输入数字")
        return

    anchor = ocr_results[idx]
    anchor_box = anchor["box"]
    print(
        f'\n锚点: "{anchor["text"]}" @ '
        f"({anchor_box[0]},{anchor_box[1]})-({anchor_box[2]},{anchor_box[3]})"
    )

    print("\n分析哪个方向的颜色?")
    print("1. 左边")
    print("2. 右边")
    print("3. 上边")
    print("4. 下边")

    direction = input("选择方向 (默认1): ").strip() or "1"
    direction_map = {"1": "left", "2": "right", "3": "above", "4": "below"}
    position = direction_map.get(direction, "left")

    ax1, ay1, ax2, ay2 = anchor_box
    anchor_cy = (ay1 + ay2) // 2
    anchor_cx = (ax1 + ax2) // 2

    region_w = int(config.SCREEN_WIDTH * 0.05)
    region_h = int(config.SCREEN_HEIGHT * 0.03)
    offset = int(config.SCREEN_WIDTH * 0.01)

    if position == "left":
        x2 = ax1 - offset
        x1 = x2 - region_w
        y1 = anchor_cy - region_h // 2
        y2 = anchor_cy + region_h // 2
    elif position == "right":
        x1 = ax2 + offset
        x2 = x1 + region_w
        y1 = anchor_cy - region_h // 2
        y2 = anchor_cy + region_h // 2
    elif position == "above":
        y2 = ay1 - offset
        y1 = y2 - region_h
        x1 = anchor_cx - region_w // 2
        x2 = anchor_cx + region_w // 2
    else:
        y1 = ay2 + offset
        y2 = y1 + region_h
        x1 = anchor_cx - region_w // 2
        x2 = anchor_cx + region_w // 2

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    height, width = img_cv.shape[:2]

    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)

    if x2 <= x1 or y2 <= y1:
        print("无效区域")
        return

    roi = img_cv[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

    h_mean = int(np.mean(hsv[:, :, 0]))
    s_mean = int(np.mean(hsv[:, :, 1]))
    v_mean = int(np.mean(hsv[:, :, 2]))

    h_min, h_max = int(np.min(hsv[:, :, 0])), int(np.max(hsv[:, :, 0]))
    s_min, s_max = int(np.min(hsv[:, :, 1])), int(np.max(hsv[:, :, 1]))
    v_min, v_max = int(np.min(hsv[:, :, 2])), int(np.max(hsv[:, :, 2]))

    print(f"\n分析区域: ({x1},{y1})-({x2},{y2})")
    print("-" * 40)
    print(f"平均值: H={h_mean}, S={s_mean}, V={v_mean}")
    print(f"H 范围: {h_min} - {h_max}")
    print(f"S 范围: {s_min} - {s_max}")
    print(f"V 范围: {v_min} - {v_max}")

    color_name = "未知"
    if s_mean < 30:
        color_name = "灰色/白色"
    elif h_mean < 10 or h_mean > 160:
        color_name = "红色"
    elif 10 <= h_mean < 25:
        color_name = "橙色"
    elif 25 <= h_mean < 35:
        color_name = "黄色"
    elif 35 <= h_mean < 85:
        color_name = "绿色"
    elif 85 <= h_mean < 100:
        color_name = "青色"
    elif 100 <= h_mean < 130:
        color_name = "蓝色"
    elif 130 <= h_mean < 160:
        color_name = "紫色"

    print(f"判断颜色: {color_name}")

    print("\n预定义颜色占比:")
    for name, color_range in COLORS.items():
        lower = np.array(color_range["lower"])
        upper = np.array(color_range["upper"])
        mask = cv2.inRange(hsv, lower, upper)
        ratio = np.count_nonzero(mask) / mask.size
        if ratio > 0.01:
            print(f"  {name}: {ratio:.1%}")

    offset_ratio = offset / config.SCREEN_WIDTH
    width_ratio = region_w / config.SCREEN_WIDTH
    height_ratio = region_h / config.SCREEN_HEIGHT

    print("\n建议的 COLOR_STATES 配置:")
    print(f'''
    "your_state_name": {{
        "locator": {{
            "type": "text_pattern",
            "key": "your_pattern_key",  # 需要在 TEXT_PATTERNS 中定义
        }},
        "color_region": {{
            "position": "{position}",
            "offset": {offset_ratio:.3f},
            "width": {width_ratio:.3f},
            "height": {height_ratio:.3f},
        }},
        "color": "{color_name.split("/")[0].lower() if "/" not in color_name else "gray"}",
        "threshold": 0.1,
    }},
''')

    debug_dir = context.get_debug_dir()
    annotated = img_cv.copy()
    cv2.rectangle(annotated, (ax1, ay1), (ax2, ay2), (255, 0, 0), 2)
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
    annotated_path = debug_dir / "color_sample.png"
    cv2.imwrite(str(annotated_path), annotated)
    print(f"✓ 标注图片已保存: {annotated_path}")
    print("  蓝框 = 锚点文字, 绿框 = 颜色分析区域")


def test_color_state(adb, recognizer):
    """测试颜色状态检测"""
    import cv2
    import numpy as np

    print("\n>>> 测试颜色状态检测...")

    if not COLOR_STATES:
        print("没有配置任何颜色状态")
        return

    print("\n可用的状态配置:")
    state_names = list(COLOR_STATES.keys())
    for i, name in enumerate(state_names, 1):
        state = COLOR_STATES[name]
        print(
            f"  {i}. {name} (定位: {state['locator']['key']}, 颜色: {state['color']})"
        )

    choice = input("\n选择状态编号 (或直接回车测试全部): ").strip()

    if choice:
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(state_names):
                print("无效编号")
                return
            test_states = [state_names[idx]]
        except ValueError:
            print("请输入数字")
            return
    else:
        test_states = state_names

    print("\n>>> 截图...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    debug_dir = context.get_debug_dir()
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    for state_name in test_states:
        print(f"\n--- 测试 {state_name} ---")
        state_config = COLOR_STATES[state_name]
        locator = state_config["locator"]

        anchor_box = None
        if locator["type"] == "text_pattern":
            anchor_box = recognizer.find_text_variants(img, locator["key"])
            if anchor_box:
                print(
                    f"定位文字 '{locator['key']}': "
                    f"({anchor_box[0]},{anchor_box[1]})-({anchor_box[2]},{anchor_box[3]})"
                )
            else:
                print(f"✗ 无法定位文字 '{locator['key']}'")
                continue
        elif locator["type"] == "template":
            anchor_box = recognizer.find_template(img, locator["key"])
            if anchor_box:
                print(
                    f"定位模板 '{locator['key']}': "
                    f"({anchor_box[0]},{anchor_box[1]})-({anchor_box[2]},{anchor_box[3]})"
                )
            else:
                print(f"✗ 无法定位模板 '{locator['key']}'")
                continue

        color_region = recognizer._calculate_color_region(
            anchor_box, state_config["color_region"]
        )
        print(
            "颜色检测区域: "
            f"({color_region[0]},{color_region[1]})-({color_region[2]},{color_region[3]})"
        )

        color_name = state_config["color"]
        color_config = COLORS[color_name]
        ratio = recognizer.get_color_ratio(
            img, color_region, color_config["lower"], color_config["upper"]
        )
        threshold = state_config["threshold"]

        result = ratio >= threshold
        status = "开启 ✓" if result else "关闭 ✗"
        print(f"{color_name}占比: {ratio:.1%} (阈值: {threshold:.1%})")
        print(f"判定结果: {status}")

        ax1, ay1, ax2, ay2 = anchor_box
        cv2.rectangle(img_cv, (ax1, ay1), (ax2, ay2), (255, 0, 0), 2)
        rx1, ry1, rx2, ry2 = color_region
        color_box = (0, 255, 0) if result else (0, 0, 255)
        cv2.rectangle(img_cv, (rx1, ry1), (rx2, ry2), color_box, 2)

    annotated_path = debug_dir / "color_state_test.png"
    cv2.imwrite(str(annotated_path), img_cv)
    print(f"\n✓ 标注图片已保存: {annotated_path}")
    print("  蓝框 = 定位锚点, 绿框 = 开启, 红框 = 关闭")
