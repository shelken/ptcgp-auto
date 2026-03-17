# -*- coding: utf-8 -*-
"""
YOLO+Hash 识别性能基准测试脚本

测试指标:
- YOLO检测耗时
- Hash计算耗时
- Hash匹配耗时（单张 vs 批量）
- 全流程耗时

说明: 本脚本走 v2 运行时链路（ModelManager/CardHashManager/YoloCardRecognizer），用于贴近线上路径的性能回归；test_massive_matching.py 更偏离线评测。
"""

import argparse
import sys
import time
from pathlib import Path

from PIL import Image

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ptcgp_auto_v2.config import constants
from ptcgp_auto_v2.infra.card_hash_manager import CardHashManager
from ptcgp_auto_v2.infra.model_manager import get_model_manager
from ptcgp_auto_v2.infra.yolo_card_recognizer import YoloCardRecognizer
from ptcgp_auto_v2.utils.perceptual_hash import (
    bgr_to_color_pixels,
    calculate_perceptual_hash,
)


class DummyAdb:
    """用于基准测试的 ADB 适配器"""

    def __init__(self, image: Image.Image):
        self._image = image
        self._width, self._height = image.size

    def screenshot(self):
        return self._image

    def scaled_x(self, value: int) -> int:
        return int(value * self._width / constants.BASE_SCREEN_WIDTH)

    def scaled_y(self, value: int) -> int:
        return int(value * self._height / constants.BASE_SCREEN_HEIGHT)


def parse_args():
    parser = argparse.ArgumentParser(description="YOLO+Hash 识别性能基准测试")
    parser.add_argument("--image", required=True, help="开包结果截图路径")
    parser.add_argument(
        "--set-code",
        required=False,
        help="卡牌系列代码（如 A1）。未提供则使用全局匹配",
    )
    parser.add_argument("--repeat", type=int, default=3, help="重复测试次数")
    return parser.parse_args()


def main():
    args = parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"图片不存在: {image_path}")
        return 1

    image = Image.open(image_path)
    adb = DummyAdb(image)

    # 依赖检查（CoreML 推理需要 coremltools）
    try:
        import coremltools  # noqa: F401
    except Exception:
        print("缺少 coremltools，无法加载 .mlpackage 模型")
        print("请使用 uv 安装依赖:")
        print('  uv pip install "coremltools>=9.0" "numpy>=1.14.5,<=2.3.5"')
        return 1

    # 模型加载
    model_manager = get_model_manager()
    start = time.perf_counter()
    model_manager.load_model_async()
    if not model_manager.wait_for_model(timeout=120):
        print("模型加载超时，请检查模型文件是否可用")
        return 1
    model_load_time = time.perf_counter() - start

    # Hash 管理器准备
    hash_manager = CardHashManager()
    start = time.perf_counter()
    if args.set_code:
        hash_manager.ensure_series_ready(args.set_code)
    else:
        hash_manager.load_all_hashes()
    hash_prepare_time = time.perf_counter() - start

    recognizer = YoloCardRecognizer(
        adb=adb, model_manager=model_manager, hash_manager=hash_manager
    )

    print("=" * 60)
    print("YOLO+Hash 识别性能基准测试")
    print("=" * 60)
    print(f"模型加载耗时: {model_load_time:.3f}s")
    print(f"Hash准备耗时: {hash_prepare_time:.3f}s")
    print(f"测试图片: {image_path}")
    print(f"系列代码: {args.set_code or '全局匹配'}")
    print(f"重复次数: {args.repeat}")

    for i in range(args.repeat):
        print("-" * 60)
        print(f"第 {i + 1} 次测试")

        # YOLO检测
        start = time.perf_counter()
        detected = recognizer._detect_cards(
            screenshot=image, conf_threshold=constants.YOLO_OBB_THRESHOLD
        )
        detect_time = time.perf_counter() - start

        # Hash计算 + 匹配
        hash_times = []
        match_times = []
        matched = 0

        for info in detected:
            start = time.perf_counter()
            color_pixels = bgr_to_color_pixels(info.cropped)
            card_hash = calculate_perceptual_hash(color_pixels)
            hash_times.append(time.perf_counter() - start)

            start = time.perf_counter()
            match = hash_manager.find_best_match(
                card_hash,
                set_code=args.set_code,
                threshold=constants.HASH_SIMILARITY_THRESHOLD,
            )
            match_times.append(time.perf_counter() - start)
            if match:
                matched += 1

        total_time = detect_time + sum(hash_times) + sum(match_times)

        print(f"YOLO检测耗时: {detect_time:.3f}s")
        print(f"Hash计算耗时(总): {sum(hash_times):.3f}s")
        print(f"Hash匹配耗时(总): {sum(match_times):.3f}s")
        print(f"识别总耗时: {total_time:.3f}s")
        print(f"检测到卡牌: {len(detected)} 张, 匹配成功: {matched} 张")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
