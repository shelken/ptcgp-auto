# -*- coding: utf-8 -*-
"""
正式识别流程可视化输出（对齐 test_massive_matching.py 格式）

示例：
PYTHONPATH=src python scripts/test_prod_scan_visual.py --adb 127.0.0.1:5775
"""

import argparse
import time
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

from ptcgp_auto_v2.config.constants import (
    HASH_SIMILARITY_GAP_MIN,
    HASH_SIMILARITY_THRESHOLD,
    YOLO_OBB_THRESHOLD,
)
from ptcgp_auto_v2.infra.adb import AdbController
from ptcgp_auto_v2.infra.card_hash_manager import get_card_hash_manager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer

# 引入终端预览工具
try:
    from ptcgp_auto_v2.utils.terminal_preview import preview_image_inline
except ImportError:

    def preview_image_inline(image, **kwargs):
        return False


def _run_formal_scan_with_screenshot(
    recognizer: YoloCardRecognizer,
    set_code: str | None,
    screenshot: Image.Image,
    obb_threshold: float,
    similarity_threshold: float,
    exclude_promo: bool,
):
    """复用正式 scan 内部流程，并固定为当前截图。"""
    original_screenshot = recognizer.adb.screenshot
    recognizer.adb.screenshot = lambda: screenshot
    try:
        return recognizer._scan_common(
            set_code=set_code,
            obb_threshold=obb_threshold,
            similarity_threshold=similarity_threshold,
            exclude_promo=exclude_promo,
        )
    finally:
        recognizer.adb.screenshot = original_screenshot


def match_with_visualization(
    recognizer: YoloCardRecognizer,
    set_code: str | None,
    screenshot: Image.Image,
    obb_threshold: float = YOLO_OBB_THRESHOLD,
    similarity_threshold: float = HASH_SIMILARITY_THRESHOLD,
    exclude_promo: bool = False,
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

    # 正式识别流程
    print("\n🚀 开始正式识别流程")
    print(f"   YOLO置信度阈值: {obb_threshold}")
    start_time = time.perf_counter()
    matched, total_detected, unmatched = _run_formal_scan_with_screenshot(
        recognizer=recognizer,
        set_code=set_code,
        screenshot=screenshot,
        obb_threshold=obb_threshold,
        similarity_threshold=similarity_threshold,
        exclude_promo=exclude_promo,
    )
    detect_time = time.perf_counter() - start_time

    # 准备图像用于可视化
    img_array = np.array(screenshot)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    vis_img = img_bgr.copy()

    if total_detected == 0:
        print(f"❌ 未检测到任何卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")
        return [], 0, vis_img

    print(f"✅ 检测到 {total_detected} 张卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")

    # 匹配
    print(f"\n🔍 正式结果 ({total_detected} 张检测)")
    print(f"   阈值: {similarity_threshold}, 最小差值: {HASH_SIMILARITY_GAP_MIN}")
    print("-" * 70)

    matches = []
    all_cards = recognizer._sort_by_reading_order(list(matched) + list(unmatched))
    for index, card in enumerate(all_cards, 1):
        x1, y1, x2, y2 = card.bbox
        center_x = int(card.center[0])
        center_y = int(card.center[1])
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)
        conf_text = f"P{index} {card.confidence:.2f}"
        text_y = y1 - 8 if y1 > 24 else y1 + 24
        cv2.putText(
            vis_img,
            conf_text,
            (x1, text_y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )

        card_id = f"{card.set_code}/{card.card_number:03d}"
        is_match = card in matched
        status = "✅" if is_match else "❌"
        note = f" {card.match_note}" if card.match_note else ""
        print(
            f"   位置#{index}: {status} 最佳匹配: {card_id} "
            f"(相似度: {card.similarity:.4f}, 边框置信度: {card.confidence:.3f}, 中心=({center_x},{center_y}), "
            f"边框=({x1},{y1},{x2},{y2}), 阶段: {card.match_stage}{note})"
        )

        if is_match:
            matches.append(
                {
                    "index": index,
                    "card_id": card_id,
                    "set_code": card.set_code,
                    "card_number": card.card_number,
                    "similarity": card.similarity,
                    "confidence": card.confidence,
                    "gap": None,
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
            label_text = f"P{index} {card_id}"
            text_size = cv2.getTextSize(
                label_text,
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                2,
            )[0]
            text_x = (inner_x1 + inner_x2 - text_size[0]) // 2
            text_y_center = (inner_y1 + inner_y2 + text_size[1]) // 2
            cv2.putText(
                vis_img,
                label_text,
                (text_x, text_y_center),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2,
            )

    # 结果汇总（对齐 test_massive_matching.py 格式）
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    print(f"   检测到的卡牌: {total_detected} 张")
    print(f"   成功匹配: {len(matched)} 张")
    print(f"   未匹配: {len(unmatched)} 张")
    print(f"   匹配率: {len(matches) / total_detected * 100:.1f}%")

    if matches:
        print("\n   ✅ 匹配详情:")
        avg_sim = sum(m["similarity"] for m in matches) / len(matches)
        print(f"      平均相似度: {avg_sim:.4f}")
        sorted_matches = sorted(matches, key=lambda x: x["similarity"], reverse=True)
        for i, m in enumerate(sorted_matches[:10], 1):
            print(
                f"      {i}. {m['card_id']}: {m['similarity']:.4f} (检测# {m['index']})"
            )
        if len(sorted_matches) > 10:
            print(f"      ... 还有 {len(sorted_matches) - 10} 张")

    if unmatched:
        print(f"\n   ⚠️  未匹配的卡牌 ({len(unmatched)} 张):")
        sorted_unmatched = recognizer._sort_by_reading_order(list(unmatched))
        for c in sorted_unmatched:
            x1, y1, x2, y2 = c.bbox
            print(
                f"      {c.set_code}/{c.card_number:03d}: conf={c.confidence:.3f}, sim={c.similarity:.4f}, 中心=({int(c.center[0])},{int(c.center[1])}), 边框=({x1},{y1},{x2},{y2}), 阶段={c.match_stage}"
            )

    print("\n" + "=" * 70)
    print("结论:")
    if len(matches) >= total_detected * 0.8:
        print("   🎉 表现优秀！建议使用当前模型")
    elif len(matches) >= total_detected * 0.5:
        print("   ⚠️  表现一般，建议检查图片质量或调整阈值")
    else:
        print("   ❌ 表现不佳，可能需要优化模型或数据库")
    print("=" * 70)

    return matches, total_detected, vis_img


def main() -> None:
    parser = argparse.ArgumentParser(
        description="正式识别流程可视化输出（对齐正式 scan 流程）"
    )
    parser.add_argument("--adb", required=True, help="ADB 设备地址")
    parser.add_argument("--out", default=None, help="可选：输出图片路径")
    parser.add_argument(
        "--conf", type=float, default=YOLO_OBB_THRESHOLD, help="YOLO 置信度阈值"
    )
    parser.add_argument("--set", default=None, help="指定系列代码；默认全局匹配")
    parser.add_argument(
        "--exclude-promo",
        action="store_true",
        help="全局匹配时排除 PROMO 系列，避免下载不存在的 PROMO 资源",
    )
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

    # 准备Hash管理器（与正式任务对齐，允许补齐缺失Hash）
    hash_manager = get_card_hash_manager()
    if args.set:
        print(f"\n📂 准备系列: {args.set}")
        hash_manager.ensure_series_ready(args.set, exclude_promo=args.exclude_promo)
    else:
        print("\n📂 加载全局Hash索引...")
        hash_manager.load_all_hashes(exclude_promo=args.exclude_promo)

    # 创建识别器
    recognizer = YoloCardRecognizer(
        adb=adb, model_manager=model_manager, hash_manager=hash_manager
    )

    # 执行匹配
    matches, total, vis_img = match_with_visualization(
        recognizer,
        args.set,
        screenshot,
        obb_threshold=args.conf,
        similarity_threshold=HASH_SIMILARITY_THRESHOLD,
        exclude_promo=args.exclude_promo,
    )

    if args.out:
        print("\n📸 生成检测结果可视化...")
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(out_path), vis_img)
        print(f"   💾 已保存到: {out_path}")

        time.sleep(0.1)
        if preview_image_inline(out_path):
            print("✅ 可视化已显示在终端")
        else:
            print(f"⚠️  终端显示失败，请直接查看文件: {out_path}")


if __name__ == "__main__":
    main()
