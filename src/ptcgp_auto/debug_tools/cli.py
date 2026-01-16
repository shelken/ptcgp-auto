"""
交互式 CLI 主循环
"""

from ptcgp_auto.debug_tools import adb_ops
from ptcgp_auto.debug_tools import color_ops
from ptcgp_auto.debug_tools import context
from ptcgp_auto.debug_tools import menu
from ptcgp_auto.debug_tools import ocr_ops
from ptcgp_auto.debug_tools import ui_detect
from ptcgp_auto.recognizer import get_recognizer


def run_cli():
    """启动交互式 CLI"""
    adb = None
    recognizer = None

    while True:
        menu.print_menu()
        choice = input("请选择操作: ").strip()

        if choice == "0":
            print("\n再见!")
            break

        if choice == "1":
            adb = adb_ops.test_adb_connection()
            continue

        if choice == "2":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if adb:
                adb_ops.take_screenshot(adb)
            continue

        if choice == "3":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                ocr_ops.ocr_screenshot(adb, recognizer)
            continue

        if choice == "4":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                ocr_ops.find_text(adb, recognizer)
            continue

        if choice == "5":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                ocr_ops.find_text_patterns(adb, recognizer)
            continue

        if choice == "6":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if adb:
                adb_ops.test_tap(adb)
            continue

        if choice == "7":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if adb:
                adb_ops.test_swipe(adb)
            continue

        if choice == "8":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if adb:
                adb_ops.crop_template(adb)
            continue

        if choice == "9":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if adb:
                ui_detect.auto_detect_components(adb)
            continue

        if choice == "10":
            menu.show_config()
            continue

        if choice == "11":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                color_ops.color_picker(adb, recognizer)
            continue

        if choice == "12":
            if not adb:
                adb = adb_ops.test_adb_connection()
            if not recognizer:
                recognizer = get_recognizer()
            if adb:
                color_ops.test_color_state(adb, recognizer)
            continue

        print("无效选择，请重试")
