"""
识别器 - OCR + 模板匹配
"""

import os
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import re

import cv2
import numpy as np
from PIL import Image

import config

# 延迟加载 easyocr（初始化较慢）
_ocr_reader = None


def _check_mps_available() -> bool:
    """检查 MPS (Metal Performance Shaders) 是否可用"""
    try:
        import torch
        return torch.backends.mps.is_available()
    except Exception:
        return False


def _check_cuda_available() -> bool:
    """检查 CUDA 是否可用"""
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


def get_ocr_reader():
    """获取 OCR 读取器（延迟初始化）"""
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr

        use_gpu = config.OCR_USE_GPU

        # 检测可用的 GPU 后端
        if use_gpu:
            if _check_cuda_available():
                print("检测到 CUDA GPU，使用 CUDA 加速...")
                gpu_flag = True
            elif _check_mps_available():
                print("检测到 Apple Silicon (MPS)，使用 MPS 加速...")
                # EasyOCR 不直接支持 MPS，但 PyTorch 会自动使用
                # 设置环境变量让某些操作使用 MPS
                os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
                gpu_flag = False  # EasyOCR 的 gpu 参数只针对 CUDA
            else:
                print("未检测到 GPU，使用 CPU...")
                gpu_flag = False
        else:
            print("GPU 已禁用，使用 CPU...")
            gpu_flag = False

        print("初始化 OCR 引擎（首次加载需要下载模型）...")
        _ocr_reader = easyocr.Reader(
            config.OCR_LANGUAGES,
            gpu=gpu_flag,
            model_storage_directory=str(Path.home() / ".easyocr"),
            download_enabled=True
        )
        print("OCR 引擎初始化完成")
    return _ocr_reader


class Recognizer:
    """界面识别器"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = Path(templates_dir)
        self.templates: Dict[str, np.ndarray] = {}
        self._load_templates()

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
                print(f"找到模板 {template_name}: ({x1}, {y1}, {x2}, {y2}), 置信度: {max_val:.2f}")

            return (x1, y1, x2, y2)

        if config.DEBUG:
            print(f"未找到模板 {template_name}, 最高置信度: {max_val:.2f}")
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
        reader = get_ocr_reader()
        screen = self.pil_to_cv2(screenshot)

        results = reader.readtext(screen)

        parsed = []
        for (box, text, confidence) in results:
            # box 是四个角的坐标，转换为矩形
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            x1, x2 = int(min(x_coords)), int(max(x_coords))
            y1, y2 = int(min(y_coords)), int(max(y_coords))

            parsed.append({
                'text': text,
                'box': (x1, y1, x2, y2),
                'confidence': confidence
            })

        if config.DEBUG:
            print(f"OCR 识别到 {len(parsed)} 个文本区域")

        return parsed

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
        variant_key: str,
        partial: bool = True
    ) -> Optional[Tuple[int, int, int, int]]:
        """在截图中查找多语言文本变体

        Args:
            screenshot: 截图
            variant_key: config.TEXT_VARIANTS 中的键名
            partial: 是否部分匹配

        Returns:
            找到的区域，未找到返回 None
        """
        if variant_key not in config.TEXT_VARIANTS:
            print(f"警告: 未知的文本变体键: {variant_key}")
            return None

        variants = config.TEXT_VARIANTS[variant_key]
        ocr_results = self.ocr_full_screen(screenshot)

        for item in ocr_results:
            text = item['text']
            for variant in variants:
                if partial:
                    if variant.lower() in text.lower():
                        if config.DEBUG:
                            print(f"找到文字变体 '{variant}' 在 '{text}'")
                        return item['box']
                else:
                    if variant.lower() == text.lower():
                        if config.DEBUG:
                            print(f"找到文字变体 '{variant}'")
                        return item['box']

        if config.DEBUG:
            print(f"未找到任何 '{variant_key}' 变体")
        return None

    def wait_for_text_variants(
        self,
        adb_controller,
        variant_key: str,
        timeout: int = None,
        check_interval: int = None
    ) -> bool:
        """等待多语言文本变体出现

        Args:
            adb_controller: ADB 控制器实例
            variant_key: config.TEXT_VARIANTS 中的键名
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
            if screenshot and self.find_text_variants(screenshot, variant_key):
                return True

            time.sleep(check_interval)

        if config.DEBUG:
            print(f"等待 '{variant_key}' 变体超时")
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
