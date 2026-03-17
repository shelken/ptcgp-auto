#!/usr/bin/env python3
"""
大规模匹配测试（对齐正方形 pad + 可选 CoreML）

对齐点：
- 正方形 pad（右侧/下方补零）
- YOLO OBB 推理
"""

import sys
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
from PIL import Image

try:
    from ultralytics import YOLO  # type: ignore

    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    YOLO = None

# 复用原脚本的工具函数
sys.path.insert(0, str(Path(__file__).parent))
from test_massive_matching import (  # type: ignore
    SimpleAdbController,
    discover_all_card_sets,
    discover_devices_simple,
    load_hash_database,
    load_multiple_hash_databases,
    match_against_database,
)


def detect_cards(
    model_path: str,
    pil_image: Image.Image,
    conf_threshold: float,
    pad_square: bool,
    task: str,
    debug_obb: bool,
):
    if not ULTRALYTICS_AVAILABLE or YOLO is None:
        raise ImportError("ultralytics not installed")

    print("     [1/7] 加载 YOLO 模型...", end=" ")
    t0 = time.perf_counter()
    model = YOLO(model_path, task=task)
    print(f"✅ ({(time.perf_counter() - t0) * 1000:.1f}ms)")

    print("     [2/7] PIL 转 numpy...", end=" ")
    t1 = time.perf_counter()
    img_array = np.array(pil_image)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    print(f"✅ ({(time.perf_counter() - t1) * 1000:.1f}ms)")

    original_height, original_width = img_bgr.shape[:2]
    padded_img = img_bgr
    if pad_square:
        max_size = max(original_width, original_height)
        padded_img = np.zeros((max_size, max_size, 3), dtype=img_bgr.dtype)
        padded_img[:original_height, :original_width] = img_bgr
        print(
            f"     启用正方形 pad: {original_width}x{original_height} -> {max_size}x{max_size}"
        )

    print("     [3/7] YOLO 推理...", end=" ")
    t2 = time.perf_counter()
    results = model(padded_img, verbose=False)
    result = results[0]
    print(f"✅ ({(time.perf_counter() - t2) * 1000:.1f}ms)")

    if result.obb is None or len(result.obb) == 0:
        print("     ❌ 未检测到卡牌")
        return [], img_bgr, img_bgr.copy()

    print("     [4/7] 处理检测框...", end=" ")
    t3 = time.perf_counter()
    vis_img = img_bgr.copy()
    cropped_cards = []

    for i, obb in enumerate(result.obb):
        conf = float(obb.conf[0].item())
        if conf < conf_threshold:
            continue

        if hasattr(obb, "xyxy") and obb.xyxy is not None:
            x1, y1, x2, y2 = map(int, obb.xyxy[0])
            if debug_obb:
                print(f"       [OBB#{i + 1}] xyxy=({x1},{y1},{x2},{y2})")
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(padded_img.shape[1], x2), min(padded_img.shape[0], y2)
            x2, y2 = min(original_width, x2), min(original_height, y2)
            cropped = img_bgr[y1:y2, x1:x2]
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        elif hasattr(obb, "xyxyxyxy") and obb.xyxyxyxy is not None:
            xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
            if xyxyxyxy.max() <= 1.5:
                xyxyxyxy[:, 0] *= padded_img.shape[1]
                xyxyxyxy[:, 1] *= padded_img.shape[0]
            corners = xyxyxyxy.astype(np.float32)
            if debug_obb:
                print(
                    f"       [OBB#{i + 1}] xyxyxyxy(min={corners.min():.1f}, max={corners.max():.1f})"
                )

            def _edge_len(a, b):
                return float(np.linalg.norm(a - b))

            w1 = _edge_len(corners[0], corners[1])
            w2 = _edge_len(corners[2], corners[3])
            h1 = _edge_len(corners[0], corners[3])
            h2 = _edge_len(corners[1], corners[2])
            target_w = max(1, int((w1 + w2) / 2))
            target_h = max(1, int((h1 + h2) / 2))

            dst = np.array(
                [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
                dtype=np.float32,
            )
            matrix = cv2.getPerspectiveTransform(corners, dst)
            cropped = cv2.warpPerspective(padded_img, matrix, (target_w, target_h))

            center_x = corners[:, 0].mean()
            center_y = corners[:, 1].mean()
            x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
            x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())
            x2, y2 = min(original_width, x2), min(original_height, y2)

            cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        else:
            continue

        conf_text = f"{conf:.2f}"
        text_x = x1
        text_y = y1 - 5 if y1 > 20 else y1 + 20
        cv2.putText(
            vis_img,
            conf_text,
            (text_x, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        cropped_cards.append(
            {
                "index": i + 1,
                "confidence": conf,
                "cropped": cropped,
                "center_x": center_x,
                "center_y": center_y,
                "bbox": (x1, y1, x2, y2),
            }
        )

    process_time = (time.perf_counter() - t3) * 1000
    print(f"✅ ({process_time:.1f}ms, {len(cropped_cards)}张卡牌)")
    return cropped_cards, img_bgr, vis_img


def sort_by_rows(cards: List[dict]) -> List[dict]:
    if not cards:
        return cards
    sorted_by_y = sorted(cards, key=lambda c: c["center_y"])
    rows = []
    current_row = [sorted_by_y[0]]
    row_threshold = 10

    for card in sorted_by_y[1:]:
        if abs(card["center_y"] - current_row[0]["center_y"]) < row_threshold:
            current_row.append(card)
        else:
            current_row.sort(key=lambda c: c["center_x"])
            rows.append(current_row)
            current_row = [card]

    if current_row:
        current_row.sort(key=lambda c: c["center_x"])
        rows.append(current_row)

    result = []
    for row in rows:
        result.extend(row)
    return result


def run_matching_test_with_db(
    model_path: str,
    hash_db: Dict[str, np.ndarray],
    hash_db_path: Path,
    screenshot: Image.Image,
    similarity_threshold: float,
    source: str,
    conf_threshold: float,
    pad_square: bool,
    task: str,
    debug_obb: bool,
):
    print("=" * 70)
    print(f"大规模匹配测试（{source} 模式）")
    print("=" * 70)

    print(f"📂 使用数据库: {hash_db_path}")
    print(f"   已加载 {len(hash_db)} 张卡牌")
    print(f"\n✅ 截图: {screenshot.width}x{screenshot.height}")

    print(f"\n🚀 加载模型并检测: {model_path}")
    print(f"   置信度阈值: {conf_threshold}")

    cropped_cards, _, vis_img = detect_cards(
        model_path,
        screenshot,
        conf_threshold=conf_threshold,
        pad_square=pad_square,
        task=task,
        debug_obb=debug_obb,
    )

    if not cropped_cards:
        print("❌ 未检测到任何卡牌")
        return

    cropped_cards = sort_by_rows(cropped_cards)
    for i, card in enumerate(cropped_cards, 1):
        card["index"] = i

    print(f"\n🔍 开始匹配 ({len(cropped_cards)} 张检测 × {len(hash_db)} 张数据库)")
    matches, total_checked, above_threshold, vis_img = match_against_database(
        cropped_cards, hash_db, vis_img, similarity_threshold
    )

    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"   检测到的卡牌: {len(cropped_cards)} 张")
    print(f"   数据库卡牌数: {len(hash_db)} 张")
    print(f"   总比对次数: {total_checked:,} 次")
    print(f"   阈值以上次数: {above_threshold} 次")
    print(f"   成功匹配: {len(matches)} 张")
    print(f"   匹配率: {len(matches) / len(cropped_cards) * 100:.1f}%")

    if matches:
        avg_sim = sum(m.similarity for m in matches) / len(matches)
        print(f"   平均相似度: {avg_sim:.4f}")

    if vis_img is not None:
        vis_path = Path("output/detection_result_pad.jpg")
        vis_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(vis_path), vis_img)
        print(f"   💾 已保存可视化: {vis_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="大规模匹配测试（pad/coreml对齐）")
    parser.add_argument("--set", default="A1", help="要匹配的卡牌系列")
    parser.add_argument("--all", action="store_true", help="匹配所有可用系列")
    parser.add_argument("--image", help="从指定图片文件加载截图")
    parser.add_argument("--conf", type=float, default=0.55, help="YOLO 置信度阈值")
    parser.add_argument("--coreml", action="store_true", help="使用 CoreML 模型")
    parser.add_argument("--pad-square", action="store_true", help="启用正方形 pad")
    parser.add_argument("--task", default="obb", help="YOLO 任务类型")
    parser.add_argument("--debug-obb", action="store_true", help="打印 OBB 坐标调试")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    if args.coreml:
        model_path = (
            repo_root / "data/models/yolo11n-5k-25-2026.02.02/best.mlpackage"
        ).resolve()
    else:
        model_path = (
            repo_root / "data/models/yolo11n-5k-25-2026.02.02/best.pt"
        ).resolve()

    if not model_path.exists():
        print(f"❌ 模型不存在: {model_path}")
        sys.exit(1)

    if args.image:
        screenshot_path = Path(args.image)
        if not screenshot_path.exists():
            print(f"❌ 截图文件不存在: {screenshot_path}")
            sys.exit(1)
        screenshot = Image.open(screenshot_path)
        source = "文件"
    else:
        devices = discover_devices_simple()
        if not devices:
            print("❌ 未发现ADB设备")
            sys.exit(1)
        adb = SimpleAdbController(devices[0])
        screenshot = adb.screenshot()
        if not screenshot:
            print("❌ 截图失败")
            sys.exit(1)
        source = "ADB"

    if args.all:
        available_sets = discover_all_card_sets(
            (script_dir.parent / "data/raw/cards").resolve()
        )
        if not available_sets:
            print("❌ 未发现卡牌系列")
            sys.exit(1)
        hash_db = load_multiple_hash_databases(
            available_sets, (script_dir.parent / "data/raw/cards").resolve()
        )
        hash_db_path = (
            script_dir.parent / "data/raw/cards" / "combined_all_sets"
        ).resolve()
    else:
        cards_dir = (script_dir.parent / "data/raw/cards").resolve()
        hash_db_path = cards_dir / args.set / "hash_database.json"
        hash_db = load_hash_database(hash_db_path)

    run_matching_test_with_db(
        model_path=str(model_path),
        hash_db=hash_db,
        hash_db_path=hash_db_path,
        screenshot=screenshot,
        similarity_threshold=0.75,
        source=source,
        conf_threshold=args.conf,
        pad_square=args.pad_square,
        task=args.task,
        debug_obb=args.debug_obb,
    )


if __name__ == "__main__":
    main()
