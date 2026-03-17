"""
交互式区域选择工具

使用 OpenCV cv2.selectROI() 显示截图，让用户用鼠标框选区域，保存为模板。
"""

import json
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np
from PIL import Image

# 模板保存目录
TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates"

# ROI 缓存文件
ROI_CACHE_FILE = Path("/tmp/ptcgp_crop_roi_cache.json")


def _load_cached_roi() -> Optional[Tuple[int, int, int, int]]:
    """加载缓存的 ROI"""
    if not ROI_CACHE_FILE.exists():
        return None
    try:
        with open(ROI_CACHE_FILE, "r") as f:
            data = json.load(f)
            return tuple(data["roi"])
    except Exception:
        return None


def _save_cached_roi(roi: Tuple[int, int, int, int]):
    """保存 ROI 到缓存"""
    try:
        with open(ROI_CACHE_FILE, "w") as f:
            json.dump({"roi": list(roi)}, f)
    except Exception:
        pass


def select_region(
    image: Image.Image,
    window_name: str = "Select Region",
) -> Optional[Tuple[int, int, int, int]]:
    """
    打开交互式区域选择器

    Args:
        image: PIL 图像对象
        window_name: 窗口标题

    Returns:
        选中的区域坐标 (x, y, w, h)，取消则返回 None
    """
    # PIL 转 OpenCV 格式 (RGB -> BGR)
    cv_image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    # 缩放显示（1080p 太大）
    scale = 0.6
    display_image = cv2.resize(cv_image, None, fx=scale, fy=scale)

    # 创建可调整大小的窗口
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, display_image.shape[1], display_image.shape[0])

    print("提示: 拖拽框选区域，按 ENTER/SPACE 确认，按 C 取消，按 ESC 退出")

    # 选择区域
    try:
        roi = cv2.selectROI(
            window_name, display_image, fromCenter=False, showCrosshair=True
        )
    except Exception as e:
        print(f"选择区域时出错: {e}")
        cv2.destroyAllWindows()
        return None
    finally:
        cv2.destroyAllWindows()
        cv2.waitKey(1)  # 确保窗口关闭

    # 检查是否取消
    if roi == (0, 0, 0, 0):
        print("已取消选择")
        return None

    # 转换回原始坐标
    x, y, w, h = roi
    x = int(x / scale)
    y = int(y / scale)
    w = int(w / scale)
    h = int(h / scale)

    print(f"选中区域: ({x}, {y}) - ({x + w}, {y + h})  尺寸: {w}x{h}")

    # 保存到缓存
    _save_cached_roi((x, y, w, h))

    return (x, y, w, h)


def select_and_save_template(
    image: Image.Image,
    template_name: str = None,
) -> Optional[Path]:
    """
    选择区域并保存为模板

    Args:
        image: PIL 图像对象
        template_name: 模板名称（不含扩展名），如果为 None 则交互式输入

    Returns:
        保存的模板路径，取消则返回 None
    """
    roi = select_region(image)
    if roi is None:
        return None

    x, y, w, h = roi

    # 裁剪区域
    cropped = image.crop((x, y, x + w, y + h))

    # 获取模板名称
    if template_name is None:
        template_name = input("请输入模板名称（不含扩展名）: ").strip()
        if not template_name:
            print("名称为空，已取消")
            return None

    # 确保模板目录存在
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

    # 保存模板
    template_path = TEMPLATES_DIR / f"{template_name}.png"
    cropped.save(template_path)

    print(f"模板已保存: {template_path}")
    print(f"区域坐标: ({x}, {y}) - ({x + w}, {y + h})")
    print(f"尺寸: {w}x{h}")

    return template_path
