# -*- coding: utf-8 -*-
"""
小图标检测与分组模块

用于在指定 ROI 内检测模板图标，并根据行与间距进行分组。
"""

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.infra.template import TemplateMatcher


@dataclass
class IconHit:
    template_name: str
    score: float
    box: Tuple[int, int, int, int]
    center: Tuple[float, float]


@dataclass
class IconGroup:
    template_name: str
    count: int
    boxes: List[Tuple[int, int, int, int]]
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _calc_center(box: Tuple[int, int, int, int]) -> Tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2.0, (y1 + y2) / 2.0


def _nms_boxes(
    boxes: List[Tuple[int, int, int, int, float]],
    iou_thresh: float,
) -> List[Tuple[int, int, int, int, float]]:
    if not boxes:
        return []
    boxes_array = np.array(boxes, dtype=np.float32)
    x1 = boxes_array[:, 0]
    y1 = boxes_array[:, 1]
    x2 = boxes_array[:, 2]
    y2 = boxes_array[:, 3]
    scores = boxes_array[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]

    keep = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        remain = np.where(iou <= iou_thresh)[0]
        order = order[remain + 1]

    return [tuple(boxes_array[i]) for i in keep]


class IconGroupDetector:
    def __init__(self, template_matcher: Optional[TemplateMatcher] = None):
        self.template_matcher = template_matcher or TemplateMatcher()

    def load_templates(
        self, templates: Iterable[str], screen_width: Optional[int] = None
    ):
        if screen_width:
            self.template_matcher.set_screen_width(screen_width)
        for template_path in templates:
            self.template_matcher.load_template(template_path)

    def detect_icons(
        self,
        screenshot: Image.Image,
        template_paths: Dict[str, str],
        roi: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = 0.8,
        nms_iou: float = 0.3,
        screen_width: Optional[int] = None,
    ) -> List[IconHit]:
        if screen_width:
            self.template_matcher.set_screen_width(screen_width)
        if roi is None:
            roi = (0, 0, screenshot.width, screenshot.height)

        roi_x1, roi_y1, roi_x2, roi_y2 = roi
        cropped = screenshot.crop((roi_x1, roi_y1, roi_x2, roi_y2))
        screen = _pil_to_bgr(cropped)

        hits: List[IconHit] = []
        for template_name, template_path in template_paths.items():
            self.template_matcher.load_template(template_path)
            template_key = (
                template_path[:-4] if template_path.endswith(".png") else template_path
            )
            template = self.template_matcher.templates.get(template_key)
            if template is None:
                continue

            if (
                template.shape[0] > screen.shape[0]
                or template.shape[1] > screen.shape[1]
            ):
                continue

            result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
            loc = np.where(result >= threshold)
            h, w = template.shape[:2]
            boxes = []
            for pt in zip(*loc[::-1]):
                x1, y1 = int(pt[0]), int(pt[1])
                x2, y2 = x1 + w, y1 + h
                score = float(result[y1, x1])
                boxes.append((x1, y1, x2, y2, score))

            filtered = _nms_boxes(boxes, nms_iou)
            for x1, y1, x2, y2, score in filtered:
                box = (
                    int(x1 + roi_x1),
                    int(y1 + roi_y1),
                    int(x2 + roi_x1),
                    int(y2 + roi_y1),
                )
                hits.append(
                    IconHit(
                        template_name=template_name,
                        score=score,
                        box=box,
                        center=_calc_center(box),
                    )
                )

        return hits

    def group_hits(
        self,
        hits: List[IconHit],
        row_tol: float,
        gap: float,
        min_count: int = 1,
    ) -> List[IconGroup]:
        groups: List[IconGroup] = []
        by_template: Dict[str, List[IconHit]] = {}
        for hit in hits:
            by_template.setdefault(hit.template_name, []).append(hit)

        for template_name, items in by_template.items():
            groups.extend(
                _group_hits_for_template(items, template_name, row_tol, gap, min_count)
            )

        return groups


def _group_hits_for_template(
    hits: List[IconHit],
    template_name: str,
    row_tol: float,
    gap: float,
    min_count: int,
) -> List[IconGroup]:
    centers = [(idx, hit.center[0], hit.center[1]) for idx, hit in enumerate(hits)]
    centers.sort(key=lambda v: v[2])

    rows: List[dict] = []
    for idx, cx, cy in centers:
        best_row = None
        best_dist = None
        for row in rows:
            dist = abs(cy - row["cy"])
            if dist <= row_tol and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_row = row
        if best_row is None:
            rows.append({"cy": cy, "items": [(idx, cx, cy)]})
        else:
            best_row["items"].append((idx, cx, cy))
            best_row["cy"] = sum(v[2] for v in best_row["items"]) / len(
                best_row["items"]
            )

    result: List[IconGroup] = []
    for row in rows:
        items = sorted(row["items"], key=lambda v: v[1])
        current: List[int] = []
        prev_cx = None
        for idx, cx, _ in items:
            if prev_cx is None or (cx - prev_cx) <= gap:
                current.append(idx)
            else:
                if len(current) >= min_count:
                    result.append(_build_group(template_name, hits, current))
                current = [idx]
            prev_cx = cx
        if len(current) >= min_count:
            result.append(_build_group(template_name, hits, current))

    return result


def _build_group(
    template_name: str,
    hits: List[IconHit],
    indices: List[int],
) -> IconGroup:
    boxes = [hits[i].box for i in indices]
    x1 = min(b[0] for b in boxes)
    y1 = min(b[1] for b in boxes)
    x2 = max(b[2] for b in boxes)
    y2 = max(b[3] for b in boxes)
    bbox = (x1, y1, x2, y2)
    return IconGroup(
        template_name=template_name,
        count=len(indices),
        boxes=boxes,
        bbox=bbox,
        center=_calc_center(bbox),
    )


def count_icons(template_name: str, hits: List[IconHit]) -> int:
    return sum(1 for hit in hits if hit.template_name == template_name)


def filter_groups(
    template_name: str,
    groups: List[IconGroup],
    min_count: int = 1,
) -> List[IconGroup]:
    return [
        group
        for group in groups
        if group.template_name == template_name and group.count >= min_count
    ]


def find_group_by_rarity(
    rarity_code: str,
    groups: List[IconGroup],
    rarity_reverse: Dict[str, Tuple[str, int]],
) -> Optional[IconGroup]:
    pattern = rarity_reverse.get(rarity_code)
    if not pattern:
        return None
    template_name, count = pattern
    candidates = [
        group
        for group in groups
        if group.template_name == template_name and group.count == count
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda g: (g.center[1], g.center[0]))
    return candidates[0]
