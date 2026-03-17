#!/usr/bin/env python3
"""
YOLO + 哈希匹配测试脚本
测试 A1-183 卡牌能否被正确识别
"""

__test__ = False

import io
import sys
import subprocess
import cv2
import numpy as np
from pathlib import Path
from PIL import Image
from dataclasses import dataclass

# ============ 哈希工具实现 (来自 yolo-hash 分支) ============

HASH_SIZE = 96
FREQ_SIZE = 8


@dataclass
class ColorPixels:
    r: list
    g: list
    b: list


def pil_to_color_pixels(pil_image: Image.Image) -> ColorPixels:
    """从 PIL Image 转换为 ColorPixels - 统一预处理流程
    参考原仓库实现：resize(cubic) + removeAlpha + sRGB
    """
    # 去除 Alpha 通道（如果存在）
    if pil_image.mode == "RGBA":
        pil_image = pil_image.convert("RGB")
    elif pil_image.mode != "RGB":
        pil_image = pil_image.convert("RGB")

    # resize 使用 cubic（与原仓库的 sharp.kernel.cubic 对应）
    pil_image = pil_image.resize((HASH_SIZE, HASH_SIZE), Image.BICUBIC)

    # 转换为 numpy array
    rgb = np.array(pil_image)

    color_pixels = ColorPixels(
        r=[0] * (HASH_SIZE * HASH_SIZE),
        g=[0] * (HASH_SIZE * HASH_SIZE),
        b=[0] * (HASH_SIZE * HASH_SIZE),
    )

    flat = rgb.reshape(-1, 3)
    for idx, (r, g, b) in enumerate(flat):
        color_pixels.r[idx] = int(r)
        color_pixels.g[idx] = int(g)
        color_pixels.b[idx] = int(b)

    return color_pixels


def bgr_to_color_pixels(bgr_image: np.ndarray) -> ColorPixels:
    """从 BGR 图片转换为 ColorPixels - 向后兼容版"""
    if bgr_image.ndim == 2:
        bgr_image = cv2.cvtColor(bgr_image, cv2.COLOR_GRAY2BGR)
    elif bgr_image.shape[2] == 4:
        bgr_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGRA2BGR)

    resized = cv2.resize(
        bgr_image,
        (HASH_SIZE, HASH_SIZE),
        interpolation=cv2.INTER_CUBIC,
    )
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    color_pixels = ColorPixels(
        r=[0] * (HASH_SIZE * HASH_SIZE),
        g=[0] * (HASH_SIZE * HASH_SIZE),
        b=[0] * (HASH_SIZE * HASH_SIZE),
    )

    flat = rgb.reshape(-1, 3)
    for idx, (r, g, b) in enumerate(flat):
        color_pixels.r[idx] = int(r)
        color_pixels.g[idx] = int(g)
        color_pixels.b[idx] = int(b)

    return color_pixels


def _compute_dct_slow(pixels: list) -> list:
    """
    原始实现 - 纯 Python 四重循环（最慢版本）
    用于对比测试，展示为什么需要优化
    """
    n = int(np.sqrt(len(pixels)))
    if n * n != len(pixels):
        raise ValueError("像素长度不是平方数")

    result = [0.0] * (FREQ_SIZE * FREQ_SIZE)
    for u in range(FREQ_SIZE):
        for v in range(FREQ_SIZE):
            total = 0.0
            # 内层双重循环遍历所有像素
            for y in range(n):
                for x in range(n):
                    total += (
                        pixels[y * n + x]
                        * np.cos(((2 * x + 1) * u * np.pi) / (2 * n))
                        * np.cos(((2 * y + 1) * v * np.pi) / (2 * n))
                    )
            cu = 1 / np.sqrt(2) if u == 0 else 1
            cv = 1 / np.sqrt(2) if v == 0 else 1
            result[u * FREQ_SIZE + v] = ((2 * cu * cv) / n) * total

    return result


def _compute_dct(pixels: list) -> list:
    """计算 DCT - 使用 scipy 加速版"""
    try:
        from scipy.fftpack import dct

        n = int(np.sqrt(len(pixels)))
        if n * n != len(pixels):
            raise ValueError("像素长度不是平方数")

        # 转换为 numpy array 并 reshape
        img = np.array(pixels, dtype=np.float32).reshape(n, n)

        # 使用 scipy DCT (Type II) - 快 100-1000 倍
        dct_rows = dct(img, type=2, norm="ortho", axis=0)
        dct_2d = dct(dct_rows, type=2, norm="ortho", axis=1)

        # 只取前 FREQ_SIZE x FREQ_SIZE
        result = dct_2d[:FREQ_SIZE, :FREQ_SIZE].flatten().tolist()
        return result

    except ImportError:
        # 降级到纯 numpy 实现（用于没有 scipy 的环境）
        return _compute_dct_numpy(pixels)


def _compute_dct_numpy(pixels: list) -> list:
    """计算 DCT - 纯 numpy 向量化版（备用）"""
    n = int(np.sqrt(len(pixels)))
    if n * n != len(pixels):
        raise ValueError("像素长度不是平方数")

    img = np.array(pixels, dtype=np.float32).reshape(n, n)

    # 预计算 cos 表
    u = np.arange(FREQ_SIZE).reshape(-1, 1)
    v = np.arange(FREQ_SIZE).reshape(1, -1)
    x = np.arange(n).reshape(1, 1, -1)
    y = np.arange(n).reshape(1, -1, 1)

    # 向量化计算 cos
    cos_x = np.cos(((2 * x + 1) * u * np.pi) / (2 * n))  # (FREQ_SIZE, 1, n)
    cos_y = np.cos(((2 * y + 1) * v * np.pi) / (2 * n))  # (1, FREQ_SIZE, n)

    # 计算 DCT: 对每个 (u,v) 计算 sum(img * cos_x * cos_y)
    result = np.zeros((FREQ_SIZE, FREQ_SIZE), dtype=np.float32)
    for i in range(FREQ_SIZE):
        for j in range(FREQ_SIZE):
            total = np.sum(img * cos_x[i, 0, :] * cos_y[0, j, :])
            cu = 1 / np.sqrt(2) if i == 0 else 1
            cv = 1 / np.sqrt(2) if j == 0 else 1
            result[i, j] = ((2 * cu * cv) / n) * total

    return result.flatten().tolist()


def calculate_perceptual_hash(color_pixels: ColorPixels) -> np.ndarray:
    """计算感知哈希，返回 uint32 数组"""
    dct_r = _compute_dct(color_pixels.r)
    dct_g = _compute_dct(color_pixels.g)
    dct_b = _compute_dct(color_pixels.b)

    total_bits = 3 * (len(dct_r) - 1)
    buffer_len = int(np.ceil(total_bits / 32))
    arr = np.zeros(buffer_len, dtype=np.uint32)

    j = 0
    for dct in (dct_r, dct_g, dct_b):
        avg = float(np.mean(dct[1:]))
        for i in range(1, len(dct)):
            if dct[i] > avg + 1e-15:
                idx = j // 32
                bit = j % 32
                arr[idx] |= np.uint32(1 << bit)
            j += 1

    return arr


def calculate_similarity(hash1: np.ndarray, hash2: np.ndarray) -> float:
    """计算相似度（0~1），使用汉明距离 - 优化版"""
    if hash1.shape != hash2.shape:
        print("⚠️  哈希长度不一致")
    length = min(hash1.shape[0], hash2.shape[0])

    # 优化：XOR 后用 Python 3.10+ 的 int.bit_count()
    diff = hash1[:length] ^ hash2[:length]
    distance = sum(x.bit_count() for x in diff)

    return 1.0 - distance / (3 * (FREQ_SIZE * FREQ_SIZE - 1))


# ============ ADB 控制 ============


def discover_devices_simple():
    """自动发现 BlueStacks 设备"""
    try:
        # 尝试导入主项目的发现工具
        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
        from ptcgp_auto_v2.utils.device_discovery import discover_devices

        devices = discover_devices()
        if devices:
            return devices
    except Exception:
        pass

    # 备用方案：直接 adb devices
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            check=True,
        )
        devices = []
        for line in result.stdout.strip().split("\n")[1:]:
            if line.strip() and "device" in line:
                addr = line.split()[0]
                devices.append(addr)
        return devices
    except Exception:
        return []


class SimpleAdbController:
    """简化版 ADB 控制器"""

    def __init__(self, address: str):
        self.address = address
        subprocess.run(
            ["adb", "connect", self.address],
            capture_output=True,
            check=False,
        )

    def screenshot(self):
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


# ============ 核心测试逻辑 ============


def load_reference_hash(card_path: Path):
    """加载参考卡牌并计算哈希"""
    print(f"📂 加载参考卡牌: {card_path}")

    # 读取 webp 图片
    bgr = cv2.imread(str(card_path), cv2.IMREAD_UNCHANGED)
    if bgr is None:
        raise ValueError(f"无法读取图片: {card_path}")

    # 转换为 BGR（如果带 alpha）
    if bgr.shape[2] == 4:
        bgr = cv2.cvtColor(bgr, cv2.COLOR_BGRA2BGR)

    print(f"   图片尺寸: {bgr.shape[1]}x{bgr.shape[0]}")

    # 计算哈希
    color_pixels = bgr_to_color_pixels(bgr)
    hash_arr = calculate_perceptual_hash(color_pixels)

    print("✅ 参考哈希已计算")
    return hash_arr


def detect_and_crop_cards(
    model_path: str, pil_image: Image.Image, conf_threshold: float = 0.6
):
    """YOLO 检测并裁剪卡牌"""
    from ultralytics import YOLO

    print(f"\n🚀 加载 YOLO 模型: {model_path}")
    model = YOLO(model_path)

    # PIL -> numpy (RGB) -> BGR
    img_array = np.array(pil_image)

    # 处理 RGBA
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)

    img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

    print(f"📸 截图尺寸: {img_bgr.shape[1]}x{img_bgr.shape[0]}")

    # YOLO 检测
    results = model(img_bgr, verbose=False)
    result = results[0]

    if result.obb is None or len(result.obb) == 0:
        print("❌ 未检测到任何卡牌")
        return []

    print(f"\n🎯 检测到 {len(result.obb)} 个目标 (阈值: {conf_threshold})")

    cropped_cards = []

    for i, obb in enumerate(result.obb):
        conf = float(obb.conf[0].item())

        if conf < conf_threshold:
            print(f"   [{i + 1}] ❌ 置信度 {conf:.3f} < {conf_threshold}，跳过")
            continue

        print(f"   [{i + 1}] ✅ 置信度: {conf:.3f}")

        # 获取 OBB 角点并正确排序
        xyxyxyxy = obb.xyxyxyxy[0].cpu().numpy().reshape(-1, 2)
        corners = xyxyxyxy.astype(np.float32)

        # 按 y 坐标排序，然后按 x 坐标排序，确保顺序：左上、右上、右下、左下
        # 1. 计算中心点
        center_x = np.mean(corners[:, 0])
        center_y = np.mean(corners[:, 1])

        # 2. 根据相对于中心的位置排序
        # 左上: x < center, y < center
        # 右上: x > center, y < center
        # 右下: x > center, y > center
        # 左下: x < center, y > center
        sorted_corners = np.zeros((4, 2), dtype=np.float32)

        for corner in corners:
            x, y = corner[0], corner[1]
            if x < center_x and y < center_y:
                sorted_corners[0] = corner  # 左上
            elif x > center_x and y < center_y:
                sorted_corners[1] = corner  # 右上
            elif x > center_x and y > center_y:
                sorted_corners[2] = corner  # 右下
            else:
                sorted_corners[3] = corner  # 左下

        corners = sorted_corners

        # 透视变换裁剪
        target_w, target_h = 480, 670
        dst = np.array(
            [[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(corners, dst)
        warped = cv2.warpPerspective(img_bgr, matrix, (target_w, target_h))

        cropped_cards.append(
            {
                "index": i + 1,
                "confidence": conf,
                "corners": corners,
                "warped": warped,
            }
        )

    return cropped_cards


def calculate_card_hash(warped_bgr: np.ndarray):
    """计算卡牌哈希"""
    color_pixels = bgr_to_color_pixels(warped_bgr)
    return calculate_perceptual_hash(color_pixels)


def test_recognition(
    reference_card_path: Path,
    model_path: str,
    device_address: str,
    similarity_threshold: float = 0.97,
):
    """完整测试流程"""
    print("=" * 60)
    print("YOLO + 哈希匹配测试")
    print("=" * 60)

    # 1. 加载参考哈希
    reference_hash = load_reference_hash(reference_card_path)

    # 2. ADB 截图
    print(f"\n📱 连接设备: {device_address}")
    adb = SimpleAdbController(device_address)

    print("📸 正在截图...")
    screenshot = adb.screenshot()
    if not screenshot:
        print("❌ 截图失败")
        return

    print(f"✅ 截图成功: {screenshot.width}x{screenshot.height}")

    # 3. YOLO 检测并裁剪
    cropped_cards = detect_and_crop_cards(model_path, screenshot, conf_threshold=0.6)

    if not cropped_cards:
        print("\n❌ 没有通过阈值过滤的卡牌")
        return

    # 4. 计算每张卡牌的哈希并比对
    print(f"\n🔍 哈希比对 (阈值: {similarity_threshold})")
    print("-" * 60)

    # 保存裁剪图片供检查
    output_dir = Path("output/test_crops")
    output_dir.mkdir(parents=True, exist_ok=True)

    import time

    matches = []
    total_dct_time = 0
    total_compare_time = 0

    for card in cropped_cards:
        # 保存裁剪图片
        crop_path = output_dir / f"card_{card['index']}.jpg"
        cv2.imwrite(str(crop_path), card["warped"])

        # 转换为 ColorPixels（两种 DCT 共用）
        color_pixels = bgr_to_color_pixels(card["warped"])

        # ===== 版本 1: 原始慢版本（四重循环）=====
        t1 = time.perf_counter()
        dct_r_slow = _compute_dct_slow(color_pixels.r)
        dct_g_slow = _compute_dct_slow(color_pixels.g)
        dct_b_slow = _compute_dct_slow(color_pixels.b)
        # 计算哈希值（简化版，只用于对比）
        hash_slow = np.array(dct_r_slow[:3] + dct_g_slow[:3] + dct_b_slow[:3])
        t2 = time.perf_counter()
        time_slow = (t2 - t1) * 1000

        # ===== 版本 2: Scipy 快版本（FFT 优化）=====
        t1 = time.perf_counter()
        card_hash = calculate_perceptual_hash(color_pixels)
        t2 = time.perf_counter()
        time_fast = (t2 - t1) * 1000
        total_dct_time += time_fast

        # 比对相似度
        t1 = time.perf_counter()
        similarity = calculate_similarity(card_hash, reference_hash)
        t2 = time.perf_counter()
        compare_time = (t2 - t1) * 1000
        total_compare_time += compare_time

        # 计算速度提升倍数
        speedup = time_slow / time_fast if time_fast > 0 else 0

        status = "✅ 匹配" if similarity >= similarity_threshold else "❌ 不匹配"
        print(f"\n   卡牌 #{card['index']} {status}")
        print(f"      相似度: {similarity:.4f}")
        print(f"      🔴 原始 DCT: {time_slow:.1f}ms")
        print(f"      🟢 Scipy DCT: {time_fast:.1f}ms")
        print(f"      ⚡ 速度提升: {speedup:.0f}x")
        print(f"      ⏱️  哈希比对: {compare_time:.3f}ms")

        if similarity >= similarity_threshold:
            matches.append(
                {
                    "index": card["index"],
                    "confidence": card["confidence"],
                    "similarity": similarity,
                }
            )

    # 5. 结果汇总
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"   参考卡牌: {reference_card_path.name}")
    print(f"   检测到卡牌: {len(cropped_cards)} 张")
    print(f"   匹配成功: {len(matches)} 张")
    print("\n   ⏱️  性能统计:")
    print(
        f"      DCT 哈希计算: {total_dct_time:.1f}ms (平均 {total_dct_time / len(cropped_cards):.1f}ms/张)"
    )
    print(
        f"      哈希比对: {total_compare_time:.3f}ms (平均 {total_compare_time / len(cropped_cards):.3f}ms/张)"
    )

    if matches:
        print("\n   ✅ 匹配的卡牌:")
        for m in matches:
            print(
                f"      #{m['index']}: 置信度 {m['confidence']:.3f}, 相似度 {m['similarity']:.4f}"
            )
    else:
        print(f"\n   ⚠️  没有匹配的卡牌 (相似度阈值: {similarity_threshold})")

    print("\n" + "=" * 60)


def main():
    # 配置路径
    reference_card = Path("data/raw/cards/A1-183.webp")
    # 模型在根目录 runs/obb/ 下
    model_path = "../runs/obb/output/models/card_obb5/weights/best.pt"

    # 检查文件
    if not reference_card.exists():
        print(f"❌ 参考卡牌不存在: {reference_card}")
        sys.exit(1)

    if not Path(model_path).exists():
        print(f"❌ 模型不存在: {model_path}")
        sys.exit(1)

    # 自动发现设备
    print("🔍 自动发现ADB设备...")
    devices = discover_devices_simple()
    if not devices:
        print("❌ 未发现任何ADB设备")
        print("💡 请确保 BlueStacks 正在运行")
        sys.exit(1)

    device_address = devices[0]
    print(f"✅ 发现设备: {device_address}")
    if len(devices) > 1:
        print(f"   (共发现 {len(devices)} 个设备，使用第一个)")

    # 执行测试
    test_recognition(
        reference_card_path=reference_card,
        model_path=model_path,
        device_address=device_address,
        similarity_threshold=0.97,
    )


if __name__ == "__main__":
    main()
