#!/usr/bin/env python3
"""
大规模匹配测试
扫描当前游戏截图，与 A1 数据库匹配，统计相似度 >= 0.8 的卡牌
"""

import io
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
    from ultralytics import YOLO

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
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
try:
    from ptcgp_auto_v2.utils.terminal_preview import preview_image_inline
except ImportError:
    # 如果导入失败，定义一个空函数避免报错
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


def load_hash_database(db_path: Path) -> Dict[str, np.ndarray]:
    """加载哈希数据库"""
    print(f"📂 加载哈希数据库: {db_path}")

    with open(db_path, "r", encoding="utf-8") as f:
        db_raw = json.load(f)

    # 数据库格式: {hash_str: card_id}
    # 需要转换为: {card_id: hash_arr}
    db_decoded: Dict[str, np.ndarray] = {}
    for hash_str, card_id in db_raw.items():
        hash_arr = decode_hash_from_base64(hash_str)
        db_decoded[card_id] = hash_arr

    print(f"✅ 已加载 {len(db_decoded)} 张卡牌")
    print(
        f"   示例: {list(db_decoded.keys())[0]} = {list(db_decoded.values())[0][:3]}..."
    )
    return db_decoded


def detect_cards(model_path: str, pil_image: Image.Image, conf_threshold: float = 0.6):
    """YOLO 检测卡牌，返回检测结果和带绿色框的可视化图片"""
    # 检查 YOLO 是否可用（已在全局导入）
    if not ULTRALYTICS_AVAILABLE:
        raise ImportError("ultralytics not installed")

    print("     [1/7] 检查 YOLO 可用性...", end=" ")
    t1 = time.perf_counter()
    t0 = t1
    print(f"✅ ({(time.perf_counter() - t1) * 1000:.1f}ms)")

    print("     [2/7] 加载 YOLO 模型...", end=" ")
    t2 = time.perf_counter()
    model = YOLO(model_path)
    print(f"✅ ({(time.perf_counter() - t2) * 1000:.1f}ms)")

    print("     [3/7] PIL 转 numpy...", end=" ")
    t3 = time.perf_counter()
    # PIL -> BGR
    img_array = np.array(pil_image)
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    print(f"✅ ({(time.perf_counter() - t3) * 1000:.1f}ms)")

    print("     [4/7] 创建可视化副本...", end=" ")
    t4 = time.perf_counter()
    # 创建可视化副本（用于绘制框）
    vis_img = img_bgr.copy()
    print(f"✅ ({(time.perf_counter() - t4) * 1000:.1f}ms)")

    print("     [5/7] YOLO 推理...", end=" ")
    t5 = time.perf_counter()
    # 检测
    results = model(img_bgr, verbose=False)
    result = results[0]
    print(f"✅ ({(time.perf_counter() - t5) * 1000:.1f}ms)")

    if result.obb is None or len(result.obb) == 0:
        total_time = (time.perf_counter() - t0) * 1000
        print(f"\n     ❌ 未检测到卡牌 (总耗时: {total_time:.1f}ms)")
        return [], img_bgr, vis_img

    print("     [6/7] 处理检测框...", end=" ")
    t6 = time.perf_counter()
    cropped_cards = []
    for i, obb in enumerate(result.obb):
        conf = float(obb.conf[0].item())

        if conf < conf_threshold:
            continue

        # 方法1：直接裁剪矩形框（对标原项目，推荐）
        if hasattr(obb, "xyxy") and obb.xyxy is not None:
            # 使用普通矩形框
            x1, y1, x2, y2 = map(int, obb.xyxy[0])
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(img_bgr.shape[1], x2), min(img_bgr.shape[0], y2)
            cropped = img_bgr[y1:y2, x1:x2]
            # 计算中心点坐标（用于排序：从左到右，从上到下）
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
        else:
            # 备用：使用旋转框（透视变换）
            xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
            corners = xyxyxyxy.astype(np.float32)
            target_w, target_h = 480, 670
            dst = np.array(
                [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
                dtype=np.float32,
            )
            matrix = cv2.getPerspectiveTransform(corners, dst)
            cropped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))
            # 旋转框：使用边界框中心
            center_x = corners[:, 0].mean()
            center_y = corners[:, 1].mean()
            # 对于旋转框，使用外接矩形坐标
            x1, y1 = int(corners[:, 0].min()), int(corners[:, 1].min())
            x2, y2 = int(corners[:, 0].max()), int(corners[:, 1].max())

        # 绘制绿色外框（置信度阈值以上）
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), (0, 255, 0), 3)  # 绿色，线宽3

        # 标注置信度（框上方）
        conf_text = f"{conf:.2f}"
        text_size = cv2.getTextSize(conf_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
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
                "index": i + 1,  # 临时编号，后续会重新排序
                "confidence": conf,
                "cropped": cropped,
                "center_x": center_x,
                "center_y": center_y,
                "bbox": (x1, y1, x2, y2),  # 保存原始坐标用于绘制红色框
            }
        )
    process_time = (time.perf_counter() - t6) * 1000
    print(f"✅ ({process_time:.1f}ms, {len(cropped_cards)}张卡牌)")

    total_time = (time.perf_counter() - t0) * 1000
    print(f"     [7/7] 检测完成 (总耗时: {total_time:.1f}ms)")

    return cropped_cards, img_bgr, vis_img


def match_against_database(
    cropped_cards: List[Dict],
    hash_db: Dict[str, np.ndarray],
    vis_img: np.ndarray,
    similarity_threshold: float = 0.55,
) -> Tuple[List[MatchResult], int, int, np.ndarray]:
    """
    将检测到的卡牌与数据库匹配，并在匹配成功时绘制红色内框

    Returns:
        (matches, total_checked, above_threshold_count, updated_vis_img)
    """
    matches: List[MatchResult] = []
    total_checked = len(cropped_cards) * len(hash_db)
    above_threshold_count = 0

    print(f"\n🔍 开始匹配 ({len(cropped_cards)} 张检测 × {len(hash_db)} 张数据库)")
    print(f"   阈值: {similarity_threshold} (推荐生产环境使用 0.68)")
    print("-" * 70)

    start_time = time.perf_counter()

    # 保存裁剪图片供检查
    output_dir = Path("output/test_crops")
    output_dir.mkdir(parents=True, exist_ok=True)

    for card in cropped_cards:
        # 保存裁剪图片（新命名：card_1.jpg, card_2.jpg...）
        crop_path = output_dir / f"card_{card['index']}.jpg"
        cv2.imwrite(str(crop_path), card["cropped"])

        # 计算检测卡牌的哈希（统一使用 PIL 处理流程）
        pil_img = Image.fromarray(cv2.cvtColor(card["cropped"], cv2.COLOR_BGR2RGB))
        color_pixels = pil_to_color_pixels(pil_img)
        card_hash = calculate_perceptual_hash(color_pixels)

        # 与数据库中所有卡牌比对
        best_match: Optional[MatchResult] = None
        above_threshold_for_card = 0

        for card_id, db_hash in hash_db.items():
            similarity = calculate_similarity(card_hash, db_hash)

            if similarity >= similarity_threshold:
                above_threshold_count += 1
                above_threshold_for_card += 1

            # 记录最佳匹配（无论是否超过阈值）
            if best_match is None or similarity > best_match.similarity:
                best_match = MatchResult(
                    detected_index=card["index"],
                    card_id=card_id,
                    similarity=similarity,
                    confidence=card["confidence"],
                )

        # 输出当前卡牌的最佳匹配（显示前3）
        if best_match:
            # 找出所有匹配，按相似度排序
            all_similarities = []
            for card_id, db_hash in hash_db.items():
                sim = calculate_similarity(card_hash, db_hash)
                all_similarities.append((card_id, sim))

            all_similarities.sort(key=lambda x: x[1], reverse=True)
            top3 = all_similarities[:3]

            status = "✅" if best_match.similarity >= similarity_threshold else "❌"
            print(
                f"   卡牌 #{card['index']}: {status} 最佳匹配: {best_match.card_id} "
                f"(相似度: {best_match.similarity:.4f}, 置信度: {best_match.confidence:.3f})"
            )

            # 显示前3候选
            for i, (cid, sim) in enumerate(top3, 1):
                mark = "👑" if sim >= similarity_threshold else "  "
                print(f"      {mark} 候选{i}: {cid} = {sim:.4f}")

            if best_match.similarity >= similarity_threshold:
                matches.append(best_match)

                # 绘制红色内框（嵌套在绿色框内）
                x1, y1, x2, y2 = card["bbox"]
                # 内缩 5 像素绘制红色框
                inner_x1, inner_y1 = x1 + 5, y1 + 5
                inner_x2, inner_y2 = x2 - 5, y2 - 5
                cv2.rectangle(
                    vis_img, (inner_x1, inner_y1), (inner_x2, inner_y2), (0, 0, 255), 2
                )  # 红色，线宽2

                # 框内居中标注卡牌ID
                card_id = best_match.card_id
                text_size = cv2.getTextSize(card_id, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[
                    0
                ]
                text_x = (inner_x1 + inner_x2 - text_size[0]) // 2
                text_y = (inner_y1 + inner_y2 + text_size[1]) // 2
                cv2.putText(
                    vis_img,
                    card_id,
                    (text_x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2,
                )
        else:
            print(f"   卡牌 #{card['index']}: ❌ 无匹配")

    elapsed = time.perf_counter() - start_time

    return matches, total_checked, above_threshold_count, vis_img


def run_matching_test(
    model_path: str,
    hash_db_path: Path,
    screenshot: Image.Image,
    similarity_threshold: float = 0.68,
    source: str = "ADB",
):
    """核心匹配测试逻辑（支持 ADB 和文件两种来源）"""
    print("=" * 70)
    print(f"大规模匹配测试（{source} 模式）")
    print("=" * 70)

    # 1. 加载数据库
    start_time = time.perf_counter()
    hash_db = load_hash_database(hash_db_path)
    db_load_time = time.perf_counter() - start_time
    print(f"   耗时: {db_load_time * 1000:.1f}ms")

    # 2. 显示截图信息
    print(f"\n✅ 截图: {screenshot.width}x{screenshot.height}")

    # 3. YOLO 检测
    print(f"\n🚀 加载模型并检测: {model_path}")
    start_time = time.perf_counter()
    cropped_cards, _, vis_img = detect_cards(model_path, screenshot, conf_threshold=0.6)
    detect_time = time.perf_counter() - start_time

    if not cropped_cards:
        print(f"❌ 未检测到任何卡牌 (检测耗时: {detect_time * 1000:.1f}ms)")
        return

    print(
        f"✅ 检测到 {len(cropped_cards)} 张卡牌 (检测耗时: {detect_time * 1000:.1f}ms)"
    )

    # 4. 按阅读顺序排序（从左到右，从上到下）
    start_time = time.perf_counter()
    cropped_cards.sort(key=lambda c: (c["center_x"], c["center_y"]))
    # 重新编号
    for i, card in enumerate(cropped_cards, 1):
        card["index"] = i
    sort_time = time.perf_counter() - start_time
    print(f"   已按从左到右、从上到下排序 (排序耗时: {sort_time * 1000:.1f}ms)")

    # 5. 大规模匹配（同时绘制红色内框）
    print(f"\n🔍 开始匹配 ({len(cropped_cards)} 张检测 × {len(hash_db)} 张数据库)")
    start_time = time.perf_counter()
    matches, total_checked, above_threshold, vis_img = match_against_database(
        cropped_cards, hash_db, vis_img, similarity_threshold
    )
    match_time = time.perf_counter() - start_time
    print(
        f"   匹配完成 (耗时: {match_time * 1000:.1f}ms, 平均每张: {match_time / len(cropped_cards) * 1000:.1f}ms)"
    )

    # 6. 结果汇总
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
        print(f"\n   ✅ 匹配详情:")
        avg_sim = sum(m.similarity for m in matches) / len(matches)
        print(f"      平均相似度: {avg_sim:.4f}")

        # 按相似度排序显示
        sorted_matches = sorted(matches, key=lambda x: x.similarity, reverse=True)
        for i, m in enumerate(sorted_matches[:10], 1):  # 显示前10
            print(
                f"      {i}. {m.card_id}: {m.similarity:.4f} (检测# {m.detected_index})"
            )

        if len(sorted_matches) > 10:
            print(f"      ... 还有 {len(sorted_matches) - 10} 张")

    # 7. 未匹配的卡牌
    matched_indices = {m.detected_index for m in matches}
    unmatched = [c for c in cropped_cards if c["index"] not in matched_indices]

    if unmatched:
        print(f"\n   ⚠️  未匹配的卡牌 ({len(unmatched)} 张):")
        for c in unmatched:
            print(f"      卡牌 #{c['index']}: 置信度 {c['confidence']:.3f}")

    # 6. 结果汇总
    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    start_time = time.perf_counter()
    print(f"   检测到的卡牌: {len(cropped_cards)} 张")
    print(f"   数据库卡牌数: {len(hash_db)} 张")
    print(f"   总比对次数: {total_checked:,} 次")
    print(f"   阈值以上次数: {above_threshold} 次")
    print(f"   成功匹配: {len(matches)} 张")
    print(f"   匹配率: {len(matches) / len(cropped_cards) * 100:.1f}%")

    if matches:
        print(f"\n   ✅ 匹配详情:")
        avg_sim = sum(m.similarity for m in matches) / len(matches)
        print(f"      平均相似度: {avg_sim:.4f}")

        # 按相似度排序显示
        sorted_matches = sorted(matches, key=lambda x: x.similarity, reverse=True)
        for i, m in enumerate(sorted_matches[:10], 1):  # 显示前10
            print(
                f"      {i}. {m.card_id}: {m.similarity:.4f} (检测# {m.detected_index})"
            )

        if len(sorted_matches) > 10:
            print(f"      ... 还有 {len(sorted_matches) - 10} 张")
    summary_time = time.perf_counter() - start_time

    # 7. 未匹配的卡牌
    matched_indices = {m.detected_index for m in matches}
    unmatched = [c for c in cropped_cards if c["index"] not in matched_indices]

    if unmatched:
        print(f"\n   ⚠️  未匹配的卡牌 ({len(unmatched)} 张):")
        for c in unmatched:
            print(f"      卡牌 #{c['index']}: 置信度 {c['confidence']:.3f}")

    print("\n" + "=" * 70)
    print("结论:")
    if len(matches) >= len(cropped_cards) * 0.8:  # 80% 匹配率
        print("   🎉 表现优秀！建议使用当前模型 (阈值 0.68)")
    elif len(matches) >= len(cropped_cards) * 0.5:  # 50% 匹配率
        print("   ⚠️  表现一般，建议检查图片质量或调整阈值")
    else:
        print("   ❌ 表现不佳，可能需要优化模型或数据库")
    print("=" * 70)

    # 8. 准备可视化（但不立即显示，等所有文字输出完成后再显示）
    print(f"\n📸 生成检测结果可视化...")
    start_time = time.perf_counter()
    # 缩放至高度 1000px（在终端中显示更大）
    current_height = vis_img.shape[0]
    if current_height > 1000:
        scale = 1000 / current_height
        new_width = int(vis_img.shape[1] * scale)
        vis_img_resized = cv2.resize(
            vis_img, (new_width, 1000), interpolation=cv2.INTER_AREA
        )
    else:
        vis_img_resized = vis_img

    # 转换为 PIL Image
    vis_pil = Image.fromarray(cv2.cvtColor(vis_img_resized, cv2.COLOR_BGR2RGB))
    vis_time = time.perf_counter() - start_time
    print(f"   图片处理耗时: {vis_time * 1000:.1f}ms")

    # 总耗时统计
    total_time = (
        db_load_time + detect_time + sort_time + match_time + summary_time + vis_time
    )
    print(f"\n⏱️  各阶段耗时统计:")
    print(f"   数据库加载: {db_load_time * 1000:.1f}ms")
    print(f"   YOLO 检测:  {detect_time * 1000:.1f}ms")
    print(f"   排序:       {sort_time * 1000:.1f}ms")
    print(
        f"   哈希匹配:   {match_time * 1000:.1f}ms (平均每张: {match_time / len(cropped_cards) * 1000:.1f}ms)"
    )
    print(f"   结果汇总:   {summary_time * 1000:.1f}ms")
    print(f"   可视化:     {vis_time * 1000:.1f}ms")
    print(f"   ─────────────────────────")
    print(f"   总计:       {total_time * 1000:.1f}ms ({total_time:.2f}s)")

    # 最后显示图片（确保不会被后续输出覆盖）
    print(f"\n🖼️  正在显示检测结果...")

    # 先保存到持久化文件（不用临时文件，避免被提前删除）
    vis_path = Path("output/detection_result.jpg")
    vis_pil.save(vis_path)
    print(f"   💾 已保存到: {vis_path}")

    # 用文件路径调用预览（避免创建临时文件）
    time.sleep(0.1)  # 短暂延迟确保文件写入完成
    if preview_image_inline(vis_path):
        print(f"✅ 可视化已显示在终端")
    else:
        print(f"⚠️  终端显示失败，请直接查看文件: {vis_path}")


def main():
    # 配置
    model_path = "../runs/obb/output/models/card_obb5/weights/best.pt"
    hash_db_path = Path("data/hash_database_a1.json")

    # 检查文件
    if not Path(model_path).exists():
        print(f"❌ 模型不存在: {model_path}")
        sys.exit(1)

    if not hash_db_path.exists():
        print(f"❌ 哈希数据库不存在: {hash_db_path}")
        print("💡 请先运行: python scripts/generate_hash_db.py")
        sys.exit(1)

    # 检查是否有文件参数
    if len(sys.argv) > 1:
        screenshot_path = Path(sys.argv[1])
        if screenshot_path.exists():
            # 从文件加载截图
            print(f"📂 加载截图: {screenshot_path}")
            screenshot = Image.open(screenshot_path)
            run_matching_test(
                model_path=model_path,
                hash_db_path=hash_db_path,
                screenshot=screenshot,
                similarity_threshold=0.68,
                source="文件",
            )
            return
        else:
            print(f"❌ 截图文件不存在: {screenshot_path}")
            sys.exit(1)

    # 自动发现设备（ADB 模式）
    print("🔍 自动发现ADB设备...")
    devices = discover_devices_simple()
    if not devices:
        print("❌ 未发现ADB设备")
        print("💡 使用方法: python test_massive_matching.py <截图文件路径>")
        sys.exit(1)

    device_address = devices[0]
    print(f"✅ 发现设备: {device_address}")

    # ADB 截图
    print(f"\n📱 连接设备: {device_address}")
    adb = SimpleAdbController(device_address)
    print("📸 正在截图...")
    screenshot = adb.screenshot()
    if not screenshot:
        print("❌ 截图失败")
        sys.exit(1)

    # 执行匹配测试
    run_matching_test(
        model_path=model_path,
        hash_db_path=hash_db_path,
        screenshot=screenshot,
        similarity_threshold=0.68,
        source="ADB",
    )


if __name__ == "__main__":
    main()
