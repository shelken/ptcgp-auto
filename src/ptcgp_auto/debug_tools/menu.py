"""
调试菜单与配置展示
"""

from ptcgp_auto import config
from ptcgp_auto.debug_tools import context


def print_menu():
    """打印菜单"""
    port = context.get_current_port() or config.ADB_PORT
    host = context.get_current_host() or config.ADB_HOST
    print("\n" + "=" * 50)
    print(f"PTCGP 调试工具 [{host}:{port}]")
    print("=" * 50)
    print("1. 测试 ADB 连接")
    print("2. 截图并保存")
    print("3. 截图 + OCR 识别（显示所有文字）")
    print("4. 测试查找特定文字")
    print("5. 测试文本模式查找")
    print("6. 测试点击屏幕中央")
    print("7. 测试滑动")
    print("8. 裁剪模板图片（手动输入坐标）")
    print("9. 自动检测 UI 组件（智能识别按钮）")
    print("10. 查看当前配置")
    print("11. 颜色取样器（获取 HSV 值）")
    print("12. 测试颜色状态检测")
    print("0. 退出")
    print("-" * 50)


def show_config():
    """显示当前配置"""
    port = context.get_current_port() or config.ADB_PORT
    host = context.get_current_host() or config.ADB_HOST
    print("\n当前配置:")
    print("-" * 40)
    print(f"ADB 地址: {host}:{port}")
    print(f"屏幕尺寸: {config.SCREEN_WIDTH} x {config.SCREEN_HEIGHT}")
    print(f"OCR 语言: {config.OCR_LANGUAGES}")
    print(f"调试模式: {config.DEBUG}")
    print(f"等级列表: {config.BATTLE_LEVELS}")
    print(f"数据目录: {context.get_debug_dir()}")
    print("-" * 40)
    print("文本模式:")
    for key, values in config.TEXT_PATTERNS.items():
        print(f"  {key}: {values}")
