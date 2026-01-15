"""
页面检测器 - 识别当前游戏界面
"""

from typing import Optional, Dict, Tuple, List

import config
from logger import get_logger
from recognizer import Recognizer

logger = get_logger(__name__)


class PageDetector:
    """页面检测器"""

    def __init__(self, recognizer: Recognizer):
        self.recognizer = recognizer

    def detect(self, screenshot) -> Tuple[Optional[str], Optional[Dict], Optional[Dict]]:
        """检测当前界面

        Args:
            screenshot: PIL Image 截图

        Returns:
            (页面名称, 页面配置, 匹配信息)
        """
        # 获取 OCR 结果
        ocr_results = self.recognizer.ocr_full_screen(screenshot)
        ocr_texts = [item['text'].strip().lower() for item in ocr_results]

        # 按优先级排序页面
        sorted_pages = sorted(
            config.PAGES.items(),
            key=lambda x: x[1].get("priority", 999)
        )

        for page_name, page_info in sorted_pages:
            identifiers = page_info.get("identifiers", [])
            templates = page_info.get("templates", [])
            exact_match = page_info.get("exact_match", False)
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
            match_all = page_info.get("match_all", False)
            match_info = self._check_text_identifiers(
                identifiers, ocr_results, exact_match, match_all
            )
            if match_info:
                # 如果有模板要求，也必须匹配模板
                if templates:
                    template_match = self._check_templates(screenshot, templates, ocr_results)
                    if not template_match:
                        continue  # 模板不匹配，跳过这个页面
                    # 合并模板匹配信息
                    match_info["template_match"] = template_match

                match_info["ocr_results"] = ocr_results
                logger.debug(f"[匹配] {page_name} <- \"{match_info['identifier']}\" in \"{match_info.get('matched_text', '')}\"")
                return page_name, page_info, match_info

            # 检查纯模板匹配（没有 identifiers 的情况）
            if not identifiers:
                match_info = self._check_templates(screenshot, templates, ocr_results)
                if match_info:
                    logger.debug(f"[匹配] {page_name} <- 模板 {match_info['template']}")
                    return page_name, page_info, match_info

        # 没有匹配到任何界面
        logger.debug("[未匹配] 无法识别当前界面")

        return None, None, None

    def _check_text_identifiers(
        self,
        identifiers: List[str],
        ocr_results: List[Dict],
        exact_match: bool,
        match_all: bool = False
    ) -> Optional[Dict]:
        """检查文字标识符匹配

        Args:
            identifiers: 要匹配的文字列表
            ocr_results: OCR 识别结果
            exact_match: 是否精确匹配
            match_all: 是否要求所有 identifiers 都匹配（默认 False，任意一个匹配即可）
        """
        if match_all:
            # AND 逻辑：所有 identifiers 都必须匹配
            matched_items = []
            for identifier in identifiers:
                found = self._find_identifier(identifier, ocr_results, exact_match)
                if not found:
                    return None  # 有一个没找到就失败
                matched_items.append(found)
            # 所有都找到了，返回第一个匹配项的信息
            return matched_items[0] if matched_items else None
        else:
            # OR 逻辑：任意一个匹配即可（原有行为）
            for identifier in identifiers:
                found = self._find_identifier(identifier, ocr_results, exact_match)
                if found:
                    return found
            return None

    def _find_identifier(
        self,
        identifier: str,
        ocr_results: List[Dict],
        exact_match: bool
    ) -> Optional[Dict]:
        """查找单个标识符"""
        for ocr_item in ocr_results:
            ocr_text = ocr_item['text'].strip()

            if exact_match:
                matched = identifier.lower() == ocr_text.lower()
            else:
                matched = (identifier.lower() == ocr_text.lower() or
                           identifier.lower() in ocr_text.lower())

            if matched:
                return {
                    "type": "text",
                    "identifier": identifier,
                    "matched_text": ocr_text,
                    "box": ocr_item['box'],
                }
        return None

    def _check_templates(
        self,
        screenshot,
        templates: List[str],
        ocr_results: List[Dict]
    ) -> Optional[Dict]:
        """检查模板匹配"""
        for template_name in templates:
            template_box = self.recognizer.find_template(
                screenshot, template_name, threshold=0.7
            )
            if template_box:
                return {
                    "type": "template",
                    "template": template_name,
                    "box": template_box,
                    "ocr_results": ocr_results,
                }
        return None
