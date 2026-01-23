# -*- coding: utf-8 -*-
"""
页面检测器模块

识别当前游戏界面，支持动态加载任务专用页面规则。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PIL import Image

from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.ocr import OcrEngine, OcrResult
from ptcgp_auto_v2.infra.template import TemplateMatcher, TemplateMatch

logger = logging.getLogger(__name__)


@dataclass
class PageMatch:
    """页面匹配结果"""

    page_name: str
    page_info: dict
    match_type: str  # "text" or "template"
    matched_text: Optional[str] = None
    matched_template: Optional[str] = None
    box: Optional[Tuple[int, int, int, int]] = None
    ocr_results: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "page_name": self.page_name,
            "match_type": self.match_type,
            "matched_text": self.matched_text,
            "matched_template": self.matched_template,
            "box": self.box,
        }


class PageDetector:
    """
    页面检测器

    根据 OCR 和模板匹配结果识别当前游戏界面。
    支持动态加载任务专用页面规则。
    """

    def __init__(
        self,
        adb: AdbController,
        ocr_engine: OcrEngine,
        template_matcher: TemplateMatcher,
        base_pages: Optional[List[dict]] = None,
    ):
        """
        初始化页面检测器

        Args:
            adb: ADB 控制器
            ocr_engine: OCR 引擎
            template_matcher: 模板匹配器
            base_pages: 基础页面规则列表
        """
        self.adb = adb
        self.ocr_engine = ocr_engine
        self.template_matcher = template_matcher
        self.base_pages = base_pages or []
        self.task_pages: List[dict] = []
        self._last_screenshot: Optional[Image.Image] = None
        self._last_ocr_results: List[dict] = []

    def load_base_pages(self, pages: List[dict]):
        """
        加载基础页面规则

        Args:
            pages: 页面规则列表
        """
        self.base_pages = pages

    def load_task_pages(self, pages: List[dict]):
        """
        加载任务专用页面规则

        Args:
            pages: 任务专用页面规则列表
        """
        self.task_pages = pages

    def clear_task_pages(self):
        """清除任务专用页面规则"""
        self.task_pages = []

    def _get_merged_pages(self) -> List[dict]:
        """
        获取合并后的页面规则（按优先级排序）

        Returns:
            合并并排序后的页面规则列表
        """
        all_pages = self.base_pages + self.task_pages
        return sorted(all_pages, key=lambda p: p.get("priority", 0))

    def detect(
        self,
        screenshot: Optional[Image.Image] = None,
    ) -> Tuple[str, dict]:
        """
        检测当前界面

        Args:
            screenshot: PIL Image 截图（可选，不提供则自动截图）

        Returns:
            (页面名称, 页面配置)，未识别返回 ("unknown", {})
        """
        # 截图
        if screenshot is None:
            screenshot = self.adb.screenshot()
            if screenshot is None:
                logger.error("截图失败")
                return "unknown", {}

        self._last_screenshot = screenshot

        # OCR 识别
        ocr_results = self.ocr_engine.recognize_as_dict(screenshot)
        self._last_ocr_results = ocr_results
        self._log_ocr_results(ocr_results)
        ocr_texts = [item["text"].strip().lower() for item in ocr_results]

        # 按优先级遍历页面规则
        for page_info in self._get_merged_pages():
            page_name = page_info.get("name", "")
            identifiers = page_info.get("identifiers", [])
            templates = page_info.get("templates", [])
            exact_match = page_info.get("exact_match", False)
            match_all = page_info.get("match_all", False)
            exclude_identifiers = page_info.get("exclude_identifiers", [])

            # 检查排除条件
            if exclude_identifiers:
                excluded = False
                for exclude in exclude_identifiers:
                    if any(exclude.lower() in t for t in ocr_texts):
                        excluded = True
                        break
                if excluded:
                    continue

            # 检查文字标识符
            text_match = self._check_text_identifiers(
                identifiers, ocr_results, exact_match, match_all
            )

            if text_match:
                # 如果有模板要求，也必须匹配模板
                if templates:
                    template_match = self._check_templates(screenshot, templates)
                    if not template_match:
                        continue  # 模板不匹配，跳过

                logger.debug(
                    f'[匹配] {page_name} <- "{text_match["identifier"]}" '
                    f'in "{text_match.get("matched_text", "")}"'
                )

                # 添加 OCR 结果到页面信息
                page_info_with_ocr = {**page_info, "ocr_results": ocr_results}
                return page_name, page_info_with_ocr

            # 检查纯模板匹配（没有 identifiers 的情况）
            if not identifiers and templates:
                template_match = self._check_templates(screenshot, templates)
                if template_match:
                    logger.debug(
                        f"[匹配] {page_name} <- 模板 {template_match['template']}"
                    )
                    page_info_with_ocr = {**page_info, "ocr_results": ocr_results}
                    return page_name, page_info_with_ocr

        # 没有匹配到任何界面
        logger.debug("[未匹配] 无法识别当前界面")
        return "unknown", {"ocr_results": ocr_results}

    def _check_text_identifiers(
        self,
        identifiers: List[str],
        ocr_results: List[dict],
        exact_match: bool,
        match_all: bool = False,
    ) -> Optional[dict]:
        """
        检查文字标识符匹配

        Args:
            identifiers: 要匹配的文字列表
            ocr_results: OCR 识别结果
            exact_match: 是否精确匹配
            match_all: 是否要求所有 identifiers 都匹配

        Returns:
            匹配信息或 None
        """
        if not identifiers:
            return None

        if match_all:
            # AND 逻辑：所有 identifiers 都必须匹配
            matched_items = []
            for identifier in identifiers:
                found = self._find_identifier(identifier, ocr_results, exact_match)
                if not found:
                    return None
                matched_items.append(found)
            return matched_items[0] if matched_items else None
        else:
            # OR 逻辑：任意一个匹配即可
            for identifier in identifiers:
                found = self._find_identifier(identifier, ocr_results, exact_match)
                if found:
                    return found
            return None

    def _find_identifier(
        self,
        identifier: str,
        ocr_results: List[dict],
        exact_match: bool,
    ) -> Optional[dict]:
        """查找单个标识符"""
        identifier_lower = identifier.lower()
        identifier_normalized = "".join(identifier_lower.split())

        for ocr_item in ocr_results:
            ocr_text = ocr_item["text"].strip()
            ocr_lower = ocr_text.lower()
            ocr_normalized = "".join(ocr_lower.split())

            if exact_match:
                matched = identifier_lower == ocr_lower
            else:
                matched = (
                    identifier_lower == ocr_lower
                    or identifier_lower in ocr_lower
                    or identifier_normalized in ocr_normalized
                )

            if matched:
                return {
                    "type": "text",
                    "identifier": identifier,
                    "matched_text": ocr_text,
                    "box": ocr_item["box"],
                }

        return None

    def _check_templates(
        self,
        screenshot: Image.Image,
        templates: List[str],
    ) -> Optional[dict]:
        """检查模板匹配"""
        for template_name in templates:
            match = self.template_matcher.find(screenshot, template_name)
            if match:
                return {
                    "type": "template",
                    "template": template_name,
                    "box": match.box,
                }
        return None

    def get_last_screenshot(self) -> Optional[Image.Image]:
        """获取最近一次截图"""
        return self._last_screenshot

    def _log_ocr_results(self, ocr_results: List[dict]):
        """打印 OCR 识别结果（调试用）"""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        if not ocr_results:
            logger.debug("OCR(0): 无识别结果")
            return

        items = []
        for item in ocr_results:
            text = item.get("text", "").strip()
            box = item.get("box")
            if box and len(box) == 4:
                cx = (box[0] + box[2]) // 2
                cy = (box[1] + box[3]) // 2
                items.append(f'"{text}"@({cx},{cy})')
            else:
                items.append(f'"{text}"')
        logger.debug(f"OCR({len(ocr_results)}): {', '.join(items)}")

    def get_last_ocr_results(self) -> List[dict]:
        """获取最近一次 OCR 结果"""
        return self._last_ocr_results

    def get_last_page_context(self) -> tuple[Optional[Image.Image], List[dict]]:
        """获取最近一次页面上下文（截图 + OCR 结果）"""
        return self._last_screenshot, self._last_ocr_results

    def capture(
        self, screenshot: Optional[Image.Image] = None
    ) -> tuple[Optional[Image.Image], List[dict]]:
        """刷新截图与 OCR 结果，并写入缓存"""
        if screenshot is None:
            screenshot = self.adb.screenshot()
            if screenshot is None:
                return None, []
        self._last_screenshot = screenshot
        ocr_results = self.ocr_engine.recognize_as_dict(screenshot)
        self._last_ocr_results = ocr_results
        return screenshot, ocr_results

    def find_template_with_scale(
        self,
        template_name: str,
        scale: float = 1.0,
        threshold: Optional[float] = None,
        screenshot: Optional[Image.Image] = None,
    ) -> Optional[TemplateMatch]:
        """按指定缩放比例匹配模板（缩放为相对系数）"""
        if screenshot is None:
            screenshot = self._last_screenshot or self.adb.screenshot()
            if screenshot is None:
                return None
        self._last_screenshot = screenshot

        return self.template_matcher.find_with_scale(
            screenshot, template_name, scale=scale, threshold=threshold
        )

    def find_text(
        self,
        text: str,
        screenshot: Optional[Image.Image] = None,
        exact_match: bool = False,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        在屏幕上查找文字

        Args:
            text: 要查找的文字
            screenshot: 截图（可选）
            exact_match: 是否精确匹配

        Returns:
            文字的边界框 (x1, y1, x2, y2) 或 None
        """
        if screenshot is None:
            screenshot = self.adb.screenshot()
            if screenshot is None:
                return None

        result = self.ocr_engine.find_text(screenshot, text, exact_match)
        return result.box if result else None

    def find_template(
        self,
        template_name: str,
        screenshot: Optional[Image.Image] = None,
        threshold: float = 0.7,
    ) -> Optional[Tuple[int, int, int, int]]:
        """
        在屏幕上查找模板

        Args:
            template_name: 模板名称
            screenshot: 截图（可选）
            threshold: 匹配阈值

        Returns:
            模板的边界框 (x1, y1, x2, y2) 或 None
        """
        if screenshot is None:
            screenshot = self._last_screenshot or self.adb.screenshot()
            if screenshot is None:
                return None
        self._last_screenshot = screenshot

        return self.template_matcher.find_box(screenshot, template_name, threshold)
