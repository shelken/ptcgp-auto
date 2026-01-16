"""
非交互模式处理
"""

from ptcgp_auto.debug_tools import context
from ptcgp_auto.recognizer import get_recognizer


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

        box = recognizer.find_template(img, args.template)
        if box:
            cx = (box[0] + box[2]) // 2
            cy = (box[1] + box[3]) // 2
            print(
                f"TEMPLATE: {args.template} "
                f"@ ({box[0]},{box[1]})-({box[2]},{box[3]}) center=({cx},{cy})"
            )
        else:
            print(f"TEMPLATE: {args.template} NOT_FOUND")
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
