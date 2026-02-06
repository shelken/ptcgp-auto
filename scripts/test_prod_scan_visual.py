# -*- coding: utf-8 -*-
"""
正式识别流程可视化输出（对齐 test_massive_matching.py 格式）

示例：
PYTHONPATH=src python scripts/test_prod_scan_visual.py --adb 127.0.0.1:5775 --out output/prod_detection.jpg
"""

import argparse
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    DETECT_HASH_VARIANT_TOP_TRIMS,
    HASH_CROP_BOTTOM_RATIO,
    HASH_CROP_SIDE_RATIO,
    HASH_SIMILARITY_GAP_MIN,
    HASH_SIMILARITY_THRESHOLD,
    SECOND_STAGE_STAGE1_WEIGHT,
    SECOND_STAGE_STAGE2_WEIGHT,
    TOPK_CANDIDATES,
    YOLO_OBB_THRESHOLD,
)
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.utils.perceptual_hash import (
    bgr_to_color_pixels,
    calculate_perceptual_hash,
    calculate_similarity,
)

# 引入终端预览工具
try:
    from ptcgp_auto_v2.utils.terminal_preview import preview_image_inline
except ImportError:

    def preview_image_inline(image, **kwargs):
        return False


def build_detect_hash_variants(image_bgr: np.ndarray) -> List[np.ndarray]:
    """构建检测卡图的多视角哈希"""
    from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer

    variants: List[np.ndarray] = []
    seen: set[bytes] = set()
    for top_trim in DETECT_HASH_VARIANT_TOP_TRIMS:
        trimmed = YoloCardRecognizer._trim_for_hash(
            image_bgr,
            top_ratio=top_trim,
            bottom_ratio=HASH_CROP_BOTTOM_RATIO,
            side_ratio=HASH_CROP_SIDE_RATIO,
        )
        color_pixels = bgr_to_color_pixels(trimmed)
        hash_arr = calculate_perceptual_hash(color_pixels)
        if hash_arr is None:
            continue
        key = hash_arr.tobytes()
        if key in seen:
            continue
        seen.add(key)
        variants.append(hash_arr)
    return variants


def compute_hash_from_bgr(image_bgr: np.ndarray):
    """从 BGR 图像计算感知哈希"""
    color_pixels = bgr_to_color_pixels(image_bgr)
    return calculate_perceptual_hash(color_pixels)


def match_with_visualization(
    recognizer: YoloCardRecognizer,
    hash_manager: CardHashManager,
    set_code: str,
    screenshot: Image.Image,
    similarity_threshold: float = HASH_SIMILARITY_THRESHOLD,
) -> Tuple[List[dict], int, np.ndarray]:
    """
    执行匹配并返回详细信息（对齐 test_massive_matching.py 格式）

    Returns:
        (matches, total_detected, vis_img)
    """
    print("=" * 70)
    print("正式识别流程可视化输出")
    print("=" * 70)

    # 截图信息
    print(f"\n✅ 截图: {screenshot.width}x{screenshot.height}")

    # YOLO检测
    print(f"\n🚀 开始YOLO检测")
    print(f"   置信度阈值: {YOLO_OBB_THRESHOLD}")
    start_time = time.perf_counter()
    detected = recognizer._detect_cards(screenshot, YOLO_OBB_THRESHOLD)
    detect_time = time.perf_counter() - start_time

    # 准备图像用于可视化
    img_array = np.array(screenshot)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    vis_img = img_bgr.copy()

    if not detected:
        print(f"❌ 未检测到任何卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")
        return [], 0, vis_img

    print(f"✅ 检测到 {len(detected)} 张卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")

    # 按阅读顺序排序
    start_time = time.perf_counter()
    detected.sort(key=lambda c: (c.center[1], c.center[0]))
    for i, card in enumerate(detected, 1):
        card.index = i
    sort_time = time.perf_counter() - start_time
    print(f"   已排序 (排序耗时: {sort_time * 1000:.1f}ms)")

    # 匹配
    print(f"\n🔍 开始匹配 ({len(detected)} 张检测)")
    print(f"   阈值: {similarity_threshold}, 最小差值: {HASH_SIMILARITY_GAP_MIN}")
    print("-" * 70)

    matches = []
    total_checked = 0
    above_threshold_count = 0

    start_time = time.perf_counter()

    for card in detected:
        # 绘制绿色外框（所有检测到的卡）
        x1, y1, x2, y2 = card.bbox
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        conf_text = f"{card.confidence:.2f}"
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

        # 计算基础哈希
        base_hash = compute_hash_from_bgr(card.cropped)
        if base_hash is None:
            print(f"   卡牌 #{card.index}: ❌ 哈希计算失败")
            continue

        # 获取TopK候选
        topk = hash_manager.find_topk_candidates(base_hash, set_code, TOPK_CANDIDATES)
        total_checked += len(topk)

        if not topk:
            print(f"   卡牌 #{card.index}: ❌ 无候选")
            continue

        # 检查是否通过阈值
        stage1_best = topk[0][2]
        bypass_stage2 = stage1_best >= similarity_threshold
        above_threshold_count += sum(
            1 for _, _, sim, _ in topk if sim >= similarity_threshold
        )

        # 构建候选列表（统一格式）
        top3 = []
        if bypass_stage2:
            # 快速路径：stage1直接通过
            for sc, num, stage1_score, _ in topk[:3]:
                top3.append((sc, num, stage1_score, stage1_score, stage1_score))
        else:
            # 第二阶段：多视角哈希重排序
            variants = build_detect_hash_variants(card.cropped)
            if not variants:
                variants = [base_hash]

            reranked = []
            for sc, num, stage1_score, db_hash in topk:
                stage2_score = max(calculate_similarity(v, db_hash) for v in variants)
                final_score = (
                    SECOND_STAGE_STAGE1_WEIGHT * stage1_score
                    + SECOND_STAGE_STAGE2_WEIGHT * stage2_score
                )
                reranked.append((sc, num, final_score, stage1_score, stage2_score))
            reranked.sort(key=lambda x: x[2], reverse=True)
            top3 = reranked[:3]

        if not top3:
            print(f"   卡牌 #{card.index}: ❌ 无匹配")
            continue

        best_sc, best_num, best_score, s1, s2 = top3[0]
        second_score = top3[1][2] if len(top3) > 1 else 0.0
        gap = best_score - second_score

        card_id = f"{best_sc}/{best_num:03d}"
        is_match = best_score >= similarity_threshold and gap >= HASH_SIMILARITY_GAP_MIN
        status = "✅" if is_match else "❌"

        # 输出匹配信息（对齐 test_massive_matching.py 格式）
        print(
            f"   卡牌 #{card.index}: {status} 最佳匹配: {card_id} "
            f"(相似度: {best_score:.4f}, 边框置信度: {card.confidence:.3f}, 候选差值: {gap:.4f})"
        )

        # 输出Top-3候选
        for i, (sc, num, final_score, stage1_score, stage2_score) in enumerate(top3, 1):
            mark = "👑" if final_score >= similarity_threshold else "  "
            cid = f"{sc}/{num:03d}"
            if bypass_stage2:
                print(
                    f"      {mark} 候选{i}: {cid} = {final_score:.4f} (stage1直接通过)"
                )
            else:
                print(
                    f"      {mark} 候选{i}: {cid} = {final_score:.4f} (stage1={stage1_score:.4f}, stage2={stage2_score:.4f})"
                )

        # 检查差距
        if best_score >= similarity_threshold and gap < HASH_SIMILARITY_GAP_MIN:
            print(
                f"      ⚠️ 差值不足，放弃匹配: gap={gap:.4f} < {HASH_SIMILARITY_GAP_MIN:.4f}"
            )

        if is_match:
            matches.append(
                {
                    "index": card.index,
                    "card_id": card_id,
                    "set_code": best_sc,
                    "card_number": best_num,
                    "similarity": best_score,
                    "confidence": card.confidence,
                    "gap": gap,
                    "bbox": card.bbox,
                }
            )

            # 绘制红色内框
            inner_x1, inner_y1 = x1 + 5, y1 + 5
            inner_x2, inner_y2 = x2 - 5, y2 - 5
            cv2.rectangle(
                vis_img, (inner_x1, inner_y1), (inner_x2, inner_y2), (0, 0, 255), 2
            )

            # 卡牌ID标签居中
            text_size = cv2.getTextSize(card_id, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
            text_x = (inner_x1 + inner_x2 - text_size[0]) // 2
            text_y_center = (inner_y1 + inner_y2 + text_size[1]) // 2
            cv2.putText(
                vis_img,
                card_id,
                (text_x, text_y_center),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

    elapsed = time.perf_counter() - start_time

    # 结果汇总（对齐 test_massive_matching.py 格式）
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"   检测到的卡牌: {len(detected)} 张")
    print(f"   总比对次数: {total_checked:,} 次")
    print(f"   阈值以上次数: {above_threshold_count} 次")
    print(f"   成功匹配: {len(matches)} 张")
    print(f"   匹配率: {len(matches) / len(detected) * 100:.1f}%")

    if matches:
        print(f"\n   ✅ 匹配详情:")
        avg_sim = sum(m["similarity"] for m in matches) / len(matches)
        print(f"      平均相似度: {avg_sim:.4f}")
        sorted_matches = sorted(matches, key=lambda x: x["similarity"], reverse=True)
        for i, m in enumerate(sorted_matches[:10], 1):
            print(
                f"      {i}. {m['card_id']}: {m['similarity']:.4f} (检测# {m['index']})"
            )
        if len(sorted_matches) > 10:
            print(f"      ... 还有 {len(sorted_matches) - 10} 张")

    matched_indices = {m["index"] for m in matches}
    unmatched = [c for c in detected if c.index not in matched_indices]
    if unmatched:
        print(f"\n   ⚠️  未匹配的卡牌 ({len(unmatched)} 张):")
        for c in unmatched:
            x1, y1, x2, y2 = c.bbox
            print(
                f"      卡牌 #{c.index}: 边框置信度 {c.confidence:.3f}, 坐标: ({x1},{y1},{x2},{y2})"
            )

    print("\n" + "=" * 70)
    print("结论:")
    if len(matches) >= len(detected) * 0.8:
        print("   🎉 表现优秀！建议使用当前模型")
    elif len(matches) >= len(detected) * 0.5:
        print("   ⚠️  表现一般，建议检查图片质量或调整阈值")
    else:
        print("   ❌ 表现不佳，可能需要优化模型或数据库")
    print("=" * 70)

    return matches, len(detected), vis_img


def main() -> None:
    parser = argparse.ArgumentParser(
        description="正式识别流程可视化输出（对齐 test_massive_matching.py 格式）"
    )
    parser.add_argument("--adb", required=True, help="ADB 设备地址")
    parser.add_argument(
        "--out", default="output/prod_detection.jpg", help="输出图片路径"
    )
    parser.add_argument(
        "--conf", type=float, default=YOLO_OBB_THRESHOLD, help="YOLO 置信度阈值"
    )
    parser.add_argument("--set", default=None, help="指定系列代码，默认全局匹配")
    parser.add_argument("--detect-only", action="store_true", help="仅检测不匹配")
    args = parser.parse_args()

    # 连接设备
    print("🔍 连接ADB设备...")
    adb = AdbController(args.adb)
    if not adb.connect():
        print(f"❌ 无法连接设备: {args.adb}")
        return
    print(f"✅ 已连接设备: {args.adb}")

    # 截图
    print("\n📸 正在截图...")
    screenshot = adb.screenshot()
    if not screenshot:
        print("❌ 截图失败")
        return
    print(f"✅ 截图成功: {screenshot.width}x{screenshot.height}")

    # 加载模型
    print("\n🚀 加载YOLO模型...")
    model_manager = get_model_manager()
    model_manager.load_model_async()
    if not model_manager.wait_for_model(timeout=120):
        print("❌ 模型加载超时")
        return
    print("✅ 模型加载完成")

    # 准备Hash管理器（禁用自动下载）
    hash_manager = CardHashManager(enable_download=False)
    if args.set:
        print(f"\n📂 准备系列: {args.set}")
        hash_manager.ensure_series_ready(args.set)
    else:
        print("\n📂 加载全局Hash索引...")
        hash_manager.load_all_hashes()

    # 创建识别器
    recognizer = YoloCardRecognizer(
        adb=adb, model_manager=model_manager, hash_manager=hash_manager
    )

    # 执行匹配
    matches, total, vis_img = match_with_visualization(
        recognizer, hash_manager, args.set, screenshot, HASH_SIMILARITY_THRESHOLD
    )

    # 保存可视化
    print(f"\n📸 生成检测结果可视化...")
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), vis_img)
    print(f"   💾 已保存到: {out_path}")

    # 终端预览
    time.sleep(0.1)
    if preview_image_inline(out_path):
        print(f"✅ 可视化已显示在终端")
    else:
        print(f"⚠️  终端显示失败，请直接查看文件: {out_path}")


if __name__ == "__main__":
    main()
