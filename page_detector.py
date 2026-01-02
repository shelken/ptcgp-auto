"""
页面检测器 - 识别当前游戏界面
"""

from typing import Optional, Dict, Tuple, List

import config
from recognizer import Recognizer


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
            match_info = self._check_text_identifiers(
                identifiers, ocr_results, exact_match
            )
            if match_info:
                match_info["ocr_results"] = ocr_results
                if config.DEBUG:
                    print(f"[匹配] {page_name} <- \"{match_info['identifier']}\" in \"{match_info.get('matched_text', '')}\"")
                return page_name, page_info, match_info

            # 检查模板匹配
            match_info = self._check_templates(screenshot, templates, ocr_results)
            if match_info:
                if config.DEBUG:
                    print(f"[匹配] {page_name} <- 模板 {match_info['template']}")
                return page_name, page_info, match_info

        # 没有匹配到任何界面
        if config.DEBUG:
            print(f"[未匹配] 无法识别当前界面")

        return None, None, None

    def _check_text_identifiers(
        self,
        identifiers: List[str],
        ocr_results: List[Dict],
        exact_match: bool
    ) -> Optional[Dict]:
        """检查文字标识符匹配"""
        for identifier in identifiers:
            for ocr_item in ocr_results:
                ocr_text = ocr_item['text'].strip()

                # 根据 exact_match 决定匹配方式
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
