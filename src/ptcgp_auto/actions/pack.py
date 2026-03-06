"""开包相关动作模块"""

import time
from typing import Dict, Optional

from ptcgp_auto import config
from ptcgp_auto.logger import get_logger

from .utils import find_text_by_variants

logger = get_logger(__name__)

# 长按时间（毫秒）
LONG_PRESS_DURATION = 2000
# 滑动时间（毫秒）
SWIPE_DURATION = 300
# 模板匹配缩放比例
SCALE_PACK_SERIES_SELECT = config.PACK_TEMPLATE_SCALES["pack_list"]
SCALE_PACK_LIST = config.PACK_TEMPLATE_SCALES["pack_select"]
SCALE_PACK_DETAIL = config.PACK_TEMPLATE_SCALES["pack_detail"]
# 最大尝试次数
MAX_SCROLL_ATTEMPTS = 10
MAX_SWITCH_ATTEMPTS = 10


def _screen_center():
    """获取屏幕中心坐标"""
    return config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2


def _swipe_pack_coords():
    """获取开包滑动坐标（从左 1/20 滑到右 19/20）"""
    w, h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
    return (w // 20, h // 2), (w * 19 // 20, h // 2)


def _swipe_card_coords():
    """获取卡牌上滑坐标（从屏幕 60% 高度滑到 20% 高度）"""
    w, h = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
    return (w // 2, int(h * 0.6)), (w // 2, int(h * 0.2))


class PackActions:
    """开包相关动作处理"""

    def __init__(self, adb, recognizer=None, state=None):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self.target_pack: Optional[Dict] = (
            None  # {"pack_code": "A1", "booster_name": "Charizard"}
        )
        self.series_switch_attempted = False

    def set_target_pack(self, pack_code: str, booster_name: str):
        """设置目标卡包"""
        self.target_pack = {"pack_code": pack_code, "booster_name": booster_name}
        self.series_switch_attempted = False
        logger.info(f"设置目标卡包: {pack_code}/{booster_name}")

    def _get_target_template_name(self) -> Optional[str]:
        """获取目标卡包的模板名称"""
        if not self.target_pack:
            return None
        return (
            f"packs/{self.target_pack['pack_code']}/{self.target_pack['booster_name']}"
        )

    def _get_target_series(self) -> Optional[str]:
        """根据 pack_code 获取目标系列（A/B）"""
        if not self.target_pack:
            return None
        pack_code = self.target_pack["pack_code"]
        # A1, A1a, A2, A2a -> A; B1, B1a -> B
        return pack_code[0].upper() if pack_code else None

    def _get_ocr_signature(self, ocr_results) -> str:
        """获取 OCR 结果的签名（用于检测内容变化）"""
        texts = sorted([item["text"] for item in ocr_results])
        return "|".join(texts)

    def click_pack_icon(self, screenshot, match_info: Dict):
        """点击开包图标进入开包流程"""
        if not self.recognizer:
            logger.error("  -> 未配置 recognizer")
            return

        pack_box = self.recognizer.find_template(
            screenshot, "icon_pack_open", threshold=0.7
        )
        if pack_box:
            logger.info("  -> 点击开包图标")
            self.adb.tap_center(pack_box)
        else:
            logger.warning("  -> 未找到开包图标")

    def select_pack_series(self, screenshot, match_info: Dict):
        """选择扩充包系列（pack_series_select 页面）

        使用模板匹配 + 上滑浏览找到目标扩充包
        """
        if not self.recognizer:
            logger.error("  -> 未配置 recognizer")
            return

        template_name = self._get_target_template_name()
        if not template_name:
            logger.warning("  -> 未设置目标卡包，点击屏幕中心")
            self.adb.tap(*_screen_center())
            return

        target_series = self._get_target_series()
        ocr_results = match_info.get("ocr_results", [])

        # 1. 确保在目标系列（A/B）
        if target_series and not self.series_switch_attempted:
            series_patterns = config.TEXT_PATTERNS.get("series", {})
            if target_series in series_patterns:
                patterns = series_patterns[target_series]
                for item in ocr_results:
                    for pattern in patterns:
                        if pattern in item["text"]:
                            logger.info(f"  -> 点击切换到 {target_series} 系列")
                            self.adb.tap_center(item["box"])
                            self.series_switch_attempted = True
                            return

        # 2. 用模板匹配查找目标扩充包
        box = self.recognizer.find_template_at_scale(
            screenshot, template_name, SCALE_PACK_SERIES_SELECT
        )
        if box:
            logger.info(f"  -> 找到目标扩充包，点击进入")
            self.adb.tap_center(box)
            return

        # 3. 上滑浏览列表
        last_signature = self._get_ocr_signature(ocr_results)
        for attempt in range(MAX_SCROLL_ATTEMPTS):
            logger.info(f"  -> 第 {attempt + 1} 次上滑查找扩充包")
            self.adb.swipe_up(ratio=0.21)
            time.sleep(1.2)

            screenshot = self.adb.screenshot()
            if not screenshot:
                continue

            # 检查模板匹配
            box = self.recognizer.find_template_at_scale(
                screenshot, template_name, SCALE_PACK_SERIES_SELECT
            )
            if box:
                logger.info(f"  -> 找到目标扩充包，点击进入")
                self.adb.tap_center(box)
                return

            # 检测是否到底（OCR 内容不变）
            ocr_results = self.recognizer.ocr_full_screen(screenshot)
            current_signature = self._get_ocr_signature(ocr_results)
            if current_signature == last_signature:
                logger.warning(f"  -> 滑动到底部，未找到目标扩充包")
                break
            last_signature = current_signature

        logger.warning(f"  -> 未找到目标扩充包: {template_name}")

    def select_pack(self, screenshot, match_info: Dict):
        """选择子包（pack_list 页面）

        使用模板匹配 + 点击右侧切换找到目标子包
        """
        if not self.recognizer:
            logger.error("  -> 未配置 recognizer")
            return

        template_name = self._get_target_template_name()
        if not template_name:
            logger.warning("  -> 未设置目标卡包，点击屏幕中心")
            self.adb.tap(*_screen_center())
            return

        # 1. 先检查当前是否是目标子包
        box = self.recognizer.find_template_at_scale(
            screenshot, template_name, SCALE_PACK_LIST
        )
        if box:
            logger.info("  -> 当前是目标子包，点击进入详情")
            self.adb.tap_center(box)
            return

        # 2. 记录初始签名，用于检测循环一圈
        ocr_results = match_info.get("ocr_results", [])
        first_signature = self._get_ocr_signature(ocr_results)

        # 3. 点击右侧切换子包
        for attempt in range(MAX_SWITCH_ATTEMPTS):
            logger.debug(f"  -> 第 {attempt + 1} 次切换子包")
            # 点击屏幕右侧区域切换
            tap_x = int(config.SCREEN_WIDTH * 0.75)
            tap_y = config.SCREEN_HEIGHT // 2
            self.adb.tap(tap_x, tap_y)
            time.sleep(1.0)

            screenshot = self.adb.screenshot()
            if not screenshot:
                continue

            # 检查模板匹配
            box = self.recognizer.find_template_at_scale(
                screenshot, template_name, SCALE_PACK_LIST
            )
            if box:
                logger.info("  -> 找到目标子包，点击进入详情")
                self.adb.tap_center(box)
                return

            # 检测是否循环一圈
            ocr_results = self.recognizer.ocr_full_screen(screenshot)
            current_signature = self._get_ocr_signature(ocr_results)
            if current_signature == first_signature:
                logger.warning(f"  -> 循环一圈，未找到目标子包")
                break

        logger.warning(f"  -> 未找到目标子包: {template_name}")

    def click_open_pack(self, screenshot, match_info: Dict):
        """点击开包按钮"""
        ocr_results = match_info.get("ocr_results", [])

        item = find_text_by_variants(ocr_results, "open_pack")
        if item:
            logger.info(f"  -> 点击 {item['text']}")
            self.adb.tap_center(item["box"])
            return

        paid_item = find_text_by_variants(ocr_results, "open_pack_1")
        if paid_item:
            logger.info("  -> 未检测到免费包，返回上一页")
            self.adb.back()
            return

        logger.warning("  -> 未找到开包按钮")

    def handle_hourglass_popup(self, screenshot, match_info: Dict):
        """处理沙漏弹窗（需要等待时间）"""
        ocr_results = match_info.get("ocr_results", [])

        template_box = None
        if self.recognizer:
            confidence = self.recognizer.get_template_confidence(
                screenshot, "btn_close"
            )
            logger.debug(
                f"  -> 关闭按钮模板置信度: {confidence:.2f} "
                f"(阈值={config.TEMPLATE_THRESHOLD})"
            )
            if confidence >= config.TEMPLATE_THRESHOLD:
                template_box = self.recognizer.find_template(
                    screenshot, "btn_close", threshold=config.TEMPLATE_THRESHOLD
                )

        if template_box:
            logger.info("  -> 没有免费包，点击关闭弹窗")
            self.adb.tap_center(template_box)
            return

        item = find_text_by_variants(ocr_results, "close_button")
        if item:
            logger.info("  -> 没有免费包，点击关闭弹窗")
            self.adb.tap_center(item["box"])
            return

        # 如果没找到关闭按钮，点击屏幕底部边缘关闭
        logger.info("  -> 点击屏幕底部关闭弹窗")
        self.adb.tap(config.SCREEN_WIDTH // 10, int(config.SCREEN_HEIGHT * 0.95))

    def swipe_open_pack(self, screenshot, match_info: Dict):
        """滑动开包"""
        logger.info("  -> 从左往右滑动开包")
        start, end = _swipe_pack_coords()
        self.adb.swipe(*start, *end, SWIPE_DURATION)

    def long_press_text(self, screenshot, match_info: Dict):
        """长按 OCR 文字位置"""
        ocr_results = match_info.get("ocr_results", [])
        item = find_text_by_variants(ocr_results, "long_press")
        if not item:
            logger.warning("  -> 未找到長按文字，跳过操作")
            return
        logger.info(f"  -> 长按文字位置: {item['text']}")
        self.adb.long_press_center(item["box"], LONG_PRESS_DURATION)

    def long_press_center(self, screenshot, match_info: Dict):
        """长按屏幕中心（跳过卡牌展示）"""
        logger.info("  -> 长按屏幕中心跳过卡牌展示")
        self.adb.long_press(*_screen_center(), LONG_PRESS_DURATION)

    def swipe_up_card(self, screenshot, match_info: Dict):
        """向上滑动卡牌登录到图鉴"""
        logger.info("  -> 向上滑动卡牌")
        start, end = _swipe_card_coords()
        self.adb.swipe(*start, *end, SWIPE_DURATION)
