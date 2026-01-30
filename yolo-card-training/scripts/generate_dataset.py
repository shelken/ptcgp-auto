#!/usr/bin/env python3
"""
生成 YOLO OBB 合成数据集
基于 1vcian 的 trainCreator.py 核心逻辑

生成 640x640 图像，每张 1-5 张卡牌，带旋转边界框标注
"""

import argparse
import math
import os
import random
from pathlib import Path

import yaml
from PIL import Image
from tqdm import tqdm


class DatasetGenerator:
    """合成数据集生成器"""

    def __init__(self, cards_dir: Path, backgrounds_dir: Path, output_dir: Path):
        self.cards_dir = cards_dir
        self.backgrounds_dir = backgrounds_dir
        self.output_dir = output_dir

        # 支持多种图片格式（包括 webp）
        self.cards_files = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            self.cards_files.extend(list(cards_dir.glob(ext)))

        self.backgrounds_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
            self.backgrounds_files.extend(list(backgrounds_dir.glob(ext)))

        print(
            f"📊 找到 {len(self.cards_files)} 张卡牌, {len(self.backgrounds_files)} 张背景"
        )

        # 如果没有背景图片，创建纯色背景
        if len(self.backgrounds_files) == 0:
            print("⚠️  未找到背景图片，将使用纯色背景")
            self.use_solid_background = True
        else:
            self.use_solid_background = False

    def calculate_iou(self, box1, box2):
        """计算 IoU（Intersection over Union）"""
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
        union = area1 + area2 - intersection

        return intersection / union if union > 0 else 0

    def place_card(
        self,
        card_img: Image.Image,
        bg_img: Image.Image,
        existing_boxes: list,
        scale_factor: float = None,
    ):
        """在背景上放置一张卡牌，返回图像和 OBB 标注"""
        bg_w, bg_h = bg_img.size
        card_w, card_h = card_img.size

        # 缩放卡牌（限制最大比例，确保旋转后不会超出背景）
        if scale_factor is None:
            # 开包场景：卡牌较大，但最大不超过背景的 40%
            scale_factor = random.uniform(0.15, 0.35)

        # 确保缩放后卡牌不会太大（考虑旋转后需要额外空间）
        max_scale = min(0.4, 0.8 * min(bg_w, bg_h) / max(card_w, card_h))
        scale_factor = min(scale_factor, max_scale)

        new_w = int(bg_w * scale_factor)
        new_h = int(card_h * (new_w / card_w))

        # 确保最小尺寸
        new_w = max(new_w, 50)
        new_h = max(new_h, 50)

        card_img = card_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 旋转（开包场景倾斜角度较小）
        angle = random.uniform(-15, 15)
        card_img = card_img.rotate(
            angle, expand=True, resample=Image.Resampling.BICUBIC
        )
        rot_w, rot_h = card_img.size

        # 安全检查：如果旋转后还是太大，跳过这张卡牌
        if rot_w >= bg_w or rot_h >= bg_h:
            return None, None, None

        # 尝试放置（避免重叠）
        max_attempts = 50
        for _ in range(max_attempts):
            x = random.randint(0, bg_w - rot_w)
            y = random.randint(0, bg_h - rot_h)

            # 检查重叠
            new_box = [x, y, x + rot_w, y + rot_h]
            overlap = any(
                self.calculate_iou(new_box, box) > 0.1 for box in existing_boxes
            )

            if not overlap:
                # 放置卡牌
                result = bg_img.copy()
                if card_img.mode == "RGBA":
                    result.paste(card_img, (x, y), card_img.split()[3])
                else:
                    result.paste(card_img, (x, y))

                # 计算 OBB 角点（归一化 0-1）
                center_x = (x + rot_w / 2) / bg_w
                center_y = (y + rot_h / 2) / bg_h

                # 原始尺寸（未旋转）的半宽高
                half_w = new_w / 2 / bg_w
                half_h = new_h / 2 / bg_h

                # 四个角点（相对于中心）
                corners = [
                    (-half_w, -half_h),  # 左上
                    (half_w, -half_h),  # 右上
                    (half_w, half_h),  # 右下
                    (-half_w, half_h),  # 左下
                ]

                # 应用旋转
                angle_rad = math.radians(-angle)
                rotated_corners = []
                for cx, cy in corners:
                    rx = cx * math.cos(angle_rad) - cy * math.sin(angle_rad)
                    ry = cx * math.sin(angle_rad) + cy * math.cos(angle_rad)
                    rotated_corners.extend([center_x + rx, center_y + ry])

                # YOLO OBB 格式: class x1 y1 x2 y2 x3 y3 x4 y4
                yolo_bbox = [0] + [round(c, 6) for c in rotated_corners]

                return result, yolo_bbox, new_box

        return None, None, None

    def generate_image(self, idx: int, split: str, num_cards: int = None):
        """生成单张数据集图像"""
        if num_cards is None:
            num_cards = random.choices(
                [1, 2, 3, 4, 5], weights=[0.1, 0.2, 0.3, 0.3, 0.1]
            )[0]

        # 选择或创建背景
        if self.use_solid_background:
            # 使用纯色背景（模拟游戏界面）
            # 随机颜色，避免纯白（255,255,255）
            bg_color = (
                random.randint(200, 240),  # R
                random.randint(200, 240),  # G
                random.randint(200, 240),  # B
                255,  # Alpha
            )
            bg_img = Image.new("RGBA", (640, 640), bg_color)
        else:
            # 使用真实背景图片
            bg_file = random.choice(self.backgrounds_files)
            bg_img = Image.open(bg_file).convert("RGBA")
            # 缩放到 640x640
            bg_img = bg_img.resize((640, 640), Image.Resampling.LANCZOS)

        existing_boxes = []
        yolo_bboxes = []

        # 放置卡牌
        for i in range(num_cards):
            card_file = random.choice(self.cards_files)
            card_img = Image.open(card_file).convert("RGBA")

            # 开包场景：1-3张时卡牌较大，4-5张时较小
            if num_cards <= 2:
                scale = random.uniform(0.5, 0.7)
            elif num_cards == 3:
                scale = random.uniform(0.35, 0.5)
            else:
                scale = random.uniform(0.25, 0.35)

            result, yolo_bbox, box = self.place_card(
                card_img, bg_img, existing_boxes, scale
            )

            if result is not None:
                bg_img = result
                existing_boxes.append(box)
                yolo_bboxes.append(yolo_bbox)

        # 保存图像
        img_path = self.output_dir / "images" / split / f"image_{idx:06d}.jpg"
        bg_img.convert("RGB").save(img_path, quality=95)

        # 保存标注
        label_path = self.output_dir / "labels" / split / f"image_{idx:06d}.txt"
        with open(label_path, "w") as f:
            for bbox in yolo_bboxes:
                f.write(" ".join(map(str, bbox)) + "\n")

        return img_path

    def generate_dataset(self, total: int = 10000, train_ratio=0.8, val_ratio=0.1):
        """生成完整数据集"""
        print(f"🎯 生成 {total} 张合成图像...")

        # 创建目录
        for split in ["train", "val", "test"]:
            (self.output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (self.output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

        # 计算数量
        train_num = int(total * train_ratio)
        val_num = int(total * val_ratio)
        test_num = total - train_num - val_num

        splits = [
            ("train", train_num, 0),
            ("val", val_num, train_num),
            ("test", test_num, train_num + val_num),
        ]

        for split, num, start_idx in splits:
            print(f"\n📦 生成 {split} 集 ({num} 张)...")
            for i in tqdm(range(num), desc=split):
                self.generate_image(start_idx + i, split)

        print(f"\n✅ 数据集生成完成！")


def create_yaml(output_dir: Path):
    """创建 data.yaml 配置文件"""
    data = {
        "path": str(output_dir.absolute()),
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": 1,
        "names": ["pokemon_card"],
    }

    yaml_path = output_dir / "data.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False)

    print(f"✅ 配置文件: {yaml_path}")


def main():
    parser = argparse.ArgumentParser(description="生成 YOLO 卡牌检测数据集")
    parser.add_argument(
        "--cards", type=Path, default="data/raw/cards", help="卡牌图片目录"
    )
    parser.add_argument(
        "--backgrounds", type=Path, default="data/raw/backgrounds", help="背景图片目录"
    )
    parser.add_argument(
        "--output", type=Path, default="data/synthetic", help="输出目录"
    )
    parser.add_argument("--num-images", type=int, default=10000, help="生成图像总数")
    args = parser.parse_args()

    print("=" * 50)
    print("YOLO 合成数据集生成器")
    print("=" * 50)

    generator = DatasetGenerator(args.cards, args.backgrounds, args.output)
    generator.generate_dataset(args.num_images)
    create_yaml(args.output)

    print(f"\n📁 数据集位置: {args.output}")
    print("💡 下一步: python scripts/train.py")


if __name__ == "__main__":
    main()
