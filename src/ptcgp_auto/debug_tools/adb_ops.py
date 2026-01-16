"""
ADB 调试操作
"""

from pathlib import Path

from ptcgp_auto import config
from ptcgp_auto.debug_tools import context


def test_adb_connection():
    """测试 ADB 连接"""
    port = context.get_current_port() or config.ADB_PORT
    host = context.get_current_host() or config.ADB_HOST
    print("\n>>> 测试 ADB 连接...")
    adb = context.get_adb()
    if adb.connect():
        print("✓ ADB 连接成功!")
        return adb
    print("✗ ADB 连接失败，请检查:")
    print("  - BlueStacks Air 是否运行")
    print("  - ADB 是否开启")
    print(f"  - 端口是否正确 (当前: {host}:{port})")
    return None


def take_screenshot(adb):
    """截图并保存"""
    print("\n>>> 截图中...")
    img = adb.screenshot()
    if img:
        debug_dir = context.get_debug_dir()
        filepath = debug_dir / "screenshot.png"
        img.save(filepath)
        print(f"✓ 截图已保存: {filepath}")
        print(f"  尺寸: {img.size[0]} x {img.size[1]}")
        return img
    print("✗ 截图失败")
    return None


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

    debug_dir = context.get_debug_dir()
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

    cropped = img.crop((x1, y1, x2, y2))
    templates_dir = Path("templates")
    templates_dir.mkdir(exist_ok=True)

    filepath = templates_dir / f"{name}.png"
    cropped.save(filepath)
    print(f"✓ 模板已保存: {filepath}")
    print(f"  尺寸: {cropped.size[0]} x {cropped.size[1]}")
