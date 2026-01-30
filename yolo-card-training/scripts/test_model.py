"""
模型测试脚本 - 用真实截图验证YOLO检测效果
支持终端内联图片预览（Kitty icat）和ADB自动截图
"""

import argparse
import cv2
import io
import numpy as np
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image
from typing import List, Optional, Tuple

# 添加主项目路径以导入 ADB 模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
from ptcgp_auto_v2.utils.device_discovery import discover_devices


def _is_kitty() -> bool:
    """检测是否在 Kitty 终端中运行"""
    return os.environ.get("KITTY_WINDOW_ID") is not None


def _has_icat() -> bool:
    """检测是否有 kitten icat 命令"""
    try:
        result = subprocess.run(
            ["kitten", "icat", "--help"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def preview_image_inline(image: Image.Image, max_width: int = 60) -> bool:
    """在终端中内联预览图片（Kitty icat）"""
    if not _is_kitty():
        print("  (不是Kitty终端)")
        return False

    if not _has_icat():
        print("  (未找到kitten icat)")
        return False

    import tempfile

    temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    try:
        # 缩放图片以适应终端
        w, h = image.size
        if w > max_width * 10:  # 假设每字符约10像素
            ratio = (max_width * 10) / w
            new_w = int(w * ratio)
            new_h = int(h * ratio)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

        image.save(temp_file.name)
        subprocess.run(
            ["kitten", "icat", "--align", "left", temp_file.name],
            check=True,
            timeout=10,
            stderr=subprocess.PIPE,
        )
        print()
        return True
    except Exception as e:
        print(f"  (预览失败: {e})")
        return False
    finally:
        try:
            os.unlink(temp_file.name)
        except Exception:
            pass


class SimpleAdbController:
    """简化版 ADB 控制器，仅用于截图"""

    def __init__(self, address: str):
        self.address = address
        self._connect()

    def _connect(self):
        """连接到设备"""
        # 先尝试连接
        subprocess.run(
            ["adb", "connect", self.address],
            capture_output=True,
            check=False,
        )

    def screenshot(self) -> Optional[Image.Image]:
        """截取屏幕截图"""
        try:
            result = subprocess.run(
                ["adb", "-s", self.address, "exec-out", "screencap", "-p"],
                capture_output=True,
                check=True,
                timeout=10,
            )
            return Image.open(io.BytesIO(result.stdout))
        except Exception as e:
            print(f"❌ ADB截图失败: {e}")
            return None


def discover_devices_simple() -> List[str]:
    """自动发现 BlueStacks 设备"""
    try:
        # 尝试导入并使用主项目的发现工具
        devices = discover_devices()
        if devices:
            return devices
    except Exception:
        pass

    # 备用方案：直接adb devices
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True,
        )
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:  # 跳过标题行
            if line.strip() and "device" in line:
                addr = line.split()[0]
                devices.append(addr)
        return devices
    except Exception:
        return []


def draw_boxes_on_image(
    img: np.ndarray, results, conf_threshold: float = 0.5
) -> Tuple[Image.Image, int]:
    """
    在图片上绘制检测框
    返回 PIL Image 和检测到的目标数
    """
    result = results[0]
    boxes = result.obb if hasattr(result, "obb") and result.obb else result.boxes

    detected_count = 0
    for i, box in enumerate(boxes):
        conf = box.conf.item() if hasattr(box.conf, "item") else float(box.conf)

        if conf < conf_threshold:
            continue

        detected_count += 1

        # 获取框坐标
        if hasattr(box, "xyxyxyxy") and box.xyxyxyxy is not None:
            # OBB 四边形
            pts = box.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
            pts = pts.astype(np.int32)
            cv2.polylines(img, [pts], True, (0, 255, 0), 2)
            x1, y1 = int(pts[0][0]), int(pts[0][1])
        elif hasattr(box, "xyxy") and box.xyxy is not None:
            # 普通 BBox
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        else:
            continue

        # 绘制置信度文字
        label = f"{conf:.2f}"
        cv2.putText(
            img, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
        )

    # 添加总数标签
    cv2.putText(
        img,
        f"Detected: {detected_count}",
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        1,
        (255, 0, 0),
        2,
    )

    return Image.fromarray(img), detected_count


def load_model_and_detect(model_path: str, image: Image.Image, conf_threshold: float):
    """加载模型并检测"""
    from ultralytics import YOLO

    print(f"加载模型: {model_path}")
    model = YOLO(model_path)

    # PIL Image -> numpy (RGB) -> BGR (OpenCV/YOLO 格式)
    img_array = np.array(image)

    # 处理通道数：RGBA -> RGB -> BGR
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        # RGBA 去掉 alpha 通道
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    # YOLO 检测
    results = model(img_bgr, verbose=False)

    result = results[0]
    boxes = result.obb if hasattr(result, "obb") else result.boxes

    print(f"\n检测到 {len(boxes)} 个目标 (置信度阈值: {conf_threshold})")
    for i, box in enumerate(boxes):
        conf = box.conf.item() if hasattr(box.conf, "item") else box.conf
        status = "✅" if conf >= conf_threshold else "❌"
        print(f"  [{i + 1}] {status} 置信度: {conf:.3f}")

    # 绘制检测框 (使用原始 BGR 图像)
    pil_img, detected_count = draw_boxes_on_image(img_bgr, results, conf_threshold)

    return pil_img, detected_count


def test_with_adb(model_path: str, device_address: str, conf_threshold: float):
    """通过ADB截图并测试"""
    print(f"连接设备: {device_address}")
    adb = SimpleAdbController(device_address)

    print("📸 正在截图...")
    screenshot = adb.screenshot()
    if not screenshot:
        print("❌ 截图失败，请检查设备是否连接")
        return False

    print(f"✅ 截图成功: {screenshot.width}x{screenshot.height}")

    # 进行检测
    pil_img, detected_count = load_model_and_detect(
        model_path, screenshot, conf_threshold
    )

    # 终端预览
    print("\n📸 检测结果预览:")
    if not preview_image_inline(pil_img):
        print("  (终端不支持图片预览，已保存到文件)")

    # 保存结果到 output/ 目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"adb_detected_{timestamp}.jpg"
    pil_img.save(output_path)
    print(f"✅ 结果已保存: {output_path}")
    print(f"   通过阈值过滤的目标数: {detected_count}")

    return True


def test_with_image(model_path: str, image_path: str, conf_threshold: float):
    """用本地图片测试"""
    image = Image.open(image_path)
    print(f"\n测试图片: {image_path} ({image.width}x{image.height})")

    pil_img, detected_count = load_model_and_detect(model_path, image, conf_threshold)

    # 终端预览
    print("\n📸 检测结果预览:")
    if not preview_image_inline(pil_img):
        print("  (终端不支持图片预览，已保存到文件)")

    # 保存结果到 output/ 目录
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    input_name = Path(image_path).stem
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{input_name}_detected_{timestamp}.jpg"
    pil_img.save(output_path)
    print(f"✅ 结果已保存: {output_path}")
    print(f"   通过阈值过滤的目标数: {detected_count}")


def main():
    parser = argparse.ArgumentParser(description="测试YOLO OBB模型（支持ADB自动截图）")
    parser.add_argument(
        "--model",
        required=True,
        help="模型路径 (如 runs/obb/output/models/card_obb/weights/best.pt)",
    )
    parser.add_argument(
        "--image",
        help="测试图片路径 (可选，不提供则使用ADB截图)",
    )
    parser.add_argument(
        "--adb",
        help="ADB设备地址 (如 127.0.0.1:5555，不提供则自动发现)",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="置信度阈值 (默认: 0.5)",
    )
    args = parser.parse_args()

    if args.image:
        # 使用本地图片
        if not Path(args.image).exists():
            print(f"❌ 图片不存在: {args.image}")
            sys.exit(1)
        test_with_image(args.model, args.image, args.conf)
    else:
        # 使用ADB截图
        device_address = args.adb
        if not device_address:
            # 自动发现设备
            print("🔍 自动发现ADB设备...")
            devices = discover_devices_simple()
            if not devices:
                print("❌ 未发现任何ADB设备")
                print("💡 请手动指定: --adb 127.0.0.1:5555")
                sys.exit(1)
            device_address = devices[0]
            print(f"✅ 发现设备: {device_address}")
            if len(devices) > 1:
                print(f"   (共发现 {len(devices)} 个设备，使用第一个)")

        test_with_adb(args.model, device_address, args.conf)


if __name__ == "__main__":
    main()
