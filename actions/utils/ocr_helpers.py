"""OCR 辅助工具"""

import re
from typing import List, Dict, Optional, Tuple

import config


def find_text_by_variants(ocr_results: List[Dict], pattern_key: str) -> Optional[Dict]:
    """根据 TEXT_PATTERNS 配置查找文本

    Args:
        ocr_results: OCR 结果列表
        pattern_key: TEXT_PATTERNS 中的 key

    Returns:
        找到的 OCR item，包含 text 和 box
    """
    patterns = config.TEXT_PATTERNS.get(pattern_key, [])
    for item in ocr_results:
        text = item['text'].strip()
        for pattern in patterns:
            if pattern in text:
                return item
    return None


def find_all_by_variants(ocr_results: List[Dict], pattern_key: str) -> List[Dict]:
    """根据 TEXT_PATTERNS 配置查找所有匹配的文本"""
    patterns = config.TEXT_PATTERNS.get(pattern_key, [])
    results = []
    for item in ocr_results:
        text = item['text'].strip()
        for pattern in patterns:
            if pattern in text:
                results.append(item)
                break
    return results


def extract_progress(text: str) -> Optional[Tuple[int, int]]:
    """从文本中提取进度数字

    Args:
        text: 包含进度的文本，如 "21/30"

    Returns:
        (current, total) 元组，或 None
    """
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def find_items_on_same_row(
    ocr_results: List[Dict],
    reference_y: int,
    tolerance: int = 150
) -> List[Dict]:
    """查找与参考 Y 坐标在同一行的所有项目

    Args:
        ocr_results: OCR 结果列表
        reference_y: 参考 Y 坐标
        tolerance: Y 坐标容差

    Returns:
        同一行的项目列表
    """
    results = []
    for item in ocr_results:
        item_y = (item['box'][1] + item['box'][3]) // 2
        if abs(item_y - reference_y) < tolerance:
            results.append(item)
    return results


def group_by_row(ocr_results: List[Dict], tolerance: int = 100) -> List[List[Dict]]:
    """按 Y 坐标将 OCR 结果分组为行

    Args:
        ocr_results: OCR 结果列表
        tolerance: 同一行的 Y 坐标容差

    Returns:
        分组后的行列表，每行按 X 坐标排序
    """
    if not ocr_results:
        return []

    # 按 Y 坐标排序
    items = sorted(ocr_results, key=lambda x: (x['box'][1] + x['box'][3]) // 2)

    rows = []
    current_row = []
    row_start_y = None

    for item in items:
        item_y = (item['box'][1] + item['box'][3]) // 2
        if row_start_y is None or abs(item_y - row_start_y) < tolerance:
            current_row.append(item)
            if row_start_y is None:
                row_start_y = item_y
        else:
            if current_row:
                # 按 X 坐标排序
                current_row.sort(key=lambda x: (x['box'][0] + x['box'][2]) // 2)
                rows.append(current_row)
            current_row = [item]
            row_start_y = item_y

    if current_row:
        current_row.sort(key=lambda x: (x['box'][0] + x['box'][2]) // 2)
        rows.append(current_row)

    return rows
