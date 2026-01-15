"""
识别器 - OCR + 模板匹配 (使用 Apple Vision Framework)
"""

from pathlib import Path
from typing import Optional, Tuple, List, Dict
import re

import cv2
import numpy as np
from PIL import Image

import config
from logger import get_logger

logger = get_logger(__name__)


# 预定义颜色范围 (HSV)
# OpenCV 中 H: 0-179, S: 0-255, V: 0-255
COLORS = {
    "green": {"lower": (35, 80, 80), "upper": (100, 255, 255)},  # 扩展到青绿色
    "gray": {"lower": (0, 0, 60), "upper": (180, 30, 200)},
    "red": {"lower": (0, 80, 80), "upper": (10, 255, 255)},  # 红色有两段
    "red2": {"lower": (160, 80, 80), "upper": (179, 255, 255)},
    "blue": {"lower": (100, 80, 80), "upper": (130, 255, 255)},
    "yellow": {"lower": (20, 80, 80), "upper": (35, 255, 255)},
}

# 颜色状态检测配置
# 用于检测 UI 元素的开关/选中状态
COLOR_STATES = {
    "auto_battle": {
        "locator": {
            "type": "text_pattern",   # text_pattern 或 template
            "key": "auto",            # TEXT_PATTERNS 的 key
        },
        "color_region": {
            "position": "left",       # left / right / above / below
            "offset": 0.01,          # 相对于屏幕宽度/高度的比例
            "width": 0.05,            # 区域宽度（屏幕宽度比例）
            "height": 0.03,           # 区域高度（屏幕高度比例）
        },
        "color": "green",             # COLORS 中的预定义颜色名
        "threshold": 0.04,            # 颜色占比阈值（4.6% > 4%）
    },
}


def perform_ocr(image: Image.Image) -> List[Dict]:
    """使用 Apple Vision Framework 进行 OCR

    Args:
        image: PIL Image 对象

    Returns:
        识别结果列表，每项包含 text, box, confidence
    """
    import Vision
    import Quartz
    from Foundation import NSData
    import objc

    # 获取图像尺寸（在 autorelease_pool 外获取，避免 image 对象问题）
    width = image.width
    height = image.height

    # 将 PIL Image 转换为 PNG bytes（在 pool 外完成）
    import io
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    png_data = buffer.getvalue()
    buffer.close()

    results = []

    # 使用 autorelease_pool 确保 Objective-C 对象被正确释放
    # 这是修复内存泄漏的关键
    with objc.autorelease_pool():
        # 创建 NSData 和 CGImage
        ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))
        image_source = Quartz.CGImageSourceCreateWithData(ns_data, None)
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

        if cg_image is None:
            logger.error("无法创建 CGImage")
            return []

        # 创建 OCR 请求
        request = Vision.VNRecognizeTextRequest.alloc().init()

        # 设置识别级别
        if config.OCR_RECOGNITION_LEVEL == "fast":
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelFast)
        else:
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)

        # 设置识别语言
        request.setRecognitionLanguages_(config.OCR_LANGUAGES)

        # 自动检测语言
        request.setAutomaticallyDetectsLanguage_(True)

        # 创建请求处理器
        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_image, None
        )

        # 执行请求
        success = handler.performRequests_error_([request], None)

        if not success:
            logger.error("OCR 请求执行失败")
            return []

        # 解析结果（在 pool 内提取为 Python 原生类型）
        observations = request.results()

        if observations:
            for observation in observations:
                # 获取最佳候选文本
                top_candidate = observation.topCandidates_(1)
                if top_candidate and len(top_candidate) > 0:
                    # 转换为 Python 字符串，避免持有 ObjC 对象引用
                    text = str(top_candidate[0].string())
                    confidence = float(top_candidate[0].confidence())

                    # 获取边界框（Vision 使用归一化坐标，原点在左下角）
                    bounding_box = observation.boundingBox()
                    x = bounding_box.origin.x
                    y = bounding_box.origin.y
                    w = bounding_box.size.width
                    h = bounding_box.size.height

                    # 转换为像素坐标（原点在左上角）
                    x1 = int(x * width)
                    y1 = int((1 - y - h) * height)  # 翻转 Y 轴
                    x2 = int((x + w) * width)
                    y2 = int((1 - y) * height)

                    results.append({
                        'text': text,
                        'box': (x1, y1, x2, y2),
                        'confidence': confidence
                    })

    # autorelease_pool 退出时，所有 ObjC 对象会被释放
    return results


class Recognizer:
    """界面识别器"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, np.ndarray] = {}
        # 初始化时不加载模板，等待分辨率确定后调用 reload_templates()
        logger.info("使用 Apple Vision Framework 进行 OCR（原生 Apple Silicon 加速）")

    def reload_templates(self):
        """重新加载模板（根据当前分辨率缩放）"""
        self.templates.clear()
        self._load_templates()

    def _load_templates(self):
        """加载所有模板图片，并根据当前分辨率缩放"""
        if not self.templates_dir.exists():
            logger.warning(f"模板目录不存在: {self.templates_dir}")
            return

        # 计算缩放比例（当前分辨率 / 模板基准分辨率）
        scale = config.SCREEN_WIDTH / config.TEMPLATE_BASE_WIDTH
        if abs(scale - 1.0) > 0.01:
            logger.info(f"模板缩放比例: {scale:.2f} ({config.SCREEN_WIDTH}/{config.TEMPLATE_BASE_WIDTH})")

        for file in self.templates_dir.glob("*.png"):
            name = file.stem
            img = cv2.imread(str(file))
            if img is not None:
                # 如果分辨率不同，缩放模板
                if abs(scale - 1.0) > 0.01:
                    new_w = int(img.shape[1] * scale)
                    new_h = int(img.shape[0] * scale)
                    img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                self.templates[name] = img
                logger.info(f"已加载模板: {name}")

    def pil_to_cv2(self, pil_image: Image.Image) -> np.ndarray:
        """PIL Image 转 OpenCV 格式"""
        return cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)

    def find_template(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: float = None
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找模板

        Args:
            screenshot: PIL 截图
            template_name: 模板名称（不含扩展名）
            threshold: 匹配阈值，默认使用配置值

        Returns:
            匹配到的区域 (x1, y1, x2, y2)，未找到返回 None
        """
        # 延迟加载：首次使用时加载模板
        if not self.templates:
            self._load_templates()

        if template_name not in self.templates:
            logger.debug(f"模板不存在: {template_name}")
            return None

        threshold = threshold or config.TEMPLATE_THRESHOLD
        template = self.templates[template_name]
        screen = self.pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

        if max_val >= threshold:
            h, w = template.shape[:2]
            x1, y1 = max_loc
            x2, y2 = x1 + w, y1 + h

            logger.debug(f"[模板] 找到 {template_name}: ({x1},{y1})-({x2},{y2}) 置信度={max_val:.2f}")

            return (x1, y1, x2, y2)

        logger.debug(f"[模板] 未找到 {template_name}, 最高置信度={max_val:.2f} (阈值={threshold})")
        return None

    def find_all_templates(
        self,
        screenshot: Image.Image,
        template_name: str,
        threshold: float = None
    ) -> List[Tuple[int, int, int, int]]:
        """在截图中查找所有匹配的模板

        Returns:
            所有匹配区域的列表
        """
        # 延迟加载：首次使用时加载模板
        if not self.templates:
            self._load_templates()

        if template_name not in self.templates:
            logger.warning(f"模板不存在: {template_name}")
            return []

        threshold = threshold or config.TEMPLATE_THRESHOLD
        template = self.templates[template_name]
        screen = self.pil_to_cv2(screenshot)

        result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        locations = np.where(result >= threshold)

        h, w = template.shape[:2]
        boxes = []

        for pt in zip(*locations[::-1]):
            x1, y1 = pt
            x2, y2 = x1 + w, y1 + h
            boxes.append((x1, y1, x2, y2))

        # 使用 NMS 去除重叠的检测
        boxes = self._non_max_suppression(boxes)

        logger.debug(f"找到 {len(boxes)} 个 {template_name}")

        return boxes

    def _non_max_suppression(
        self,
        boxes: List[Tuple[int, int, int, int]],
        overlap_thresh: float = 0.5
    ) -> List[Tuple[int, int, int, int]]:
        """非极大值抑制，去除重叠的检测框"""
        if len(boxes) == 0:
            return []

        boxes_array = np.array(boxes)
        x1 = boxes_array[:, 0]
        y1 = boxes_array[:, 1]
        x2 = boxes_array[:, 2]
        y2 = boxes_array[:, 3]

        areas = (x2 - x1) * (y2 - y1)
        indices = np.argsort(y1)  # 按 y 坐标排序

        keep = []
        while len(indices) > 0:
            last = len(indices) - 1
            i = indices[last]
            keep.append(i)

            xx1 = np.maximum(x1[i], x1[indices[:last]])
            yy1 = np.maximum(y1[i], y1[indices[:last]])
            xx2 = np.minimum(x2[i], x2[indices[:last]])
            yy2 = np.minimum(y2[i], y2[indices[:last]])

            w = np.maximum(0, xx2 - xx1)
            h = np.maximum(0, yy2 - yy1)

            overlap = (w * h) / areas[indices[:last]]

            indices = np.delete(
                indices,
                np.concatenate(([last], np.where(overlap > overlap_thresh)[0]))
            )

        return [boxes[i] for i in keep]

    def ocr_full_screen(self, screenshot: Image.Image) -> List[Dict]:
        """对整个屏幕进行 OCR

        Returns:
            识别结果列表，每项包含 text, box, confidence
        """
        results = perform_ocr(screenshot)

        ocr_str = ", ".join([f'"{item["text"]}"@({item["box"][0]},{item["box"][1]})' for item in results])
        logger.debug(f"OCR({len(results)}): {ocr_str}")

        return results

    def find_text(
        self,
        screenshot: Image.Image,
        target_text: str,
        partial: bool = True
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找包含指定文字的区域

        Args:
            screenshot: 截图
            target_text: 目标文字
            partial: 是否部分匹配

        Returns:
            找到的区域，未找到返回 None
        """
        ocr_results = self.ocr_full_screen(screenshot)

        for item in ocr_results:
            text = item['text']
            if partial:
                if target_text.lower() in text.lower():
                    logger.debug(f"找到文字 '{target_text}' 在 '{text}'")
                    return item['box']
            else:
                if target_text.lower() == text.lower():
                    logger.debug(f"找到文字 '{target_text}'")
                    return item['box']

        logger.debug(f"未找到文字: {target_text}")
        return None

    def find_text_variants(
        self,
        screenshot: Image.Image,
        pattern_key: str,
        partial: bool = False  # 默认改为精确匹配
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找多语言文本模式

        Args:
            screenshot: 截图
            pattern_key: config.TEXT_PATTERNS 中的键名
            partial: 是否部分匹配（默认精确匹配）

        Returns:
            找到的区域，未找到返回 None
        """
        if pattern_key not in config.TEXT_PATTERNS:
            logger.warning(f"未知的文本模式键: {pattern_key}")
            return None

        patterns = config.TEXT_PATTERNS[pattern_key]
        ocr_results = self.ocr_full_screen(screenshot)

        # 先尝试精确匹配
        for item in ocr_results:
            text = item['text'].strip()
            for pattern in patterns:
                if pattern.lower().strip() == text.lower():
                    logger.debug(f"找到文字模式(精确) '{pattern}' = '{text}'")
                    return item['box']

        # 如果允许部分匹配且精确匹配失败，再尝试部分匹配
        if partial:
            for item in ocr_results:
                text = item['text'].strip()
                for pattern in patterns:
                    if pattern.lower().strip() in text.lower():
                        logger.debug(f"找到文字模式(部分) '{pattern}' 在 '{text}'")
                        return item['box']

        logger.debug(f"未找到任何 '{pattern_key}' 模式")
        return None

    def wait_for_text_variants(
        self,
        adb_controller,
        pattern_key: str,
        timeout: int = None,
        check_interval: int = None
    ) -> bool:
        """等待多语言文本模式出现

        Args:
            adb_controller: ADB 控制器实例
            pattern_key: config.TEXT_PATTERNS 中的键名
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            是否找到
        """
        import time

        timeout = timeout or config.WAIT_BATTLE_TIMEOUT
        check_interval = check_interval or config.WAIT_BATTLE_CHECK_INTERVAL

        start_time = time.time()

        while time.time() - start_time < timeout:
            screenshot = adb_controller.screenshot()
            if screenshot and self.find_text_variants(screenshot, pattern_key):
                return True

            time.sleep(check_interval)

        logger.debug(f"等待 '{pattern_key}' 模式超时")
        return False

    def check_complete_status(self, screenshot: Image.Image) -> Dict[str, bool]:
        """检查界面上的完成状态

        Returns:
            {'complete': bool, 'clear': bool, 'progress': str or None}
        """
        ocr_results = self.ocr_full_screen(screenshot)

        result = {
            'complete': False,
            'clear': False,
            'progress': None
        }

        for item in ocr_results:
            text = item['text'].upper()

            if 'COMPLETE' in text:
                result['complete'] = True

            if 'CLEAR' in text:
                result['clear'] = True

            # 匹配进度格式如 "10/35"
            progress_match = re.search(r'(\d+)\s*/\s*(\d+)', item['text'])
            if progress_match:
                result['progress'] = item['text']

        return result

    def wait_for_text(
        self,
        adb_controller,
        target_text: str,
        timeout: int = None,
        check_interval: int = None
    ) -> bool:
        """等待指定文字出现

        Args:
            adb_controller: ADB 控制器实例
            target_text: 目标文字
            timeout: 超时时间（秒）
            check_interval: 检查间隔（秒）

        Returns:
            是否找到
        """
        import time

        timeout = timeout or config.WAIT_BATTLE_TIMEOUT
        check_interval = check_interval or config.WAIT_BATTLE_CHECK_INTERVAL

        start_time = time.time()

        while time.time() - start_time < timeout:
            screenshot = adb_controller.screenshot()
            if screenshot and self.find_text(screenshot, target_text):
                return True

            time.sleep(check_interval)

        logger.info(f"等待 '{target_text}' 超时")
        return False

    def check_color_ratio(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        hsv_lower: Tuple[int, int, int],
        hsv_upper: Tuple[int, int, int],
        threshold: float = 0.1
    ) -> bool:
        """检测区域内指定颜色占比是否超过阈值

        Args:
            screenshot: PIL 截图
            region: 检测区域 (x1, y1, x2, y2)
            hsv_lower: HSV 颜色下限 (H, S, V)
            hsv_upper: HSV 颜色上限 (H, S, V)
            threshold: 颜色占比阈值

        Returns:
            颜色占比是否超过阈值
        """
        x1, y1, x2, y2 = region
        img = self.pil_to_cv2(screenshot)

        # 确保区域在图像范围内
        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            logger.debug(f"[颜色] 无效区域: ({x1},{y1})-({x2},{y2})")
            return False

        roi = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
        ratio = np.count_nonzero(mask) / mask.size

        logger.debug(f"[颜色] 区域({x1},{y1})-({x2},{y2}) 占比={ratio:.2%} 阈值={threshold:.2%}")

        return ratio >= threshold

    def check_green(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        threshold: float = 0.1
    ) -> bool:
        """便捷方法：检测区域内是否有足够的绿色"""
        return self.check_color_ratio(
            screenshot, region,
            COLORS["green"]["lower"],
            COLORS["green"]["upper"],
            threshold
        )

    def get_color_ratio(
        self,
        screenshot: Image.Image,
        region: Tuple[int, int, int, int],
        hsv_lower: Tuple[int, int, int],
        hsv_upper: Tuple[int, int, int]
    ) -> float:
        """获取区域内指定颜色的占比（用于调试）

        Returns:
            颜色占比 (0.0 - 1.0)
        """
        x1, y1, x2, y2 = region
        img = self.pil_to_cv2(screenshot)

        h, w = img.shape[:2]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(w, x2), min(h, y2)

        if x2 <= x1 or y2 <= y1:
            return 0.0

        roi = img[y1:y2, x1:x2]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
        return np.count_nonzero(mask) / mask.size

    def _calculate_color_region(
        self,
        anchor_box: Tuple[int, int, int, int],
        region_config: Dict
    ) -> Tuple[int, int, int, int]:
        """根据锚点和配置计算颜色检测区域

        Args:
            anchor_box: 锚点区域 (x1, y1, x2, y2)
            region_config: 颜色区域配置

        Returns:
            检测区域 (x1, y1, x2, y2)
        """
        ax1, ay1, ax2, ay2 = anchor_box
        position = region_config["position"]
        offset = region_config["offset"]
        width = region_config["width"]
        height = region_config["height"]

        # 转换比例为像素
        screen_w = config.SCREEN_WIDTH
        screen_h = config.SCREEN_HEIGHT
        offset_px = int(offset * screen_w)
        width_px = int(width * screen_w)
        height_px = int(height * screen_h)

        # 锚点中心
        anchor_cy = (ay1 + ay2) // 2
        anchor_cx = (ax1 + ax2) // 2

        if position == "left":
            x2 = ax1 - offset_px
            x1 = x2 - width_px
            y1 = anchor_cy - height_px // 2
            y2 = anchor_cy + height_px // 2
        elif position == "right":
            x1 = ax2 + offset_px
            x2 = x1 + width_px
            y1 = anchor_cy - height_px // 2
            y2 = anchor_cy + height_px // 2
        elif position == "above":
            y2 = ay1 - offset_px
            y1 = y2 - height_px
            x1 = anchor_cx - width_px // 2
            x2 = anchor_cx + width_px // 2
        elif position == "below":
            y1 = ay2 + offset_px
            y2 = y1 + height_px
            x1 = anchor_cx - width_px // 2
            x2 = anchor_cx + width_px // 2
        else:
            raise ValueError(f"未知的位置: {position}")

        return (x1, y1, x2, y2)

    def check_state(
        self,
        screenshot: Image.Image,
        state_name: str
    ) -> Optional[bool]:
        """根据 COLOR_STATES 配置检测状态

        Args:
            screenshot: PIL 截图
            state_name: COLOR_STATES 中的配置名

        Returns:
            状态值 (True/False)，无法检测返回 None
        """
        if state_name not in COLOR_STATES:
            logger.warning(f"未知的状态配置: {state_name}")
            return None

        state_config = COLOR_STATES[state_name]
        locator = state_config["locator"]

        # 1. 定位锚点
        anchor_box = None
        if locator["type"] == "text_pattern":
            anchor_box = self.find_text_variants(screenshot, locator["key"])
        elif locator["type"] == "template":
            anchor_box = self.find_template(screenshot, locator["key"])
        else:
            logger.warning(f"未知的定位类型: {locator['type']}")
            return None

        if anchor_box is None:
            logger.debug(f"[状态] 无法定位 {state_name} 的锚点")
            return None

        # 2. 计算颜色检测区域
        color_region = self._calculate_color_region(
            anchor_box, state_config["color_region"]
        )

        # 3. 获取颜色配置
        color_name = state_config["color"]
        if color_name not in COLORS:
            logger.warning(f"未知的颜色: {color_name}")
            return None

        color_config = COLORS[color_name]

        # 4. 检测颜色
        result = self.check_color_ratio(
            screenshot,
            color_region,
            color_config["lower"],
            color_config["upper"],
            state_config["threshold"]
        )

        logger.debug(f"[状态] {state_name} = {result}")

        return result


# 便捷的全局实例
_recognizer: Optional[Recognizer] = None


def get_recognizer() -> Recognizer:
    """获取全局识别器实例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = Recognizer()
    return _recognizer
