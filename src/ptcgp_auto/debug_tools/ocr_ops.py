"""
OCR 调试操作
"""

from ptcgp_auto import config
from ptcgp_auto.debug_tools import context


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
        text = item["text"]
        box = item["box"]
        conf = item["confidence"]
        print(f'{i:2}. [{conf:.2f}] "{text}"')
        print(f"    位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
    print("-" * 60)

    try:
        import cv2
        import numpy as np

        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        for item in results:
            box = item["box"]
            cv2.rectangle(img_cv, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)

        debug_dir = context.get_debug_dir()
        filepath = debug_dir / "ocr_result.png"
        cv2.imwrite(str(filepath), img_cv)
        print(f"\n✓ 标注图片已保存: {filepath}")
    except Exception as exc:
        print(f"保存标注图片失败: {exc}")


def find_text(adb, recognizer):
    """查找特定文字"""
    text = input("\n请输入要查找的文字: ").strip()
    if not text:
        print("未输入文字")
        return

    print(f'\n>>> 查找文字: "{text}"...')
    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    box = recognizer.find_text(img, text)
    if box:
        print(f"✓ 找到! 位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
        print(f"  中心点: ({(box[0] + box[2]) // 2}, {(box[1] + box[3]) // 2})")
    else:
        print(f'✗ 未找到文字: "{text}"')


def find_text_patterns(adb, recognizer):
    """查找文本模式"""
    print("\n可用的模式键:")
    for key in config.TEXT_PATTERNS:
        patterns = config.TEXT_PATTERNS[key]
        print(f"  {key}: {patterns}")

    key = input("\n请输入模式键 (如 auto, series_a): ").strip()
    if not key:
        print("未输入")
        return

    if key not in config.TEXT_PATTERNS:
        print(f"✗ 未知的模式键: {key}")
        return

    print(f"\n>>> 查找模式: {key}...")
    print(f"    候选: {config.TEXT_PATTERNS[key]}")

    img = adb.screenshot()
    if not img:
        print("✗ 截图失败")
        return

    box = recognizer.find_text_variants(img, key)
    if box:
        print(f"✓ 找到! 位置: ({box[0]}, {box[1]}) - ({box[2]}, {box[3]})")
    else:
        print(f"✗ 未找到任何 {key} 模式")
