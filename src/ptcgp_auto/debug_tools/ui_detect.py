"""
UI 组件自动检测
"""

from pathlib import Path

from ptcgp_auto.debug_tools import context


def auto_detect_components(adb):
    """自动检测 UI 组件（按钮、图标等）"""
    import cv2
    import numpy as np

    print("\n>>> 截图并自动检测 UI 组件...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    debug_dir = context.get_debug_dir()

    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    detected_regions = []

    print("检测圆形组件...")
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=50,
        param1=100,
        param2=30,
        minRadius=20,
        maxRadius=80,
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for x, y, r in circles[0, :]:
            padding = 5
            x1 = max(0, x - r - padding)
            y1 = max(0, y - r - padding)
            x2 = min(img.width, x + r + padding)
            y2 = min(img.height, y + r + padding)
            detected_regions.append(
                {
                    "type": "circle",
                    "box": (int(x1), int(y1), int(x2), int(y2)),
                    "center": (int(x), int(y)),
                    "radius": int(r),
                }
            )

    print("检测矩形组件...")
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area < 1000 or area > 100000:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < 0.3 or aspect_ratio > 5:
            continue

        is_duplicate = False
        for region in detected_regions:
            rx1, ry1, rx2, ry2 = region["box"]
            overlap_x = max(0, min(x + w, rx2) - max(x, rx1))
            overlap_y = max(0, min(y + h, ry2) - max(y, ry1))
            overlap_area = overlap_x * overlap_y
            if overlap_area > area * 0.5:
                is_duplicate = True
                break

        if not is_duplicate:
            detected_regions.append(
                {"type": "rect", "box": (x, y, x + w, y + h), "area": area}
            )

    detected_regions.sort(key=lambda r: (r["box"][1], r["box"][0]))

    print(f"\n检测到 {len(detected_regions)} 个 UI 组件:")
    print("-" * 60)

    annotated = img_cv.copy()
    for i, region in enumerate(detected_regions):
        box = region["box"]
        color = (0, 255, 0) if region["type"] == "circle" else (255, 0, 0)
        cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color, 2)

        label = f"{i + 1}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2

        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        label_x = box[0]
        label_y = box[1] - 5 if box[1] > 25 else box[3] + text_h + 5

        cv2.rectangle(
            annotated,
            (label_x, label_y - text_h - 2),
            (label_x + text_w + 4, label_y + 2),
            (0, 0, 0),
            -1,
        )
        cv2.putText(
            annotated,
            label,
            (label_x + 2, label_y),
            font,
            font_scale,
            (255, 255, 255),
            thickness,
        )

        type_str = "⭕" if region["type"] == "circle" else "▢"
        width = box[2] - box[0]
        height = box[3] - box[1]
        print(
            f"{i + 1:2}. {type_str} 位置: ({box[0]}, {box[1]}) 尺寸: {width}x{height}"
        )

    print("-" * 60)

    preview_path = debug_dir / "detected_components.png"
    cv2.imwrite(str(preview_path), annotated)
    print(f"\n✓ 标注图片已保存: {preview_path}")
    print("请打开该图片查看检测到的组件编号")

    if not detected_regions:
        print("未检测到任何组件")
        return

    while True:
        choice = input("\n输入编号保存为模板 (或直接回车退出): ").strip()
        if not choice:
            break

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(detected_regions):
                print(f"无效编号，请输入 1-{len(detected_regions)}")
                continue
        except ValueError:
            print("请输入数字编号")
            continue

        region = detected_regions[idx]
        box = region["box"]

        name = input("模板名称 (不含扩展名，如 btn_back): ").strip()
        if not name:
            print("未输入名称，跳过")
            continue

        cropped = img.crop(box)
        templates_dir = Path("templates")
        templates_dir.mkdir(exist_ok=True)

        filepath = templates_dir / f"{name}.png"
        cropped.save(filepath)
        print(f"✓ 模板已保存: {filepath}")
        print(f"  尺寸: {cropped.size[0]} x {cropped.size[1]}")
