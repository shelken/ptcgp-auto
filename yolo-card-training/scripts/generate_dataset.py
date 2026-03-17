#!/usr/bin/env python3
"""
生成 YOLO OBB 合成数据集（双模式 v2）
基于 1vcian 的 trainCreator.py 核心逻辑

双模式：
- 网格模式（50%）：密集排列 50-300 张卡牌
- 随机模式（50%）：1-15 张卡牌，包含小目标训练（0.08-0.15 缩放）

生成 640x640 图像，带旋转边界框标注
"""

import argparse
import math
import random
from pathlib import Path

import yaml
from PIL import Image
from tqdm import tqdm


class DatasetGenerator:
    """合成数据集生成器（双模式）"""

    def __init__(self, cards_dir: Path, backgrounds_dir: Path, output_dir: Path):
        self.cards_dir = cards_dir
        self.backgrounds_dir = backgrounds_dir
        self.output_dir = output_dir

        # 支持多种图片格式（递归扫描所有子目录）
        self.cards_files = []
        for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
            self.cards_files.extend(list(cards_dir.rglob(ext)))

        self.backgrounds_files = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
            self.backgrounds_files.extend(list(backgrounds_dir.glob(ext)))

        print(
            f"📊 找到 {len(self.cards_files)} 张卡牌, {len(self.backgrounds_files)} 张背景"
        )

        if len(self.backgrounds_files) == 0:
            raise FileNotFoundError("未找到背景图片，请检查 backgrounds 目录")

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

    def _build_random_result(
        self,
        bg_img: Image.Image,
        card_img: Image.Image,
        x: int,
        y: int,
        rot_w: int,
        rot_h: int,
        new_w: int,
        new_h: int,
        angle: float,
    ):
        """根据随机模式位置与角度生成结果与 OBB 标注"""
        bg_w, bg_h = bg_img.size

        result = bg_img.copy()
        if card_img.mode == "RGBA":
            result.paste(card_img, (x, y), card_img.split()[3])
        else:
            result.paste(card_img, (x, y))

        center_x = (x + rot_w / 2) / bg_w
        center_y = (y + rot_h / 2) / bg_h

        half_w = new_w / 2 / bg_w
        half_h = new_h / 2 / bg_h

        corners = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        angle_rad = math.radians(-angle)
        rotated_corners = []
        for cx, cy in corners:
            rx = cx * math.cos(angle_rad) - cy * math.sin(angle_rad)
            ry = cx * math.sin(angle_rad) + cy * math.cos(angle_rad)
            x_final = max(0, min(1, center_x + rx))
            y_final = max(0, min(1, center_y + ry))
            rotated_corners.extend([x_final, y_final])

        yolo_bbox = [0] + [round(c, 6) for c in rotated_corners]
        pixel_bbox = [x, y, x + rot_w, y + rot_h]

        return result, yolo_bbox, pixel_bbox

    def place_card(
        self,
        card_img: Image.Image,
        bg_img: Image.Image,
        existing_boxes: list,
        scale_factor: float | None = None,
        angle: float | None = None,
    ):
        """在背景上放置一张卡牌（随机模式），返回图像和 OBB 标注"""
        bg_w, bg_h = bg_img.size
        card_w, card_h = card_img.size

        # 缩放卡牌
        if scale_factor is None:
            scale_factor = random.uniform(0.15, 0.35)

        # 确保缩放后卡牌不会太大
        max_scale = min(0.4, 0.8 * min(bg_w, bg_h) / max(card_w, card_h))
        scale_factor = min(scale_factor, max_scale)

        new_w = int(bg_w * scale_factor)
        new_h = int(card_h * (new_w / card_w))

        # 确保最小尺寸
        new_w = max(new_w, 50)
        new_h = max(new_h, 50)

        card_img = card_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 旋转角度（参考原版逻辑）
        if angle is None:
            if scale_factor > 0.3:
                angle = random.uniform(-5, 5)
            else:
                angle = random.uniform(-15, 15)

        card_img = card_img.rotate(
            angle, expand=True, resample=Image.Resampling.BICUBIC
        )
        rot_w, rot_h = card_img.size

        # 安全检查
        if rot_w >= bg_w or rot_h >= bg_h:
            return None, None, None

        # 尝试放置（参考原版：网格随机格 + 偏移）
        max_attempts = 50
        grid_cols = 5
        grid_rows = 4
        cell_w = bg_w // grid_cols
        cell_h = bg_h // grid_rows

        last_pos = None
        for _ in range(max_attempts):
            grid_x = random.randint(0, grid_cols - 1)
            grid_y = random.randint(0, grid_rows - 1)

            base_x = grid_x * cell_w + random.randint(-10, 10)
            base_y = grid_y * cell_h + random.randint(-10, 10)

            x = max(0, min(base_x, bg_w - rot_w))
            y = max(0, min(base_y, bg_h - rot_h))
            last_pos = (x, y)

            # 检查重叠（IoU阈值0.1）
            new_box = [x, y, x + rot_w, y + rot_h]
            overlap = any(
                self.calculate_iou(new_box, box) > 0.1 for box in existing_boxes
            )

            if not overlap:
                return self._build_random_result(
                    bg_img, card_img, x, y, rot_w, rot_h, new_w, new_h, angle
                )

        # 兜底：使用最后一次位置
        if last_pos is None:
            return None, None, None
        x, y = last_pos
        return self._build_random_result(
            bg_img, card_img, x, y, rot_w, rot_h, new_w, new_h, angle
        )

    def place_card_grid(
        self,
        card_img: Image.Image,
        bg_img: Image.Image,
        grid_x: int,
        grid_y: int,
        grid_cols: int = 5,
        grid_rows: int = 4,
    ):
        """在网格位置放置卡牌（规整布局）"""
        bg_w, bg_h = bg_img.size
        card_w, card_h = card_img.size

        # 计算网格单元大小
        cell_w = bg_w // grid_cols
        cell_h = bg_h // grid_rows

        # 卡牌大小适配单元格（留边距）
        card_scale = 0.99
        new_w = int(cell_w * card_scale)
        new_h = int(card_h * (new_w / card_w))

        # 如果高度超限，按高度缩放
        if new_h > cell_h * card_scale:
            new_h = int(cell_h * card_scale)
            new_w = int(card_w * (new_h / card_h))

        card_img = card_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 网格模式不旋转、不偏移，严格居中对齐
        rot_w, rot_h = new_w, new_h

        paste_x = grid_x * cell_w + (cell_w - rot_w) // 2
        paste_y = grid_y * cell_h + (cell_h - rot_h) // 2

        # 边界检查
        paste_x = max(0, min(paste_x, bg_w - rot_w))
        paste_y = max(0, min(paste_y, bg_h - rot_h))

        # 放置卡牌
        result = bg_img.copy()
        if card_img.mode == "RGBA":
            result.paste(card_img, (paste_x, paste_y), card_img.split()[3])
        else:
            result.paste(card_img, (paste_x, paste_y))

        # 计算 OBB 标注（轴对齐）
        x1 = paste_x / bg_w
        y1 = paste_y / bg_h
        x2 = (paste_x + rot_w) / bg_w
        y2 = y1
        x3 = x2
        y3 = (paste_y + rot_h) / bg_h
        x4 = x1
        y4 = y3

        yolo_bbox = [0] + [round(v, 6) for v in [x1, y1, x2, y2, x3, y3, x4, y4]]
        pixel_bbox = [paste_x, paste_y, paste_x + rot_w, paste_y + rot_h]

        return result, yolo_bbox, pixel_bbox

    def generate_image(self, idx: int, split: str, num_cards: int | None = None):
        """生成单张数据集图像（随机模式）"""
        if num_cards is None:
            # 30%概率1-3张，70%概率8-15张
            num_cards = random.choices(
                [1, 2, 3, random.randint(8, 15)], weights=[0.1, 0.1, 0.1, 0.7]
            )[0]

        bg_file = random.choice(self.backgrounds_files)
        bg_img = Image.open(bg_file).convert("RGBA")
        bg_img = bg_img.resize((640, 640), Image.Resampling.LANCZOS)

        existing_boxes = []
        yolo_bboxes = []

        # 放置卡牌
        for i in range(num_cards):
            card_file = random.choice(self.cards_files)
            card_img = Image.open(card_file).convert("RGBA")

            # 根据卡牌数量确定缩放因子（原作者算法）
            if num_cards == 1:
                scale_factor = random.uniform(0.7, 0.8)
            elif num_cards == 2:
                scale_factor = random.uniform(0.35, 0.45)
            elif num_cards == 3:
                scale_factor = random.uniform(0.25, 0.35)
            else:
                scale_factor = random.uniform(0.08, 0.15)  # 小目标训练

            # 旋转角度根据卡牌大小调整
            if scale_factor > 0.3:
                angle = random.uniform(-5, 5)
            else:
                angle = random.uniform(-15, 15)

            result, yolo_bbox, box = self.place_card(
                card_img, bg_img, existing_boxes, scale_factor, angle
            )

            if result is not None:
                bg_img = result
                existing_boxes.append(box)
                yolo_bboxes.append(yolo_bbox)

        # 保存图像
        img_path = self.output_dir / "images" / split / f"{idx:06d}.jpg"
        bg_img.convert("RGB").save(img_path, quality=95)

        # 保存标注
        label_path = self.output_dir / "labels" / split / f"{idx:06d}.txt"
        with open(label_path, "w") as f:
            for bbox in yolo_bboxes:
                f.write(" ".join(map(str, bbox)) + "\n")

        return img_path

    def generate_image_grid(
        self,
        idx: int,
        split: str,
        grid_rows: int | None = None,
        grid_cols: int | None = None,
    ):
        """生成网格模式数据集图像（密集排列）"""
        # 随机确定网格大小
        if grid_rows is None:
            grid_rows = random.randint(5, 15)
        if grid_cols is None:
            grid_cols = random.randint(10, 20)

        bg_file = random.choice(self.backgrounds_files)
        bg_img = Image.open(bg_file).convert("RGBA")
        bg_img = bg_img.resize((640, 640), Image.Resampling.LANCZOS)

        yolo_bboxes = []

        # 在网格中放置卡牌
        for row in range(grid_rows):
            for col in range(grid_cols):
                card_file = random.choice(self.cards_files)
                card_img = Image.open(card_file).convert("RGBA")

                result, yolo_bbox, _ = self.place_card_grid(
                    card_img, bg_img, col, row, grid_cols, grid_rows
                )
                bg_img = result
                yolo_bboxes.append(yolo_bbox)

        # 保存图像
        img_path = self.output_dir / "images" / split / f"{idx:06d}.jpg"
        bg_img.convert("RGB").save(img_path, quality=95)

        # 保存标注
        label_path = self.output_dir / "labels" / split / f"{idx:06d}.txt"
        with open(label_path, "w") as f:
            for bbox in yolo_bboxes:
                f.write(" ".join(map(str, bbox)) + "\n")

        return img_path

    def generate_dataset(self, total: int = 1000, train_ratio=0.8, val_ratio=0.1):
        """生成完整数据集（双模式：网格+随机）"""
        print(f"\n🎯 生成 {total} 张数据集（双模式）:")

        # 创建目录
        for subdir in [
            "images/train",
            "images/val",
            "images/test",
            "labels/train",
            "labels/val",
            "labels/test",
        ]:
            (self.output_dir / subdir).mkdir(parents=True, exist_ok=True)

        # 计算各split数量
        train_num = int(total * train_ratio)
        val_num = int(total * val_ratio)
        test_num = total - train_num - val_num

        splits = [
            ("train", train_num, 0),
            ("val", val_num, train_num),
            ("test", test_num, train_num + val_num),
        ]

        print(f"   网格模式: ~{total // 2}张（密集场景训练）")
        print(f"   随机模式: ~{total // 2}张（真实场景训练）")
        print(f"   Train: {train_num}, Val: {val_num}, Test: {test_num}")

        current_idx = 0
        for split, count, offset in splits:
            print(f"\n📁 生成 {split} 集 ({count}张)...")

            # 50%网格模式，50%随机模式
            grid_count = count // 2
            random_count = count - grid_count

            # 生成网格模式图像
            for i in tqdm(range(grid_count), desc="  网格模式"):
                idx = offset + i
                self.generate_image_grid(idx, split)
                current_idx += 1

            # 生成随机模式图像
            for i in tqdm(range(random_count), desc="  随机模式"):
                idx = offset + grid_count + i
                self.generate_image(idx, split)
                current_idx += 1

        print(f"\n✅ 完成！共生成 {current_idx} 张图像")
        return current_idx


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

    print(f"\n📝 配置文件: {yaml_path}")
    return yaml_path


def main():
    parser = argparse.ArgumentParser(
        description="生成 YOLO OBB 合成数据集（双模式 v2）"
    )
    parser.add_argument("--cards", type=Path, default="data/raw/cards")
    parser.add_argument("--backgrounds", type=Path, default="data/raw/backgrounds")
    parser.add_argument("--output", type=Path, default="data/synthetic")
    parser.add_argument(
        "--total", type=int, default=1000, help="总图像数量（默认1000）"
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    args = parser.parse_args()

    print("=" * 50)
    print("YOLO 合成数据集生成器（双模式 v2）")
    print("=" * 50)

    gen = DatasetGenerator(args.cards, args.backgrounds, args.output)

    # 生成数据集
    gen.generate_dataset(args.total, args.train_ratio, args.val_ratio)

    # 创建 YAML
    create_yaml(args.output)

    print("\n" + "=" * 50)
    print("💡 下一步: python scripts/train.py --epochs 50")
    print("=" * 50)


if __name__ == "__main__":
    main()
