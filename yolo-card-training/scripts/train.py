#!/usr/bin/env python3
"""
YOLO 模型训练脚本

在 M3 MacBook Air 上使用 MPS (Metal Performance Shaders) 加速训练
"""

import argparse
import sys
from pathlib import Path


def check_mps():
    """检查 MPS 是否可用"""
    import torch

    if torch.backends.mps.is_available():
        print("✅ MPS (Metal) 可用")
        return "mps"
    else:
        print("⚠️  MPS 不可用，将使用 CPU 训练（较慢）")
        return "cpu"


def train_model(
    data_yaml: Path, epochs: int = 100, batch: int = 16, device: str = None
):
    """训练 YOLO 模型"""
    from ultralytics import YOLO

    # 自动检测设备
    if device is None:
        device = check_mps()

    print("\n🚀 开始训练")
    print(f"   数据: {data_yaml}")
    print(f"   轮数: {epochs}")
    print(f"   Batch: {batch}")
    print(f"   设备: {device}")

    # 加载预训练模型
    print("\n📥 加载 yolo11n-obb.pt...")
    model = YOLO("yolo11n-obb.pt")

    # 训练
    print("\n⏳ 训练中...")
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=640,
        batch=batch,
        device=device,
        patience=20,  # 早停
        save=True,
        project="output/models",
        name="card_obb",
        verbose=True,
    )

    return results


def export_model(model_path: Path):
    """导出为 CoreML（macOS 加速推理）"""
    from ultralytics import YOLO

    print(f"\n📦 导出 CoreML: {model_path}")
    model = YOLO(str(model_path))

    # 导出
    model.export(format="coreml", imgsz=640)

    print("✅ 导出完成！")


def main():
    parser = argparse.ArgumentParser(description="YOLO 卡牌检测模型训练")
    parser.add_argument(
        "--data",
        type=Path,
        default="data/synthetic/data.yaml",
        help="数据集配置文件路径",
    )
    parser.add_argument("--epochs", type=int, default=100, help="训练轮数")
    parser.add_argument(
        "--batch", type=int, default=16, help="Batch size（M3 Air 建议 16）"
    )
    parser.add_argument(
        "--device", type=str, default=None, help="设备: mps (Mac), cpu, 或 0 (CUDA)"
    )
    parser.add_argument("--export", action="store_true", help="训练后导出 CoreML")
    args = parser.parse_args()

    print("=" * 50)
    print("YOLO 卡牌检测模型训练")
    print("=" * 50)

    # 检查数据
    if not args.data.exists():
        print(f"❌ 数据集不存在: {args.data}")
        print("💡 请先运行: python scripts/generate_dataset.py")
        sys.exit(1)

    # 训练
    train_model(
        args.data,
        epochs=args.epochs,
        batch=args.batch,
        device=args.device,
    )

    # 显示结果
    print("\n" + "=" * 50)
    print("训练完成！")
    print("=" * 50)
    # ultralytics 实际输出路径（project 参数可能被覆盖）
    actual_output = "runs/obb/output/models/card_obb/weights"
    print(f"⚠️  注意：ultralytics 实际输出到: {actual_output}/")
    print(f"最佳模型: {actual_output}/best.pt")
    print(f"最后模型: {actual_output}/last.pt")

    # 导出 CoreML
    if args.export:
        export_model(Path(f"{actual_output}/best.pt"))

    print("\n💡 使用模型:")
    print(f"   uv run python scripts/test_model.py --model {actual_output}/best.pt")
    print("   uv run python scripts/benchmark.py")


if __name__ == "__main__":
    main()
