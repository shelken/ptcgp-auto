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

    # 将 PIL Image 转换为 CGImage
    # 先转为 PNG bytes
    import io
    buffer = io.BytesIO()
    image.save(buffer, format='PNG')
    png_data = buffer.getvalue()

    # 创建 NSData 和 CGImage
    ns_data = NSData.dataWithBytes_length_(png_data, len(png_data))
    image_source = Quartz.CGImageSourceCreateWithData(ns_data, None)
    cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

    if cg_image is None:
        print("无法创建 CGImage")
        return []

    # 获取图像尺寸
    width = image.width
    height = image.height

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
        print("OCR 请求执行失败")
        return []

    # 解析结果
    results = []
    observations = request.results()

    if observations:
        for observation in observations:
            # 获取最佳候选文本
            top_candidate = observation.topCandidates_(1)
            if top_candidate and len(top_candidate) > 0:
                text = top_candidate[0].string()
                confidence = top_candidate[0].confidence()

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

    return results


class Recognizer:
    """界面识别器"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, np.ndarray] = {}
        self._load_templates()
        print("使用 Apple Vision Framework 进行 OCR（原生 Apple Silicon 加速）")

    def _load_templates(self):
        """加载所有模板图片"""
        if not self.templates_dir.exists():
            print(f"警告: 模板目录不存在: {self.templates_dir}")
            return

        for file in self.templates_dir.glob("*.png"):
            name = file.stem
            img = cv2.imread(str(file))
            if img is not None:
                self.templates[name] = img
                print(f"已加载模板: {name}")

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
        if template_name not in self.templates:
            if config.DEBUG:
                print(f"警告: 模板不存在: {template_name}")
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

            if config.DEBUG:
                print(f"[模板] 找到 {template_name}: ({x1},{y1})-({x2},{y2}) 置信度={max_val:.2f}")

            return (x1, y1, x2, y2)

        if config.DEBUG:
            print(f"[模板] 未找到 {template_name}, 最高置信度={max_val:.2f} (阈值={threshold})")
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
        if template_name not in self.templates:
            print(f"警告: 模板不存在: {template_name}")
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

        if config.DEBUG:
            print(f"找到 {len(boxes)} 个 {template_name}")

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

        if config.DEBUG:
            texts = [f'"{item["text"]}"@({item["box"][0]},{item["box"][1]})' for item in results]
            print(f"OCR({len(results)}): {', '.join(texts)}")

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
                    if config.DEBUG:
                        print(f"找到文字 '{target_text}' 在 '{text}'")
                    return item['box']
            else:
                if target_text.lower() == text.lower():
                    if config.DEBUG:
                        print(f"找到文字 '{target_text}'")
                    return item['box']

        if config.DEBUG:
            print(f"未找到文字: {target_text}")
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
            print(f"警告: 未知的文本模式键: {pattern_key}")
            return None

        patterns = config.TEXT_PATTERNS[pattern_key]
        ocr_results = self.ocr_full_screen(screenshot)

        # 先尝试精确匹配
        for item in ocr_results:
            text = item['text'].strip()
            for pattern in patterns:
                if pattern.lower().strip() == text.lower():
                    if config.DEBUG:
                        print(f"找到文字模式(精确) '{pattern}' = '{text}'")
                    return item['box']

        # 如果允许部分匹配且精确匹配失败，再尝试部分匹配
        if partial:
            for item in ocr_results:
                text = item['text'].strip()
                for pattern in patterns:
                    if pattern.lower().strip() in text.lower():
                        if config.DEBUG:
                            print(f"找到文字模式(部分) '{pattern}' 在 '{text}'")
                        return item['box']

        if config.DEBUG:
            print(f"未找到任何 '{pattern_key}' 模式")
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

        if config.DEBUG:
            print(f"等待 '{pattern_key}' 模式超时")
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

        print(f"等待 '{target_text}' 超时")
        return False


# 便捷的全局实例
_recognizer: Optional[Recognizer] = None


def get_recognizer() -> Recognizer:
    """获取全局识别器实例"""
    global _recognizer
    if _recognizer is None:
        _recognizer = Recognizer()
    return _recognizer
