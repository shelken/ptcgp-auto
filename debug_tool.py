"""
PTCGP 自动化脚本 - 交互式调试工具
"""

import sys
import os
from pathlib import Path

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent))

import config
from adb_controller import get_controller
from recognizer import get_recognizer


def print_menu():
    """打印菜单"""
    print("\n" + "=" * 50)
    print("PTCGP 调试工具")
    print("=" * 50)
    print("1. 测试 ADB 连接")
    print("2. 截图并保存")
    print("3. 截图 + OCR 识别（显示所有文字）")
    print("4. 测试查找特定文字")
    print("5. 测试多语言变体查找")
    print("6. 测试点击屏幕中央")
    print("7. 测试滑动")
    print("8. 裁剪模板图片（从截图中裁剪按钮）")
    print("9. 查看当前配置")
    print("0. 退出")
    print("-" * 50)


def test_adb_connection():
    """测试 ADB 连接"""
    print("\n>>> 测试 ADB 连接...")
    adb = get_controller()
    if adb.connect():
        print("✓ ADB 连接成功!")
        return adb
    else:
        print("✗ ADB 连接失败，请检查:")
        print(f"  - BlueStacks Air 是否运行")
        print(f"  - ADB 是否开启")
        print(f"  - 端口是否正确 (当前: {config.ADB_HOST}:{config.ADB_PORT})")
        return None


def take_screenshot(adb):
    """截图并保存"""
    print("\n>>> 截图中...")
    img = adb.screenshot()
    if img:
        # 保存到 debug_output 目录
        debug_dir = Path(config.DEBUG_DIR)
        debug_dir.mkdir(exist_ok=True)

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

        debug_dir = Path(config.DEBUG_DIR)
        debug_dir.mkdir(exist_ok=True)
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
    debug_dir = Path(config.DEBUG_DIR)
    debug_dir.mkdir(exist_ok=True)
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
    print("\n当前配置:")
    print("-" * 40)
    print(f"ADB 地址: {config.ADB_HOST}:{config.ADB_PORT}")
    print(f"屏幕尺寸: {config.SCREEN_WIDTH} x {config.SCREEN_HEIGHT}")
    print(f"OCR 语言: {config.OCR_LANGUAGES}")
    print(f"调试模式: {config.DEBUG}")
    print(f"等级列表: {config.BATTLE_LEVELS}")
    print("-" * 40)
    print("多语言变体:")
    for key, values in config.TEXT_VARIANTS.items():
        print(f"  {key}: {values}")


def main():
    """主函数"""
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
            show_config()

        else:
            print("无效选择，请重试")


if __name__ == "__main__":
    main()
