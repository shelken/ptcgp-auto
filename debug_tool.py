"""
PTCGP 自动化脚本 - 交互式调试工具
"""

import argparse
import sys
import os
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

import config
from adb_controller import AdbController
from recognizer import get_recognizer
from utils import get_data_dir


# 全局变量保存当前连接信息
_current_host = None
_current_port = None


def get_adb():
    """获取 ADB 控制器"""
    return AdbController(_current_host, _current_port)


def get_debug_dir():
    """获取当前连接的调试目录"""
    port = _current_port or config.ADB_PORT
    return get_data_dir(port)


def print_menu():
    """打印菜单"""
    port = _current_port or config.ADB_PORT
    host = _current_host or config.ADB_HOST
    print("\n" + "=" * 50)
    print(f"PTCGP 调试工具 [{host}:{port}]")
    print("=" * 50)
    print("1. 测试 ADB 连接")
    print("2. 截图并保存")
    print("3. 截图 + OCR 识别（显示所有文字）")
    print("4. 测试查找特定文字")
    print("5. 测试多语言变体查找")
    print("6. 测试点击屏幕中央")
    print("7. 测试滑动")
    print("8. 裁剪模板图片（手动输入坐标）")
    print("9. 自动检测 UI 组件（智能识别按钮）")
    print("10. 查看当前配置")
    print("0. 退出")
    print("-" * 50)


def test_adb_connection():
    """测试 ADB 连接"""
    port = _current_port or config.ADB_PORT
    host = _current_host or config.ADB_HOST
    print("\n>>> 测试 ADB 连接...")
    adb = get_adb()
    if adb.connect():
        print("✓ ADB 连接成功!")
        return adb
    else:
        print("✗ ADB 连接失败，请检查:")
        print(f"  - BlueStacks Air 是否运行")
        print(f"  - ADB 是否开启")
        print(f"  - 端口是否正确 (当前: {host}:{port})")
        return None


def take_screenshot(adb):
    """截图并保存"""
    print("\n>>> 截图中...")
    img = adb.screenshot()
    if img:
        # 保存到调试目录
        debug_dir = get_debug_dir()

        filepath = debug_dir / "screenshot.png"
        img.save(filepath)
        print(f"✓ 截图已保存: {filepath}")
        print(f"  尺寸: {img.size[0]} x {img.size[1]}")
        return img
    else:
        print("✗ 截图失败")
        return None


def ocr_screenshot(adb, recognizer):
    """OCR 识别截图中的所有文字"""
    print("\n>>> 截图并进行 OCR 识别...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    results = recognizer.ocr_full_screen(img)

    print(f"\n识别到 {len(results)} 个文本区域:")
    print("-" * 60)
    for i, item in enumerate(results, 1):
        text = item['text']
        box = item['box']
        conf = item['confidence']
        print(f"{i:2}. [{conf:.2f}] \"{text}\"")
        print(f"    位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
    print("-" * 60)

    # 保存带标注的截图
    try:
        import cv2
        import numpy as np

        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        for item in results:
            box = item['box']
            cv2.rectangle(img_cv, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)

        debug_dir = get_debug_dir()
        filepath = debug_dir / "ocr_result.png"
        cv2.imwrite(str(filepath), img_cv)
        print(f"\n✓ 标注图片已保存: {filepath}")
    except Exception as e:
        print(f"保存标注图片失败: {e}")


def find_text(adb, recognizer):
    """查找特定文字"""
    text = input("\n请输入要查找的文字: ").strip()
    if not text:
        print("未输入文字")
        return

    print(f"\n>>> 查找文字: \"{text}\"...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    box = recognizer.find_text(img, text)
    if box:
        print(f"✓ 找到! 位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
        print(f"  中心点: ({(box[0]+box[2])//2}, {(box[1]+box[3])//2})")
    else:
        print(f"✗ 未找到文字: \"{text}\"")


def find_text_variants(adb, recognizer):
    """查找多语言变体"""
    print("\n可用的变体键:")
    for key in config.TEXT_VARIANTS:
        variants = config.TEXT_VARIANTS[key]
        print(f"  {key}: {variants[:3]}...")

    key = input("\n请输入变体键 (如 continue, battle): ").strip()
    if not key:
        print("未输入")
        return

    if key not in config.TEXT_VARIANTS:
        print(f"✗ 未知的变体键: {key}")
        return

    print(f"\n>>> 查找变体: {key}...")
    print(f"    候选: {config.TEXT_VARIANTS[key]}")

    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    box = recognizer.find_text_variants(img, key)
    if box:
        print(f"✓ 找到! 位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
    else:
        print(f"✗ 未找到任何 {key} 变体")


def test_tap(adb):
    """测试点击"""
    print("\n>>> 点击屏幕中央...")
    x = config.SCREEN_WIDTH // 2
    y = config.SCREEN_HEIGHT // 2
    adb.tap(x, y)
    print(f"✓ 已点击 ({x}, {y})")


def test_swipe(adb):
    """测试滑动"""
    print("\n选择滑动方向:")
    print("1. 向上滑动")
    print("2. 向下滑动")
    choice = input("请选择: ").strip()

    if choice == "1":
        print(">>> 向上滑动...")
        adb.swipe_up()
        print("✓ 滑动完成")
    elif choice == "2":
        print(">>> 向下滑动...")
        adb.swipe_down()
        print("✓ 滑动完成")
    else:
        print("无效选择")


def crop_template(adb):
    """从截图中裁剪模板"""
    print("\n>>> 首先截图...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    # 保存原图
    debug_dir = get_debug_dir()
    screenshot_path = debug_dir / "for_crop.png"
    img.save(screenshot_path)
    print(f"截图已保存: {screenshot_path}")

    print("\n请用图片编辑器打开上面的截图，记下要裁剪区域的坐标")
    print("格式: x1,y1,x2,y2 (左上角和右下角)")

    coords = input("输入坐标 (如 100,200,300,400): ").strip()
    if not coords:
        print("未输入坐标")
        return

    try:
        x1, y1, x2, y2 = map(int, coords.split(","))
    except ValueError:
        print("坐标格式错误")
        return

    name = input("模板名称 (不含扩展名，如 btn_battle): ").strip()
    if not name:
        print("未输入名称")
        return

    # 裁剪并保存
    cropped = img.crop((x1, y1, x2, y2))
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    filepath = templates_dir / f"{name}.png"
    cropped.save(filepath)
    print(f"✓ 模板已保存: {filepath}")
    print(f"  尺寸: {cropped.size[0]} x {cropped.size[1]}")


def show_config():
    """显示当前配置"""
    port = _current_port or config.ADB_PORT
    host = _current_host or config.ADB_HOST
    print("\n当前配置:")
    print("-" * 40)
    print(f"ADB 地址: {host}:{port}")
    print(f"屏幕尺寸: {config.SCREEN_WIDTH} x {config.SCREEN_HEIGHT}")
    print(f"OCR 语言: {config.OCR_LANGUAGES}")
    print(f"调试模式: {config.DEBUG}")
    print(f"等级列表: {config.BATTLE_LEVELS}")
    print(f"数据目录: {get_debug_dir()}")
    print("-" * 40)
    print("多语言变体:")
    for key, values in config.TEXT_VARIANTS.items():
        print(f"  {key}: {values}")


def auto_detect_components(adb):
    """自动检测 UI 组件（按钮、图标等）"""
    import cv2
    import numpy as np

    print("\n>>> 截图并自动检测 UI 组件...")
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    # 保存原图
    debug_dir = get_debug_dir()

    # 转换为 OpenCV 格式
    img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)

    detected_regions = []

    # 方法1: 检测圆形（返回按钮等圆形图标）
    print("检测圆形组件...")
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=50,
        param1=100,
        param2=30,
        minRadius=20,
        maxRadius=80
    )

    if circles is not None:
        circles = np.uint16(np.around(circles))
        for i, (x, y, r) in enumerate(circles[0, :]):
            # 扩大一点边界以包含完整按钮
            padding = 5
            x1 = max(0, x - r - padding)
            y1 = max(0, y - r - padding)
            x2 = min(img.width, x + r + padding)
            y2 = min(img.height, y + r + padding)
            detected_regions.append({
                'type': 'circle',
                'box': (int(x1), int(y1), int(x2), int(y2)),
                'center': (int(x), int(y)),
                'radius': int(r)
            })

    # 方法2: 检测矩形按钮（边缘检测 + 轮廓）
    print("检测矩形组件...")
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)

    # 膨胀边缘使轮廓更完整
    kernel = np.ones((3, 3), np.uint8)
    edges = cv2.dilate(edges, kernel, iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        # 过滤太小或太大的区域
        if area < 1000 or area > 100000:
            continue

        x, y, w, h = cv2.boundingRect(contour)

        # 过滤长宽比不合理的区域（太细长的不是按钮）
        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < 0.3 or aspect_ratio > 5:
            continue

        # 检查是否与已有区域重叠
        is_duplicate = False
        for region in detected_regions:
            rx1, ry1, rx2, ry2 = region['box']
            # 计算重叠
            overlap_x = max(0, min(x + w, rx2) - max(x, rx1))
            overlap_y = max(0, min(y + h, ry2) - max(y, ry1))
            overlap_area = overlap_x * overlap_y
            if overlap_area > area * 0.5:
                is_duplicate = True
                break

        if not is_duplicate:
            detected_regions.append({
                'type': 'rect',
                'box': (x, y, x + w, y + h),
                'area': area
            })

    # 按 y 坐标排序，方便查看
    detected_regions.sort(key=lambda r: (r['box'][1], r['box'][0]))

    print(f"\n检测到 {len(detected_regions)} 个 UI 组件:")
    print("-" * 60)

    # 在图片上标注编号
    annotated = img_cv.copy()
    for i, region in enumerate(detected_regions):
        box = region['box']
        color = (0, 255, 0) if region['type'] == 'circle' else (255, 0, 0)
        cv2.rectangle(annotated, (box[0], box[1]), (box[2], box[3]), color, 2)

        # 添加编号标签
        label = f"{i + 1}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        thickness = 2

        # 计算标签位置
        (text_w, text_h), _ = cv2.getTextSize(label, font, font_scale, thickness)
        label_x = box[0]
        label_y = box[1] - 5 if box[1] > 25 else box[3] + text_h + 5

        # 绘制背景
        cv2.rectangle(annotated, (label_x, label_y - text_h - 2),
                      (label_x + text_w + 4, label_y + 2), (0, 0, 0), -1)
        cv2.putText(annotated, label, (label_x + 2, label_y),
                    font, font_scale, (255, 255, 255), thickness)

        # 打印信息
        type_str = "⭕" if region['type'] == 'circle' else "▢"
        w = box[2] - box[0]
        h = box[3] - box[1]
        print(f"{i + 1:2}. {type_str} 位置: ({box[0]}, {box[1]}) 尺寸: {w}x{h}")

    print("-" * 60)

    # 保存标注后的图片
    preview_path = debug_dir / "detected_components.png"
    cv2.imwrite(str(preview_path), annotated)
    print(f"\n✓ 标注图片已保存: {preview_path}")
    print("请打开该图片查看检测到的组件编号")

    if not detected_regions:
        print("未检测到任何组件")
        return

    # 让用户选择要保存的组件
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
        box = region['box']

        name = input("模板名称 (不含扩展名，如 btn_back): ").strip()
        if not name:
            print("未输入名称，跳过")
            continue

        # 裁剪并保存
        cropped = img.crop(box)
        templates_dir = Path("templates")
        templates_dir.mkdir(exist_ok=True)

        filepath = templates_dir / f"{name}.png"
        cropped.save(filepath)
        print(f"✓ 模板已保存: {filepath}")
        print(f"  尺寸: {cropped.size[0]} x {cropped.size[1]}")


def main():
    """主函数"""
    global _current_host, _current_port

    parser = argparse.ArgumentParser(description='PTCGP 调试工具')
    parser.add_argument(
        '-a', '--address',
        type=str,
        default=None,
        help='ADB 连接地址，格式: host:port 或 port (默认: 127.0.0.1:5555)'
    )
    args = parser.parse_args()

    # 解析地址
    if args.address:
        if ':' in args.address:
            parts = args.address.split(':')
            _current_host = parts[0]
            _current_port = int(parts[1])
        else:
            _current_port = int(args.address)

    adb = None
    recognizer = None

    while True:
        print_menu()
        choice = input("请选择操作: ").strip()

        if choice == "0":
            print("\n再见!")
            break

        elif choice == "1":
            adb = test_adb_connection()

        elif choice == "2":
            if not adb:
                adb = test_adb_connection()
            if adb:
                take_screenshot(adb)

        elif choice == "3":
            if not adb:
                adb = test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                ocr_screenshot(adb, recognizer)

        elif choice == "4":
            if not adb:
                adb = test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                find_text(adb, recognizer)

        elif choice == "5":
            if not adb:
                adb = test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                find_text_variants(adb, recognizer)

        elif choice == "6":
            if not adb:
                adb = test_adb_connection()
            if adb:
                test_tap(adb)

        elif choice == "7":
            if not adb:
                adb = test_adb_connection()
            if adb:
                test_swipe(adb)

        elif choice == "8":
            if not adb:
                adb = test_adb_connection()
            if adb:
                crop_template(adb)

        elif choice == "9":
            if not adb:
                adb = test_adb_connection()
            if adb:
                auto_detect_components(adb)

        elif choice == "10":
            show_config()

        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()
