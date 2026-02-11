# -*- coding: utf-8 -*-
"""
每日送卡任务辅助函数。
"""

from typing import Optional


def build_ocr_signature(ocr_results: list[dict]) -> str:
    """构建 OCR 文本签名。"""
    texts = [str(item.get("text", "")).strip() for item in ocr_results]
    return "|".join(sorted(texts))


def find_send_button_for_target(
    ocr_results: list[dict],
    target_nickname: str,
    send_text_patterns: list[str],
) -> Optional[tuple[int, int, int, int]]:
    """按目标昵称匹配对应分送按钮。"""
    target_text = "".join(target_nickname.lower().split())
    nickname_boxes: list[tuple[int, int, int, int]] = []
    for item in ocr_results:
        text = "".join(str(item.get("text", "")).lower().split())
        if text != target_text:
            continue
        box = item.get("box")
        if box and len(box) == 4:
            nickname_boxes.append(tuple(box))

    if not nickname_boxes:
        return None

    send_patterns = {"".join(t.lower().split()) for t in send_text_patterns}
    send_boxes: list[tuple[int, int, int, int]] = []
    for item in ocr_results:
        text = "".join(str(item.get("text", "")).lower().split())
        if text not in send_patterns:
            continue
        box = item.get("box")
        if box and len(box) == 4:
            send_boxes.append(tuple(box))

    best: Optional[tuple[int, int, int, int]] = None
    best_distance: Optional[int] = None
    for nickname_box in nickname_boxes:
        nickname_cy = (nickname_box[1] + nickname_box[3]) // 2
        nickname_cx = (nickname_box[0] + nickname_box[2]) // 2
        for send_box in send_boxes:
            send_cy = (send_box[1] + send_box[3]) // 2
            send_cx = (send_box[0] + send_box[2]) // 2
            if send_cx <= nickname_cx:
                continue
            distance = abs(send_cy - nickname_cy)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = send_box
    return best


def is_target_row_unavailable(
    ocr_results: list[dict],
    target_nickname: str,
    unavailable_patterns: list[str],
    row_threshold_y: int,
) -> bool:
    """判断目标昵称所在行是否包含不可送标记。"""
    target_text = "".join(target_nickname.lower().split())
    nickname_boxes = []
    for item in ocr_results:
        text = "".join(str(item.get("text", "")).lower().split())
        if text == target_text and item.get("box"):
            nickname_boxes.append(item["box"])

    if not nickname_boxes:
        return False

    pattern_set = {"".join(t.lower().split()) for t in unavailable_patterns}
    for nickname_box in nickname_boxes:
        nickname_cy = (nickname_box[1] + nickname_box[3]) // 2
        for item in ocr_results:
            box = item.get("box")
            if not box:
                continue
            text = "".join(str(item.get("text", "")).lower().split())
            if text not in pattern_set:
                continue
            text_cy = (box[1] + box[3]) // 2
            if abs(text_cy - nickname_cy) <= row_threshold_y:
                return True
    return False
