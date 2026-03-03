# -*- coding: utf-8 -*-
"""
卡包图片测试模块

提供卡包封面图片的下载、对比、匹配测试功能。
"""

import sys
from pathlib import Path
from typing import List, Optional, Tuple

from io import BytesIO
from PIL import Image, ImageDraw

# 确保能导入 v2 模块
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from ptcgp_auto_v2.utils.pack_image_manager import (
    PackImageManager,
    PACK_CROP_RATIO,
)


def test_download(booster_names: List[str]) -> dict[str, bool]:
    """
    测试下载指定卡包图片

    Args:
        booster_names: 子包名称列表

    Returns:
        字典 {name: success}
    """
    print(f"\n=== 测试下载 {len(booster_names)} 个卡包 ===")

    manager = PackImageManager()
    results = {}

    for name in booster_names:
        success = manager.ensure_pack_ready(name)
        results[name] = success
        status = "✓" if success else "✗"
        print(f"  [{status}] {name}")

    return results


def test_compare(booster_name: str, old_templates_dir: str = "templates/packs"):
    """
    对比公共图片与现有手动模板

    Args:
        booster_name: 子包名称
        old_templates_dir: 旧模板目录路径
    """
    print(f"\n=== 对比卡包: {booster_name} ===")

    manager = PackImageManager()

    # 1. 确保新图片已下载
    if not manager.ensure_pack_ready(booster_name):
        print(f"✗ 下载新图片失败: {booster_name}")
        return

    new_path = manager.get_pack_path(booster_name)
    new_img = Image.open(new_path)

    print(f"\n新图片（公共资源处理后）:")
    print(f"  路径: {new_path}")
    print(f"  尺寸: {new_img.width}x{new_img.height}")

    # 2. 查找旧模板
    old_dir = Path(old_templates_dir)
    old_candidates = list(old_dir.rglob(f"{booster_name}.png"))

    if not old_candidates:
        print(f"\n⚠ 未找到旧模板: {booster_name}.png")
        print(f"   搜索路径: {old_dir}")
        return

    old_path = old_candidates[0]
    old_img = Image.open(old_path)

    print(f"\n旧模板（手动裁剪）:")
    print(f"  路径: {old_path}")
    print(f"  尺寸: {old_img.width}x{old_img.height}")

    # 3. 计算缩放比例建议
    if old_img.width > 0 and new_img.width > 0:
        scale_w = old_img.width / new_img.width
        scale_h = old_img.height / new_img.height
        print(f"\n缩放比例建议:")
        print(f"  宽度比: {scale_w:.3f}")
        print(f"  高度比: {scale_h:.3f}")
        print(f"  平均值: {(scale_w + scale_h) / 2:.3f}")

    # 4. 显示裁剪参数
    print(f"\n当前裁剪参数:")
    print(f"  CROP_RATIO: {PACK_CROP_RATIO}")
    print(f"  注: 模板只裁剪不缩放，由匹配器动态缩放")


def test_match(
    adb_controller, booster_name: str, scale: float = None, threshold: float = 0.8
) -> Optional[Tuple[float, Tuple[int, int, int, int]]]:
    """
    在设备上测试模板匹配效果

    Args:
        adb_controller: ADB 控制器
        booster_name: 子包名称
        scale: 指定缩放比例（None 则自动扫描）
        threshold: 匹配阈值

    Returns:
        (confidence, box) 或 None
    """
    print(f"\n=== 匹配测试: {booster_name} ===")

    # 1. 准备资源
    manager = PackImageManager()
    if not manager.ensure_pack_ready(booster_name):
        print(f"✗ 准备资源失败: {booster_name}")
        return None

    # 2. 截图
    print("正在截图...")
    screenshot = adb_controller.screenshot()
    if not screenshot:
        print("✗ 截图失败")
        return None

    # 3. 加载模板到 TemplateMatcher
    from ptcgp_auto_v2.infra.template import TemplateMatcher
    import cv2

    matcher = TemplateMatcher()
    if screenshot.width > 0:
        matcher.set_screen_width(screenshot.width)

    pack_path = manager.get_pack_path(booster_name)
    template_name = manager.get_template_name(booster_name)

    # 加载模板（使用标准 load_template，与正式代码一致，会进行预缩放）
    if not matcher.load_template(f"{template_name}.png", is_pack_template=True):
        print(f"✗ 加载模板失败: {template_name}")
        return None
    print(f"LOADED: {template_name}")

    # 4. 执行匹配
    if scale:
        # 指定比例匹配
        print(f"使用指定缩放比例: {scale}")
        match = matcher.find_with_scale(screenshot, template_name, scale, threshold=threshold)
        if match:
            print(f"✓ 匹配成功! 置信度: {match.confidence:.4f}, 位置: {match.box}")
            return (match.confidence, match.box)
        else:
            confidence = matcher.get_confidence(screenshot, template_name)
            print(f"✗ 未匹配. 置信度: {confidence:.4f} (阈值: {threshold})")
            return None
    else:
        # 自动扫描最佳比例
        print("自动扫描最佳缩放比例...")
        from ptcgp_auto_v2.tools.card_matcher import scan_best_scale_with_matcher

        best_scale, best_conf = scan_best_scale_with_matcher(matcher, screenshot, template_name)
        print(f"\n最佳比例: {best_scale:.3f}, 置信度: {best_conf:.4f}")

        if best_conf >= threshold:
            match = matcher.find_with_scale(screenshot, template_name, best_scale)
            if match:
                print(f"✓ 匹配成功! 位置: {match.box}")
                print(f"\n推荐命令:")
                print(
                    f"  python debug_tool.py -a PORT --test-pack match --booster {booster_name} --scale {best_scale:.3f}"
                )
                return (best_conf, match.box)
        print(f"✗ 未达到阈值. 建议调整裁剪参数后重试")
        return None


def test_batch(
    adb_controller,
    boosters: List[str] = None,
    scale: float = None,
    threshold: float = 0.8,
) -> dict[str, dict]:
    """
    批量测试卡包匹配

    Args:
        adb_controller: ADB 控制器
        boosters: 卡包列表（None 则使用所有已下载的）
        scale: 统一缩放比例（None 则对每个卡包自动扫描）
        threshold: 匹配阈值

    Returns:
        测试结果字典
    """
    manager = PackImageManager()

    if boosters is None:
        boosters = manager.list_available_packs()

    if not boosters:
        print("\n✗ 没有可测试的卡包")
        return {}

    print(f"\n=== 批量测试 {len(boosters)} 个卡包 ===")
    if scale:
        print(f"统一缩放比例: {scale}")
    else:
        print("自动扫描最佳比例")

    results = {}
    success_count = 0

    for i, booster in enumerate(boosters, 1):
        print(f"\n[{i}/{len(boosters)}] {booster}:")
        result = test_match(adb_controller, booster, scale=scale, threshold=threshold)

        if result:
            confidence, box = result
            results[booster] = {
                "success": True,
                "confidence": confidence,
                "box": box,
                "scale": scale,
            }
            success_count += 1
        else:
            results[booster] = {"success": False}

    # 汇总
    print(f"\n{'=' * 50}")
    print(f"测试结果汇总:")
    print(f"  总计: {len(boosters)}")
    print(f"  成功: {success_count}")
    print(f"  失败: {len(boosters) - success_count}")
    print(f"  成功率: {success_count / len(boosters) * 100:.1f}%")

    # 显示失败项
    failed = [k for k, v in results.items() if not v["success"]]
    if failed:
        print(f"\n失败的卡包: {', '.join(failed)}")

    return results


def list_all_packs():
    """列出所有已下载的卡包"""
    manager = PackImageManager()
    packs = manager.list_available_packs()

    print(f"\n=== 已下载卡包 ({len(packs)} 个) ===")
    for i, pack in enumerate(packs, 1):
        print(f"  {i}. {pack}")

    return packs


def clear_packs(booster_name: str = None):
    """
    清除卡包图片

    Args:
        booster_name: 指定卡包（None 则清除全部）
    """
    manager = PackImageManager()

    if booster_name:
        if manager.delete_pack(booster_name):
            print(f"✓ 已删除: {booster_name}")
        else:
            print(f"✗ 未找到: {booster_name}")
    else:
        count = manager.clear_all()
        print(f"✓ 已清除 {count} 个卡包图片")


def test_crop_adjust(
    booster_name: str,
    adb_controller=None,
    threshold: float = 0.8,
    scale: float = None,
):
    """
    交互式裁剪参数调整工具 - 实时调整裁剪比例

    使用 OpenCV 滑块界面，实时调整左右上下裁剪比例，
    立即看到裁剪效果，可测试匹配。

    Args:
        booster_name: 卡包名称（如 Charizard）
        adb_controller: ADB 控制器（可选，用于匹配测试）
        threshold: 匹配阈值
        scale: 指定缩放比例（None 则自动扫描）

    Returns:
        (best_confidence, crop_ratio, best_scale) 或 None
    """
    import cv2
    import numpy as np
    import tempfile
    import os

    print(f"\n{'=' * 60}")
    print(f"交互式裁剪调整工具: {booster_name}")
    print(f"{'=' * 60}")

    # 1. 下载原始 WebP 图片（不处理）
    print("\n[1/3] 下载原始 WebP 图片...")
    with PackImageManager() as manager:
        image_data = manager.download_pack_image(booster_name)
    if not image_data:
        print("✗ 下载失败：所有源都不可用")
        return None

    try:
        public_img = Image.open(BytesIO(image_data))
        pw, ph = public_img.size
        print(f"✓ 原始 WebP: {pw}x{ph}")
    except Exception as e:
        print(f"✗ 图片解码异常: {e}")
        return None

    # 获取设备截图（如果有 ADB）
    screenshot = None
    if adb_controller:
        print("\n[2/3] 获取设备截图...")
        screenshot = adb_controller.screenshot()
        if screenshot:
            print(f"✓ 截图尺寸: {screenshot.width}x{screenshot.height}")
        else:
            print("⚠ 截图失败，将仅进行裁剪预览")

    # 3. 创建交互式裁剪界面
    print("\n[3/3] 启动交互式裁剪界面...")
    print("操作说明:")
    print("  - 拖动滑块调整裁剪比例")
    print("  - 实时预览裁剪效果")
    print("  - 按 't' 测试匹配（需要 ADB）")
    print("  - 按 's' 保存当前配置")
    print("  - 按 'r' 重置为默认值")
    print("  - 按 'q' 退出")

    # 默认值（当前配置）
    from ptcgp_auto_v2.utils.pack_image_manager import PACK_CROP_RATIO

    default_left = int(PACK_CROP_RATIO[0] * 100)  # 5
    default_top = int(PACK_CROP_RATIO[1] * 100)  # 0
    default_right = int(PACK_CROP_RATIO[2] * 100)  # 95
    default_bottom = int(PACK_CROP_RATIO[3] * 100)  # 62

    # 创建窗口和滑块
    window_name = f"Crop Adjust - {booster_name}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    # 创建滑块（值范围 0-100，表示百分比）
    cv2.createTrackbar("Left %", window_name, default_left, 20, lambda x: None)
    cv2.createTrackbar("Top %", window_name, default_top, 30, lambda x: None)
    cv2.createTrackbar("Right %", window_name, default_right, 100, lambda x: None)
    cv2.createTrackbar("Bottom %", window_name, default_bottom, 100, lambda x: None)

    current_crop_ratio = PACK_CROP_RATIO
    best_result = None

    # 从 PIL 转换为 OpenCV 格式（RGB -> BGR）
    def pil_to_cv(img):
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    # 应用裁剪（不缩放，匹配 PackImageManager 的处理）
    def apply_crop(img, left_pct, top_pct, right_pct, bottom_pct):
        w, h = img.size
        left = int(w * left_pct / 100)
        top = int(h * top_pct / 100)
        right = int(w * right_pct / 100)
        bottom = int(h * bottom_pct / 100)

        # 确保有效范围
        left = max(0, min(left, w - 1))
        top = max(0, min(top, h - 1))
        right = max(left + 1, min(right, w))
        bottom = max(top + 1, min(bottom, h))

        cropped = img.crop((left, top, right, bottom))

        # 转换为 RGB
        if cropped.mode == "RGBA":
            background = Image.new("RGB", cropped.size, (255, 255, 255))
            background.paste(cropped, mask=cropped.split()[3])
            cropped = background
        elif cropped.mode != "RGB":
            cropped = cropped.convert("RGB")

        # 注: 不再缩放，与 PackImageManager 保持一致
        # 模板匹配器会在加载时自动缩放

        return cropped, (left, top, right, bottom)

    # 测试匹配
    def test_matching(crop_ratio, fixed_scale=None):
        if not adb_controller or not screenshot:
            print("⚠ 无法测试：没有 ADB 连接或截图")
            return None

        # 应用裁剪
        processed, _ = apply_crop(
            public_img,
            crop_ratio[0] * 100,
            crop_ratio[1] * 100,
            crop_ratio[2] * 100,
            crop_ratio[3] * 100,
        )

        # 保存临时文件
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, f"{booster_name}_adjust.png")
        processed.save(temp_path)

        # 加载并测试匹配
        from ptcgp_auto_v2.infra.template import TemplateMatcher
        from ptcgp_auto_v2.tools.card_matcher import scan_best_scale_with_matcher
        import cv2

        matcher = TemplateMatcher()
        if screenshot.width > 0:
            matcher.set_screen_width(screenshot.width)

        template_name = f"{booster_name}_adjust"
        template_img = cv2.imread(temp_path)
        if template_img is None:
            os.remove(temp_path)
            os.rmdir(temp_dir)
            return None

        # 预缩放到屏幕比例（与正式代码一致）
        scale_ratio = screenshot.width / matcher.base_width
        if abs(scale_ratio - 1.0) > 0.01:
            new_w = int(template_img.shape[1] * scale_ratio)
            new_h = int(template_img.shape[0] * scale_ratio)
            template_img = cv2.resize(template_img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        matcher.templates[template_name] = template_img

        # 如果指定了固定 scale，直接使用；否则自动扫描
        if fixed_scale:
            best_scale = fixed_scale
            match = matcher.find_with_scale(screenshot, template_name, best_scale)
            best_conf = match.confidence if match else 0.0
        else:
            best_scale, best_conf = scan_best_scale_with_matcher(
                matcher, screenshot, template_name
            )

        # 清理
        os.remove(temp_path)
        os.rmdir(temp_dir)

        return best_conf, best_scale

    # 准备原始图片（转换为 RGB）
    if public_img.mode == "RGBA":
        bg = Image.new("RGB", public_img.size, (255, 255, 255))
        bg.paste(public_img, mask=public_img.split()[3])
        original_rgb = bg
    elif public_img.mode != "RGB":
        original_rgb = public_img.convert("RGB")
    else:
        original_rgb = public_img

    # 主循环
    while True:
        # 获取滑块值
        left_pct = cv2.getTrackbarPos("Left %", window_name)
        top_pct = cv2.getTrackbarPos("Top %", window_name)
        right_pct = cv2.getTrackbarPos("Right %", window_name)
        bottom_pct = cv2.getTrackbarPos("Bottom %", window_name)

        # 确保合理性
        right_pct = max(left_pct + 10, right_pct)
        bottom_pct = max(top_pct + 10, bottom_pct)

        # 转换为比例
        crop_ratio = (left_pct / 100, top_pct / 100, right_pct / 100, bottom_pct / 100)
        current_crop_ratio = crop_ratio

        # 应用裁剪
        processed, crop_coords = apply_crop(
            public_img, left_pct, top_pct, right_pct, bottom_pct
        )

        # 创建左侧：原始图片 + 裁剪框
        left_img = original_rgb.copy()
        left_cv = pil_to_cv(left_img)

        # 在原始图片上画裁剪框（红色）
        x1, y1, x2, y2 = crop_coords
        cv2.rectangle(left_cv, (x1, y1), (x2, y2), (0, 0, 255), 2)

        # 添加标签
        cv2.putText(
            left_cv,
            "Original (with crop box)",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )

        # 创建右侧：裁剪后的结果
        right_cv = pil_to_cv(processed)

        # 添加文字信息到右侧图片
        info_lines = [
            f"Crop: ({crop_ratio[0]:.2f}, {crop_ratio[1]:.2f}, {crop_ratio[2]:.2f}, {crop_ratio[3]:.2f})",
            f"Raw: {crop_coords[2] - crop_coords[0]}x{crop_coords[3] - crop_coords[1]}",
            f"Final: {processed.width}x{processed.height}",
            f"Aspect: {processed.width / processed.height:.3f}",
            "",
            "Keys: t=test  s=save  r=reset  q=quit",
        ]

        y_offset = 30
        for line in info_lines:
            cv2.putText(
                right_cv,
                line,
                (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            y_offset += 25

        # 合并左右两张图片（并排显示）
        # 调整高度一致
        target_height = max(left_cv.shape[0], right_cv.shape[0])
        target_height = max(target_height, 400)  # 最小高度

        # 缩放左侧图片
        left_scale = target_height / left_cv.shape[0]
        left_width = int(left_cv.shape[1] * left_scale)
        left_resized = cv2.resize(left_cv, (left_width, target_height))

        # 缩放右侧图片
        right_scale = target_height / right_cv.shape[0]
        right_width = int(right_cv.shape[1] * right_scale)
        right_resized = cv2.resize(right_cv, (right_width, target_height))

        # 水平拼接
        display_img = np.hstack((left_resized, right_resized))

        # 显示
        cv2.imshow(window_name, display_img)

        # 处理按键
        key = cv2.waitKey(100) & 0xFF

        if key == ord("q"):
            print("\n退出裁剪调整")
            break

        elif key == ord("r"):
            # 重置
            cv2.setTrackbarPos("Left %", window_name, default_left)
            cv2.setTrackbarPos("Top %", window_name, default_top)
            cv2.setTrackbarPos("Right %", window_name, default_right)
            cv2.setTrackbarPos("Bottom %", window_name, default_bottom)
            print("\n已重置为默认值")

        elif key == ord("t"):
            # 测试匹配
            print("\n正在测试匹配...")
            result = test_matching(crop_ratio, fixed_scale=scale)
            if result:
                conf, scale = result
                print(f"  匹配结果: 置信度={conf:.4f}, 缩放={scale:.3f}")
                if conf >= threshold:
                    print(f"  ✓ 匹配成功！")
                    best_result = (conf, crop_ratio, scale)
                else:
                    print(f"  ✗ 未达阈值 ({threshold})")
            else:
                print("  ✗ 匹配失败")

        elif key == ord("s"):
            # 保存配置
            print(f"\n{'=' * 60}")
            print(f"当前裁剪配置:")
            print(f"  PACK_CROP_RATIO = {crop_ratio}")
            print(
                f"  原始尺寸: {crop_coords[2] - crop_coords[0]}x{crop_coords[3] - crop_coords[1]}"
            )
            print(f"  处理后: {processed.width}x{processed.height}")
            print(f"  宽高比: {processed.width / processed.height:.3f}")
            print(f"{'=' * 60}")

    cv2.destroyAllWindows()
    cv2.waitKey(1)

    # 返回最佳结果
    if best_result:
        print(f"\n最佳匹配结果:")
        print(f"  置信度: {best_result[0]:.4f}")
        print(f"  裁剪参数: {best_result[1]}")
        print(f"  缩放比例: {best_result[2]:.3f}")
        return best_result

    return None


def test_roi_interactive(
    adb_controller,
    booster_name: str,
    threshold: float = 0.8,
    scale: float = None,
):
    """
    交互式 ROI 测试工具 - 使用裁剪调整工具确定参数

    Args:
        adb_controller: ADB 控制器
        booster_name: 卡包名称（如 Charizard）
        threshold: 匹配阈值
        scale: 指定缩放比例（None 则自动扫描）

    Returns:
        test_crop_adjust 的结果
    """
    # 直接调用新的交互式裁剪工具
    return test_crop_adjust(booster_name, adb_controller, threshold, scale)


def test_quick_match(adb_controller, threshold: float = 0.8):
    """
    快速测试模式 - 交互式选择卡包并立即测试匹配

    工作流程:
    1. 列出所有可用卡包
    2. 用户选择卡包名称
    3. 下载并处理卡包图片
    4. 与当前 ADB 画面测试最佳匹配

    Args:
        adb_controller: ADB 控制器
        threshold: 匹配阈值
    """
    print(f"\n{'=' * 60}")
    print(f"快速匹配测试模式")
    print(f"{'=' * 60}")

    # 1. 列出所有可用卡包（从 GitHub 源）
    manager = PackImageManager()

    # 所有可能的卡包名称（基于 GitHub 源）
    all_packs = [
        "Arceus",
        "Charizard",
        "Celebi",
        "Crimson Blaze",
        "Deluxe",
        "Dialga",
        "Eevee",
        "Extradimensional",
        "Gardevoir",
        "Giratina",
        "Ho-Oh",
        "Lugia",
        "Lunala",
        "Mega Altaria",
        "Mega Blaziken",
        "Mega Gyarados",
        "Mew",
        "Mewtwo",
        "Palkia",
        "Pikachu",
        "Secluded",
        "Shining",
        "Solgaleo",
    ]

    # 获取已下载的卡包
    downloaded_packs = manager.list_available_packs()

    if not downloaded_packs:
        print("\n本地没有已下载的卡包，将按需下载")

    print(f"\n可用卡包 ({len(all_packs)} 个):")
    for i, pack in enumerate(all_packs, 1):
        status = "✓" if pack in downloaded_packs else " "
        print(f"  {i}. [{status}] {pack}")

    # 2. 交互式选择
    print("\n请输入卡包名称或编号 (回车退出):")
    user_input = input("> ").strip()

    if not user_input:
        print("已取消")
        return

    # 尝试解析为编号
    try:
        idx = int(user_input) - 1
        if 0 <= idx < len(all_packs):
            booster_name = all_packs[idx]
        else:
            print(f"✗ 无效编号: {user_input}")
            return
    except ValueError:
        # 直接作为名称
        booster_name = user_input

    print(f"\n选择的卡包: {booster_name}")

    # 3. 确保卡包已准备
    if not manager.ensure_pack_ready(booster_name):
        print(f"✗ 准备卡包失败: {booster_name}")
        return

    # 4. 截图
    print("正在截图...")
    screenshot = adb_controller.screenshot()
    if not screenshot:
        print("✗ 截图失败")
        return

    # 5. 加载模板并测试匹配
    from ptcgp_auto_v2.infra.template import TemplateMatcher
    from ptcgp_auto_v2.tools.card_matcher import scan_best_scale_with_matcher
    import cv2

    matcher = TemplateMatcher()
    if screenshot.width > 0:
        matcher.set_screen_width(screenshot.width)

    pack_path = manager.get_pack_path(booster_name)
    template_name = manager.get_template_name(booster_name)

    # 加载模板（使用标准 load_template，与正式代码一致，会进行预缩放）
    if not matcher.load_template(f"{template_name}.png", is_pack_template=True):
        print(f"✗ 加载模板失败: {template_name}")
        return
    print(f"LOADED: {template_name}")

    # 6. 扫描最佳匹配
    print(f"\n正在测试匹配...")
    best_scale, best_conf = scan_best_scale_with_matcher(matcher, screenshot, template_name)

    print(f"\n{'=' * 60}")
    print(f"测试结果: {booster_name}")
    print(f"{'=' * 60}")
    print(f"  缩放比例: {best_scale:.3f}")
    print(f"  置信度: {best_conf:.4f}")

    if best_conf >= threshold:
        print(f"  ✓ 匹配成功！")
        print(f"\n推荐命令:")
        print(
            f"  python debug_tool.py -a PORT --test-pack match --booster {booster_name} --scale {best_scale:.3f}"
        )
    else:
        print(f"  ✗ 未达阈值 ({threshold})")
        print(f"\n建议: 尝试调整裁剪参数")
        print(
            f"  python debug_tool.py -a PORT --test-pack roi --booster {booster_name}"
        )

    print(f"{'=' * 60}")

    return best_conf, best_scale
