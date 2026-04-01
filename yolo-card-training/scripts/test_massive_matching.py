#!/usr/bin/env python3
"""
大规模匹配测试 - 优化版本
扫描当前游戏截图，与数据库匹配，统计相似度 >= 0.75 的卡牌
"""

import heapq
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image

# 全局导入 YOLO（避免每次调用都重新初始化）
try:
    from ultralytics import YOLO  # type: ignore

    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    YOLO = None

# 引入必要的函数
sys.path.insert(0, str(Path(__file__).parent))
from test_yolo_hash_match import (
    SimpleAdbController,
    calculate_perceptual_hash,
    calculate_similarity,
    discover_devices_simple,
    pil_to_color_pixels,
)

# 引入终端预览工具
try:
    from ptcgp_auto_v2.utils.terminal_preview import (
        preview_image_inline,  # type: ignore
    )
except ImportError:

    def preview_image_inline(image, **kwargs):
        return False


def decode_hash_from_base64(encoded: str) -> np.ndarray:
    """解码 base64 字符串为 uint32 数组"""
    import base64

    raw = base64.b64decode(encoded)
    return np.frombuffer(raw, dtype=np.uint32)


@dataclass
class MatchResult:
    """匹配结果"""

    detected_index: int
    card_id: str
    similarity: float
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None


# 配置常量
HASH_SIMILARITY_THRESHOLD = 0.75
HASH_SIMILARITY_GAP_MIN = 0.005
YOLO_OBB_THRESHOLD = 0.55
TOPK_CANDIDATES = 3
SECOND_STAGE_STAGE1_WEIGHT = 0.4
SECOND_STAGE_STAGE2_WEIGHT = 0.6
OBB_INSET_RATIO = 0.04
HASH_CROP_TOP_RATIO = 0.08
HASH_CROP_BOTTOM_RATIO = 0.03
HASH_CROP_SIDE_RATIO = 0.03
DETECT_HASH_VARIANT_TOP_TRIMS = [0.0, 0.04, 0.08, 0.12]
BYPASS_SECOND_STAGE_WHEN_STAGE1_PASS = True


def order_obb_corners(corners: np.ndarray) -> np.ndarray:
    """将 OBB 四点统一为 [左上, 右上, 右下, 左下] 顺序"""
    y_sorted = corners[np.argsort(corners[:, 1])]
    top_two = y_sorted[:2]
    bottom_two = y_sorted[2:]
    top_two = top_two[np.argsort(top_two[:, 0])]
    bottom_two = bottom_two[np.argsort(bottom_two[:, 0])]
    tl, tr = top_two[0], top_two[1]
    bl, br = bottom_two[0], bottom_two[1]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def inset_obb_corners(corners: np.ndarray, ratio: float) -> np.ndarray:
    """按中心点将 OBB 四点向内收缩"""
    center = corners.mean(axis=0)
    return center + (corners - center) * (1.0 - ratio)


def trim_for_hash(
    image_bgr: np.ndarray,
    top_ratio: float = HASH_CROP_TOP_RATIO,
    bottom_ratio: float = HASH_CROP_BOTTOM_RATIO,
    side_ratio: float = HASH_CROP_SIDE_RATIO,
) -> np.ndarray:
    """哈希前对卡图做非对称裁剪"""
    if image_bgr.size == 0:
        return image_bgr
    h, w = image_bgr.shape[:2]
    x1 = int(w * side_ratio)
    x2 = int(w * (1.0 - side_ratio))
    y1 = int(h * top_ratio)
    y2 = int(h * (1.0 - bottom_ratio))
    x1 = max(0, min(x1, w - 1))
    x2 = max(x1 + 1, min(x2, w))
    y1 = max(0, min(y1, h - 1))
    y2 = max(y1 + 1, min(y2, h))
    return image_bgr[y1:y2, x1:x2]


def compute_hash_from_bgr(image_bgr: np.ndarray) -> Optional[np.ndarray]:
    """从 BGR 图像计算感知哈希"""
    if image_bgr.size == 0:
        return None
    pil_img = Image.fromarray(cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB))
    color_pixels = pil_to_color_pixels(pil_img)
    return calculate_perceptual_hash(color_pixels)


def build_detect_hash_variants(image_bgr: np.ndarray) -> List[np.ndarray]:
    """构建检测卡图的多视角哈希"""
    variants: List[np.ndarray] = []
    seen: set[bytes] = set()
    for top_trim in DETECT_HASH_VARIANT_TOP_TRIMS:
        trimmed = trim_for_hash(
            image_bgr,
            top_ratio=top_trim,
            bottom_ratio=HASH_CROP_BOTTOM_RATIO,
            side_ratio=HASH_CROP_SIDE_RATIO,
        )
        hash_arr = compute_hash_from_bgr(trimmed)
        if hash_arr is None:
            continue
        key = hash_arr.tobytes()
        if key in seen:
            continue
        seen.add(key)
        variants.append(hash_arr)
    return variants


def load_hash_database(db_path: Path) -> Dict[str, np.ndarray]:
    """加载哈希数据库"""
    print(f"📂 加载哈希数据库: {db_path}")
    with open(db_path, "r", encoding="utf-8") as f:
        db_raw = json.load(f)
    db_decoded: Dict[str, np.ndarray] = {}
    for hash_str, card_id in db_raw.items():
        hash_arr = decode_hash_from_base64(hash_str)
        db_decoded[card_id] = hash_arr
    print(f"✅ 已加载 {len(db_decoded)} 张卡牌")
    return db_decoded


def detect_cards(
    model_path: str, pil_image: Image.Image, conf_threshold: float = YOLO_OBB_THRESHOLD
):
    """YOLO 检测卡牌"""
    if not ULTRALYTICS_AVAILABLE or YOLO is None:
        raise ImportError("ultralytics not installed")

    model = YOLO(model_path, task="obb")

    img_array = np.array(pil_image)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    vis_img = img_bgr.copy()

    results = model(img_bgr, verbose=False)
    result = results[0]

    if result.obb is None or len(result.obb) == 0:
        return [], img_bgr, vis_img

    cropped_cards = []
    for i, obb in enumerate(result.obb):
        conf = float(obb.conf[0].item())
        if conf < conf_threshold:
            continue

        # 优先使用矩形框裁剪（YOLO已经过NMS，重复少）
        if hasattr(obb, "xyxy") and obb.xyxy is not None:
            x1, y1, x2, y2 = map(int, obb.xyxy[0])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
            cropped = img_bgr[y1:y2, x1:x2]
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
        elif hasattr(obb, "xyxyxyxy") and obb.xyxyxyxy is not None:
            # 备用：使用旋转框透视变换
            xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
            corners = order_obb_corners(xyxyxyxy.astype(np.float32))
            corners = inset_obb_corners(corners, OBB_INSET_RATIO)
            target_w, target_h = 480, 670
            dst = np.array(
                [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
                dtype=np.float32,
            )
            matrix = cv2.getPerspectiveTransform(corners, dst)
            cropped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))
            center_x = corners[:, 0].mean()
            center_y = corners[:, 1].mean()
            x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
            x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())
        else:
            continue

        if hasattr(obb, "xyxyxyxy") and obb.xyxyxyxy is not None:
            xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
            corners = order_obb_corners(xyxyxyxy.astype(np.float32))
            corners = inset_obb_corners(corners, OBB_INSET_RATIO)
            target_w, target_h = 480, 670
            dst = np.array(
                [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
                dtype=np.float32,
            )
            matrix = cv2.getPerspectiveTransform(corners, dst)
            cropped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))
            center_x = corners[:, 0].mean()
            center_y = corners[:, 1].mean()
            x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
            x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())
        elif hasattr(obb, "xyxy") and obb.xyxy is not None:
            x1, y1, x2, y2 = map(int, obb.xyxy[0])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
            cropped = img_bgr[y1:y2, x1:x2]
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
        else:
            continue

        if cropped.size == 0:
            continue

        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        conf_text = f"{conf:.2f}"
        text_y = y1 - 5 if y1 > 20 else y1 + 20
        cv2.putText(
            vis_img,
            conf_text,
            (x1, text_y),
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

    return cropped_cards, img_bgr, vis_img


def match_against_database(
    cropped_cards: List[Dict],
    hash_db: Dict[str, np.ndarray],
    vis_img: np.ndarray,
    similarity_threshold: float = HASH_SIMILARITY_THRESHOLD,
) -> Tuple[List[MatchResult], int, int, np.ndarray]:
    """将检测到的卡牌与数据库匹配"""
    matches: List[MatchResult] = []
    total_checked = len(cropped_cards) * len(hash_db)
    above_threshold_count = 0

    print(f"\n🔍 开始匹配 ({len(cropped_cards)} 张检测 × {len(hash_db)} 张数据库)")
    print(f"   阈值: {HASH_SIMILARITY_THRESHOLD}, 最小差值: {HASH_SIMILARITY_GAP_MIN}")
    print("-" * 70)

    for card in cropped_cards:
        base_hash = compute_hash_from_bgr(card["cropped"])
        if base_hash is None:
            continue

        detect_hash_variants = build_detect_hash_variants(card["cropped"])
        if not detect_hash_variants:
            detect_hash_variants = [base_hash]

        # 使用 heapq.nlargest 优化性能 (O(N log K) vs O(N log N))
        all_similarities = (
            (card_id, calculate_similarity(base_hash, db_hash))
            for card_id, db_hash in hash_db.items()
        )
        topk_stage1 = heapq.nlargest(
            TOPK_CANDIDATES, all_similarities, key=lambda x: x[1]
        )
        above_threshold_count += sum(
            1 for _, sim in topk_stage1 if sim >= similarity_threshold
        )

        # 快速路径
        if BYPASS_SECOND_STAGE_WHEN_STAGE1_PASS and topk_stage1:
            stage1_best_score = topk_stage1[0][1]
            if stage1_best_score >= similarity_threshold:
                reranked = [(cid, s1, s1, s1) for cid, s1 in topk_stage1]
                top3 = reranked[:3]
            else:
                top3 = []
        else:
            top3 = []

        # 二阶段
        if not top3:
            reranked = []
            for candidate_id, stage1_score in topk_stage1:
                candidate_hash = hash_db[candidate_id]
                stage2_score = max(
                    calculate_similarity(variant_hash, candidate_hash)
                    for variant_hash in detect_hash_variants
                )
                final_score = (
                    SECOND_STAGE_STAGE1_WEIGHT * stage1_score
                    + SECOND_STAGE_STAGE2_WEIGHT * stage2_score
                )
                reranked.append((candidate_id, final_score, stage1_score, stage2_score))
            reranked.sort(key=lambda x: x[1], reverse=True)
            top3 = reranked[:3]

        if not top3:
            print(f"   卡牌 #{card['index']}: ❌ 无匹配")
            continue

        best_id, best_score, _, _ = top3[0]
        second_score = top3[1][1] if len(top3) > 1 else 0.0
        similarity_gap = best_score - second_score

        status = "✅" if best_score >= similarity_threshold else "❌"
        x1, y1, x2, y2 = card["bbox"]
        print(
            f"   卡牌 #{card['index']}: {status} 最佳匹配: {best_id} "
            f"(相似度: {best_score:.4f}, 边框置信度: {card['confidence']:.3f}, "
            f"候选差值: {similarity_gap:.4f})"
        )

        for i, (cid, final_score, stage1_score, stage2_score) in enumerate(top3, 1):
            mark = "👑" if final_score >= similarity_threshold else "  "
            print(
                f"      {mark} 候选{i}: {cid} = {final_score:.4f} "
                f"(stage1={stage1_score:.4f}, stage2={stage2_score:.4f})"
            )

        if (
            best_score >= similarity_threshold
            and similarity_gap >= HASH_SIMILARITY_GAP_MIN
        ):
            matches.append(
                MatchResult(
                    detected_index=card["index"],
                    card_id=best_id,
                    similarity=best_score,
                    confidence=card["confidence"],
                    bbox=card["bbox"],
                )
            )

            # 绘制红色内框
            inner_x1, inner_y1 = x1 + 5, y1 + 5
            inner_x2, inner_y2 = x2 - 5, y2 - 5
            cv2.rectangle(
                vis_img, (inner_x1, inner_y1), (inner_x2, inner_y2), (0, 0, 255), 2
            )

            text_size = cv2.getTextSize(best_id, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            text_x = (inner_x1 + inner_x2 - text_size[0]) // 2
            text_y = (inner_y1 + inner_y2 + text_size[1]) // 2
            cv2.putText(
                vis_img,
                best_id,
                (text_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )
        elif best_score >= similarity_threshold:
            print(
                f"      ⚠️ 差值不足，放弃匹配: gap={similarity_gap:.4f} < {HASH_SIMILARITY_GAP_MIN:.4f}"
            )

    return matches, total_checked, above_threshold_count, vis_img


def run_matching_test_with_db(
    model_path: str,
    hash_db: Dict[str, np.ndarray],
    hash_db_path: Path,
    screenshot: Image.Image,
    similarity_threshold: float = HASH_SIMILARITY_THRESHOLD,
    source: str = "ADB",
    conf_threshold: float = 0.9,
):
    """核心匹配测试逻辑"""
    print("=" * 70)
    print(f"大规模匹配测试（{source} 模式）")
    print("=" * 70)
    print(f"📂 使用数据库: {hash_db_path}")
    print(f"   已加载 {len(hash_db)} 张卡牌")
    print(f"\n✅ 截图: {screenshot.width}x{screenshot.height}")

    # YOLO 检测
    print(f"\n🚀 加载模型并检测: {model_path}")
    print(f"   置信度阈值: {conf_threshold}")
    start_time = time.perf_counter()
    cropped_cards, _, vis_img = detect_cards(
        model_path, screenshot, conf_threshold=conf_threshold
    )
    detect_time = time.perf_counter() - start_time

    if not cropped_cards:
        print(f"❌ 未检测到任何卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")
        return

    print(
        f"✅ 检测到 {len(cropped_cards)} 张卡牌 (检测耗时: {detect_time * 1000:.1f}ms)"
    )

    # 按阅读顺序排序
    start_time = time.perf_counter()
    cropped_cards.sort(key=lambda c: (c["center_y"], c["center_x"]))
    for i, card in enumerate(cropped_cards, 1):
        card["index"] = i
    sort_time = time.perf_counter() - start_time
    print(f"   已排序 (排序耗时: {sort_time * 1000:.1f}ms)")

    # 匹配
    matches, total_checked, above_threshold, vis_img = match_against_database(
        cropped_cards, hash_db, vis_img, similarity_threshold
    )

    # 结果汇总
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
        print("\n   ✅ 匹配详情:")
        avg_sim = sum(m.similarity for m in matches) / len(matches)
        print(f"      平均相似度: {avg_sim:.4f}")
        sorted_matches = sorted(matches, key=lambda x: x.similarity, reverse=True)
        for i, m in enumerate(sorted_matches[:10], 1):
            print(
                f"      {i}. {m.card_id}: {m.similarity:.4f} (检测# {m.detected_index})"
            )
        if len(sorted_matches) > 10:
            print(f"      ... 还有 {len(sorted_matches) - 10} 张")

    matched_indices = {m.detected_index for m in matches}
    unmatched = [c for c in cropped_cards if c["index"] not in matched_indices]
    if unmatched:
        print(f"\n   ⚠️  未匹配的卡牌 ({len(unmatched)} 张):")
        for c in unmatched:
            x1, y1, x2, y2 = c["bbox"]
            print(
                f"      卡牌 #{c['index']}: 边框置信度 {c['confidence']:.3f}, 坐标: ({x1},{y1},{x2},{y2})"
            )

    print("\n" + "=" * 70)
    print("结论:")
    if len(matches) >= len(cropped_cards) * 0.8:
        print("   🎉 表现优秀！建议使用当前模型")
    elif len(matches) >= len(cropped_cards) * 0.5:
        print("   ⚠️  表现一般，建议检查图片质量或调整阈值")
    else:
        print("   ❌ 表现不佳，可能需要优化模型或数据库")
    print("=" * 70)

    # 保存可视化
    print("\n📸 生成检测结果可视化...")
    vis_path = Path("output/detection_result.jpg")
    vis_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(vis_path), vis_img)
    print(f"   💾 已保存到: {vis_path}")

    time.sleep(0.1)
    if preview_image_inline(vis_path):
        print("✅ 可视化已显示在终端")
    else:
        print(f"⚠️  终端显示失败，请直接查看文件: {vis_path}")


def discover_all_card_sets(cards_dir: Path) -> List[str]:
    """发现所有可用的卡牌系列"""
    sets = []
    if not cards_dir.exists():
        return sets
    for subdir in sorted(cards_dir.iterdir()):
        if subdir.is_dir() and (subdir / "hash_database.json").exists():
            sets.append(subdir.name)
    return sets


def load_multiple_hash_databases(
    sets: List[str], cards_dir: Path
) -> Dict[str, np.ndarray]:
    """加载多个系列的哈希数据库并合并"""
    combined_db: Dict[str, np.ndarray] = {}
    print(f"\n📂 加载 {len(sets)} 个系列的哈希数据库...")
    for card_set in sets:
        db_path = cards_dir / card_set / "hash_database.json"
        if not db_path.exists():
            print(f"   ⚠️  跳过 {card_set}: 数据库不存在")
            continue
        with open(db_path, "r", encoding="utf-8") as f:
            db_raw = json.load(f)
        for hash_str, card_id in db_raw.items():
            prefixed_id = f"{card_set}/{card_id}"
            combined_db[prefixed_id] = decode_hash_from_base64(hash_str)
        print(f"   ✅ {card_set}: {len(db_raw)} 张卡牌")
    print(f"\n📊 总计加载: {len(combined_db)} 张卡牌")
    return combined_db


def list_available_models(models_dir: Path) -> None:
    """列出 data/models 下可用模型"""
    print(f"📂 扫描模型目录: {models_dir}")
    if not models_dir.exists():
        print("❌ 模型目录不存在")
        return
    model_dirs = sorted(
        [d for d in models_dir.iterdir() if d.is_dir()], key=lambda d: d.name
    )
    if not model_dirs:
        print("⚠️  未发现任何模型目录")
        return
    found = 0
    for model_dir in model_dirs:
        pt_path = model_dir / "best.pt"
        mlpackage_path = model_dir / "best.mlpackage"
        has_pt = pt_path.exists()
        has_mlpackage = mlpackage_path.exists()
        if not has_pt and not has_mlpackage:
            continue
        found += 1
        print(f"\n- {model_dir.name}")
        if has_pt:
            print(f"  PT:      {pt_path}")
        if has_mlpackage:
            print(f"  CoreML:  {mlpackage_path}")
    if found == 0:
        print("⚠️  未发现可用模型文件")
    else:
        print(f"\n✅ 共发现 {found} 个可用模型目录")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="大规模匹配测试")
    parser.add_argument("--set", default="A1", help="要匹配的卡牌系列，默认 A1")
    parser.add_argument("--all", action="store_true", help="匹配所有可用的卡牌系列")
    parser.add_argument("--image", help="从指定图片文件加载截图（不使用 ADB）")
    parser.add_argument(
        "--conf", type=float, default=YOLO_OBB_THRESHOLD, help="YOLO 检测置信度阈值"
    )
    parser.add_argument("--coreml", action="store_true", help="使用 CoreML 模型")
    parser.add_argument("--model", help="手动指定模型路径")
    parser.add_argument("--list-models", action="store_true", help="列出可用模型并退出")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    models_dir = (repo_root / "data/models").resolve()

    if args.list_models:
        list_available_models(models_dir)
        return

    if args.model:
        model_path = Path(args.model).expanduser().resolve()
    elif args.coreml:
        model_path = (
            repo_root / "data/models/yolo26n-10k-50-2026.02.06/best.mlpackage"
        ).resolve()
    else:
        model_path = (
            repo_root / "data/models/yolo26n-10k-50-2026.02.06/best.pt"
        ).resolve()

    cards_dir = (script_dir.parent / "data/raw/cards").resolve()

    if not model_path.exists():
        print(f"❌ 模型不存在: {model_path}")
        sys.exit(1)

    if args.image:
        screenshot_path = Path(args.image)
        if not screenshot_path.exists():
            print(f"❌ 截图文件不存在: {screenshot_path}")
            sys.exit(1)
        print(f"📂 加载截图: {screenshot_path}")
        screenshot = Image.open(screenshot_path)
        source = "文件"
    else:
        print("🔍 自动发现ADB设备...")
        devices = discover_devices_simple()
        if not devices:
            print("❌ 未发现ADB设备")
            sys.exit(1)
        device_address = devices[0]
        print(f"✅ 发现设备: {device_address}")
        adb = SimpleAdbController(device_address)
        print(f"\n📱 连接设备: {device_address}")
        print("📸 正在截图...")
        screenshot = adb.screenshot()
        if not screenshot:
            print("❌ 截图失败")
            sys.exit(1)
        source = "ADB"

    if args.all:
        available_sets = discover_all_card_sets(cards_dir)
        if not available_sets:
            print(f"❌ 未在 {cards_dir} 下发现任何卡牌系列")
            sys.exit(1)
        print(
            f"\n🔍 发现 {len(available_sets)} 个卡牌系列: {', '.join(available_sets)}"
        )
        hash_db = load_multiple_hash_databases(available_sets, cards_dir)
        hash_db_path = cards_dir / "combined_all_sets"
    else:
        hash_db_path = cards_dir / args.set / "hash_database.json"
        print(f"📂 使用系列: {args.set}")
        if not hash_db_path.exists():
            print("⚠️  哈希数据库不存在，尝试自动生成...")
            result = subprocess.run(
                [sys.executable, "scripts/generate_hash_db.py", "--set", args.set],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                print(f"❌ 生成失败: {result.stderr}")
                sys.exit(1)
        hash_db = load_hash_database(hash_db_path)

    run_matching_test_with_db(
        model_path=str(model_path),
        hash_db=hash_db,
        hash_db_path=hash_db_path,
        screenshot=screenshot,
        similarity_threshold=HASH_SIMILARITY_THRESHOLD,
        source=source,
        conf_threshold=args.conf,
    )


if __name__ == "__main__":
    main()
