"""
YOLO 模型性能对比测试
对比 PyTorch (.pt) vs CoreML (.mlpackage) 推理速度
"""

import time
from pathlib import Path

import numpy as np
from PIL import Image


def benchmark_model(model_path: str, image_path: str, runs: int = 10):
    """测试模型推理时间"""
    from ultralytics import YOLO

    print(f"\n加载模型: {Path(model_path).name}")
    model = YOLO(model_path)

    # 加载图片
    img = Image.open(image_path)
    img_array = np.array(img)

    # 预热（第1次加载较慢，不计入统计）
    print("  预热中...")
    model(img_array, verbose=False)

    # 正式测试
    print(f"  运行 {runs} 次测试...")
    times = []
    for i in range(runs):
        start = time.perf_counter()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # 转换为毫秒

    # 统计
    times = np.array(times)
    avg = times.mean()
    std = times.std()
    min_t = times.min()
    max_t = times.max()

    print(f"  平均: {avg:.1f}ms ± {std:.1f}ms")
    print(f"  范围: {min_t:.1f}ms - {max_t:.1f}ms")

    return avg, std


def main():
    # 配置
    pytorch_model = "../runs/obb/output/models/card_obb/weights/best.pt"
    coreml_model = "../runs/obb/output/models/card_obb/weights/best.mlpackage"
    test_image = "/tmp/ptcgp_auto_5755/screenshot.png"
    runs = 10

    print("=" * 50)
    print("YOLO 模型性能对比测试")
    print("=" * 50)
    print(f"测试图片: {test_image}")
    print(f"测试次数: {runs}")

    # 测试 PyTorch
    pt_avg, pt_std = benchmark_model(pytorch_model, test_image, runs)

    # 测试 CoreML
    ml_avg, ml_std = benchmark_model(coreml_model, test_image, runs)

    # 对比结果
    print("\n" + "=" * 50)
    print("对比结果")
    print("=" * 50)
    print(f"PyTorch (.pt):     {pt_avg:.1f}ms ± {pt_std:.1f}ms")
    print(f"CoreML (.mlpackage): {ml_avg:.1f}ms ± {ml_std:.1f}ms")

    if ml_avg < pt_avg:
        speedup = pt_avg / ml_avg
        print(f"\n✅ CoreML 更快，提速: {speedup:.2f}x")
    else:
        slowdown = ml_avg / pt_avg
        print(f"\n⚠️ CoreML 更慢，减速: {slowdown:.2f}x")

    print("\n说明:")
    print("  - CoreML 使用 Apple Neural Engine (ANE)")
    print("  - 如果 CoreML 更慢，可能是模型太小，ANE 优势不明显")
    print("  - 或者 ANE 未启用（macOS 版本问题）")


if __name__ == "__main__":
    main()
