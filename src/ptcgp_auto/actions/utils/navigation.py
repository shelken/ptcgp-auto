"""导航辅助工具"""

from typing import List, Dict

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

logger = get_logger(__name__)


def go_back(adb, recognizer, screenshot):
    """返回上一页

    优先使用返回按钮模板，否则使用系统返回键
    """
    if screenshot:
        back_btn = recognizer.find_template(screenshot, "btn_back", threshold=0.6)
        if back_btn:
            adb.tap_center(back_btn)
            return
    adb.back()


def close_popup(adb, recognizer, screenshot, ocr_results: List[Dict]):
    """关闭弹窗

    优先查找 X 按钮，否则使用返回键
    """
    # 尝试 OCR 查找 X 按钮
    for item in ocr_results:
        text = item["text"].strip()
        if text in ["×", "X", "x", "✕"]:
            adb.tap_center(item["box"])
            return

    # 尝试模板匹配
    close_btn = recognizer.find_template(screenshot, "btn_close", threshold=0.6)
    if close_btn:
        adb.tap_center(close_btn)
        return

    # 使用返回键
    go_back(adb, recognizer, screenshot)


def detect_and_close_popup(adb, ocr_results: List[Dict]) -> bool:
    """检测并关闭遮挡弹窗（OK/确认/取消按钮），返回是否处理了弹窗

    注意：此函数用于滚动循环中检测遮挡内容的弹窗。
    与 close_popup 不同，close_popup 用于关闭 X 按钮类型的弹窗。
    """
    for item in ocr_results:
        text = item["text"].strip()
        if text in config.POPUP_BUTTONS:
            logger.info(f"  -> 检测到弹窗按钮 '{text}'，点击关闭")
            adb.tap_center(item["box"])
            return True
    return False
