# -*- coding: utf-8 -*-
"""
快速验证：基础图标模板匹配效果

示例：
python scripts/verify_icon_match.py --image /path/to/screen.png --template /path/to/star.png --out /path/to/out.png

可选：
  --threshold 0.75          匹配阈值
  --nms 0.3                 NMS IoU 阈值
  --scales 0.9,1.0,1.1      多尺度匹配
  --roi 100,200,800,1200    只在 ROI 内匹配 (x1,y1,x2,y2)
"""

import argparse
from typing import List, Tuple, Optional

import cv2
import numpy as np


def parse_scales(value: str) -> List[float]:
    return [float(v.strip()) for v in value.split(",") if v.strip()]


def parse_roi(value: str) -> Tuple[int, int, int, int]:
    parts = [int(v.strip()) for v in value.split(",") if v.strip()]
    if len(parts) != 4:
        raise ValueError("ROI 格式应为 x1,y1,x2,y2")
    return parts[0], parts[1], parts[2], parts[3]


def nms_boxes(
    boxes: List[Tuple[int, int, int, int]], scores: List[float], iou_thresh: float
) -> List[int]:
    if not boxes:
        return []
    boxes_np = np.array(boxes, dtype=np.float32)
    scores_np = np.array(scores, dtype=np.float32)
    x1 = boxes_np[:, 0]
    y1 = boxes_np[:, 1]
    x2 = boxes_np[:, 2]
    y2 = boxes_np[:, 3]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores_np.argsort()[::-1]
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
    return keep


def match_template_multi_scale(
    image_gray: np.ndarray,
    template_gray: np.ndarray,
    scales: List[float],
    method: int,
    mask_gray: Optional[np.ndarray] = None,
) -> List[Tuple[Tuple[int, int], np.ndarray, float]]:
    results = []
    for scale in scales:
        if scale <= 0:
            continue
        th, tw = template_gray.shape[:2]
        new_w = max(1, int(tw * scale))
        new_h = max(1, int(th * scale))
        resized = cv2.resize(
            template_gray, (new_w, new_h), interpolation=cv2.INTER_AREA
        )
        if (
            resized.shape[0] > image_gray.shape[0]
            or resized.shape[1] > image_gray.shape[1]
        ):
            continue
        mask_resized = None
        if mask_gray is not None:
            mask_resized = cv2.resize(
                mask_gray, (new_w, new_h), interpolation=cv2.INTER_NEAREST
            )
        if mask_resized is not None:
            res = cv2.matchTemplate(image_gray, resized, method, mask=mask_resized)
        else:
            res = cv2.matchTemplate(image_gray, resized, method)
        results.append(((new_w, new_h), res, scale))
    return results


def group_boxes(
    boxes: List[Tuple[int, int, int, int]],
    row_tol: float,
    gap: float,
) -> List[List[int]]:
    centers = []
    for idx, (x1, y1, x2, y2) in enumerate(boxes):
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        centers.append((idx, cx, cy))

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

    groups: List[List[int]] = []
    for row in rows:
        items = sorted(row["items"], key=lambda v: v[1])
        current: List[int] = []
        prev_cx = None
        for idx, cx, _ in items:
            if prev_cx is None or (cx - prev_cx) <= gap:
                current.append(idx)
            else:
                if current:
                    groups.append(current)
                current = [idx]
            prev_cx = cx
        if current:
            groups.append(current)
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description="快速验证基础图标模板匹配效果")
    parser.add_argument("--image", required=True, help="截图路径")
    parser.add_argument("--template", required=True, help="基础图标模板路径")
    parser.add_argument("--out", required=True, help="输出标注图路径")
    parser.add_argument("--threshold", type=float, default=0.78, help="匹配阈值 (0-1)")
    parser.add_argument("--nms", type=float, default=0.3, help="NMS IoU 阈值")
    parser.add_argument(
        "--scales", type=parse_scales, default=[1.0], help="多尺度倍率，逗号分隔"
    )
    parser.add_argument(
        "--roi", type=parse_roi, default=None, help="ROI 区域 x1,y1,x2,y2"
    )
    parser.add_argument(
        "--method",
        choices=["ccoeff", "ccorr"],
        default="ccoeff",
        help="模板匹配方法：ccoeff 或 ccorr",
    )
    parser.add_argument(
        "--row-tol",
        type=float,
        default=None,
        help="分组行容差，像素 (默认按模板尺寸推断)",
    )
    parser.add_argument(
        "--gap",
        type=float,
        default=None,
        help="同组图标间距阈值，像素 (默认按模板尺寸推断)",
    )
    parser.add_argument(
        "--min-count",
        type=int,
        default=1,
        help="最小分组数量 (默认 1)",
    )
    parser.add_argument(
        "--draw-groups",
        action="store_true",
        help="绘制分组外框与数量",
    )
    args = parser.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        raise FileNotFoundError(f"无法读取截图: {args.image}")
    template = cv2.imread(args.template, cv2.IMREAD_UNCHANGED)
    if template is None:
        raise FileNotFoundError(f"无法读取模板: {args.template}")

    roi_offset = (0, 0)
    if args.roi is not None:
        x1, y1, x2, y2 = args.roi
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(image.shape[1], x2)
        y2 = min(image.shape[0], y2)
        image_roi = image[y1:y2, x1:x2]
        roi_offset = (x1, y1)
    else:
        image_roi = image

    image_gray = cv2.cvtColor(image_roi, cv2.COLOR_BGR2GRAY)
    mask_gray = None
    if template.ndim == 3 and template.shape[2] == 4:
        bgr = template[:, :, :3]
        alpha = template[:, :, 3]
        mask_gray = cv2.threshold(alpha, 0, 255, cv2.THRESH_BINARY)[1]
        template_gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        if args.method == "ccoeff":
            print("模板含透明通道，已自动改用 ccorr 以支持 mask")
            args.method = "ccorr"
    else:
        template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)

    if args.method == "ccoeff":
        method = cv2.TM_CCOEFF_NORMED
    else:
        method = cv2.TM_CCORR_NORMED

    matches = match_template_multi_scale(
        image_gray, template_gray, args.scales, method, mask_gray
    )
    boxes: List[Tuple[int, int, int, int]] = []
    scores: List[float] = []

    for (tw, th), res, scale in matches:
        loc = np.where(res >= args.threshold)
        for pt in zip(*loc[::-1]):
            x1 = int(pt[0])
            y1 = int(pt[1])
            x2 = x1 + tw
            y2 = y1 + th
            boxes.append((x1, y1, x2, y2))
            scores.append(float(res[y1, x1]))

    keep = nms_boxes(boxes, scores, args.nms)
    output = image.copy()

    kept_boxes = [boxes[idx] for idx in keep]
    kept_scores = [scores[idx] for idx in keep]

    if kept_boxes:
        widths = [b[2] - b[0] for b in kept_boxes]
        heights = [b[3] - b[1] for b in kept_boxes]
        med_w = float(np.median(widths))
        med_h = float(np.median(heights))
        row_tol = args.row_tol if args.row_tol is not None else max(6.0, med_h * 0.6)
        gap = args.gap if args.gap is not None else max(6.0, med_w * 1.6)
    else:
        row_tol = args.row_tol if args.row_tol is not None else 12.0
        gap = args.gap if args.gap is not None else 40.0

    for i, idx in enumerate(keep):
        x1, y1, x2, y2 = boxes[idx]
        x1 += roi_offset[0]
        x2 += roi_offset[0]
        y1 += roi_offset[1]
        y2 += roi_offset[1]
        cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            output,
            f"{scores[idx]:.2f}",
            (x1, max(0, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
        )

    group_indices = group_boxes(kept_boxes, row_tol=row_tol, gap=gap)
    groups_filtered = [g for g in group_indices if len(g) >= args.min_count]
    if args.draw_groups:
        for g in groups_filtered:
            xs1 = [kept_boxes[i][0] for i in g]
            ys1 = [kept_boxes[i][1] for i in g]
            xs2 = [kept_boxes[i][2] for i in g]
            ys2 = [kept_boxes[i][3] for i in g]
            gx1 = min(xs1) + roi_offset[0]
            gy1 = min(ys1) + roi_offset[1]
            gx2 = max(xs2) + roi_offset[0]
            gy2 = max(ys2) + roi_offset[1]
            cv2.rectangle(output, (gx1, gy1), (gx2, gy2), (0, 0, 255), 2)
            cv2.putText(
                output,
                f"cnt={len(g)}",
                (gx1, max(0, gy1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
            )

    cv2.imwrite(args.out, output)

    print("匹配完成")
    print(f"候选框数量: {len(boxes)}")
    print(f"NMS 后数量: {len(keep)}")
    print(f"分组数量: {len(groups_filtered)}")
    print(f"row_tol: {row_tol:.1f}, gap: {gap:.1f}")
    print("分组详情:")
    for idx, g in enumerate(groups_filtered):
        xs = [kept_boxes[i][0] for i in g]
        ys = [kept_boxes[i][1] for i in g]
        print(
            f"  group#{idx}: count={len(g)}, x=[{min(xs)},{max(xs)}], y=[{min(ys)},{max(ys)}]"
        )
    print(f"输出标注图: {args.out}")


if __name__ == "__main__":
    main()
