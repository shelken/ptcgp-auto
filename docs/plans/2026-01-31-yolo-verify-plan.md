# YOLO + 感知哈希验证方案实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
> **Worktree:** 使用 `.worktrees/yolo-verify` 工作区

**Goal:** 使用官方 YOLO11 OBB 预训练模型验证卡牌检测效果，不依赖训练好的专用模型

**Architecture:** 
- 基于 yolo-hash 分支代码，提取核心检测逻辑
- 使用官方 `yolo11n-obb.pt` 模型（自动下载）
- 实现测试脚本验证检测精度
- 不修改现有主分支代码，在独立工作区验证

**Tech Stack:** 
- Python + Ultralytics (YOLO11 OBB)
- OpenCV (图像处理)
- NumPy (数值计算)

---

## 前置依赖

**新增依赖（requirements.txt）：**
```
ultralytics>=8.0.0  # YOLO11 支持
```

---

## 任务清单

### Task 1: 创建工作区

**Files:**
- 修改: `.gitignore`（如需）
- 创建: `.worktrees/yolo-verify/` 目录

**Step 1: 检查并创建工作区**

```bash
# 检查 .worktrees 是否已忽略
git check-ignore -q .worktrees

# 创建新工作区和分支
git worktree add .worktrees/yolo-verify -b feature/yolo-verify

# 进入工作区
cd .worktrees/yolo-verify
```

**Step 2: 安装依赖**

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装 YOLO 依赖
pip install ultralytics>=8.0.0
```

**Step 3: 验证环境**

```bash
python -c "from ultralytics import YOLO; print('Ultralytics OK')"
```

**Step 4: Commit 依赖更新**

```bash
git add requirements.txt
git commit -m "chore(deps): add ultralytics for YOLO support"
```

---

### Task 2: 实现 YOLO 卡牌检测器

**Files:**
- 创建: `src/ptcgp_auto_v2/infra/experiments/yolo_card/yolo_detector.py`
- 参考: `.worktrees/yolo-hash/src/ptcgp_auto_v2/infra/experiments/yolo_card/yolo_detector.py`

**Step 1: 创建实验目录结构**

```bash
mkdir -p src/ptcgp_auto_v2/infra/experiments/yolo_card
mkdir -p tests/infra/experiments/yolo_card
```

**Step 2: 实现 YoloObbDetector**

```python
# src/ptcgp_auto_v2/infra/experiments/yolo_card/yolo_detector.py
# -*- coding: utf-8 -*-
"""
YOLO11 OBB 检测器
使用官方预训练模型验证卡牌检测效果
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class YoloObbDetection:
    """YOLO OBB 检测结果"""
    corners: np.ndarray  # 4x2 角点坐标
    confidence: float
    angle: float
    center: Tuple[float, float]
    class_id: int = 0


class YoloObbDetector:
    """YOLO11 OBB 检测器 - 使用官方预训练模型"""
    
    def __init__(
        self, 
        model_source: str = "yolo11n-obb.pt",
        confidence: float = 0.1,
        device: Optional[str] = None
    ):
        """
        初始化检测器
        
        Args:
            model_source: 模型路径或名称，默认使用官方 yolo11n-obb.pt
            confidence: 置信度阈值
            device: 运行设备 ('mps' for Mac, '0' for CUDA, None for auto)
        """
        self.model_source = model_source
        self.confidence = confidence
        self.device = device
        self._model = None
    
    def load(self):
        """加载 YOLO 模型（首次会自动下载）"""
        from ultralytics import YOLO
        
        logger.info("正在加载 YOLO 模型: %s", self.model_source)
        self._model = YOLO(self.model_source)
        logger.info("YOLO 模型加载完成")
        
        # 打印模型信息
        logger.info("模型任务类型: %s", self._model.task)
        logger.info("模型输入尺寸: %s", self._model.model.args.imgsz)
    
    def detect(self, bgr_image: np.ndarray) -> List[YoloObbDetection]:
        """
        检测图像中的旋转边界框
        
        Args:
            bgr_image: OpenCV BGR 格式图像
            
        Returns:
            检测结果列表
        """
        if self._model is None:
            raise RuntimeError("YOLO 模型未加载，请先调用 load()")
        
        # 执行推理
        results = self._model.predict(
            source=bgr_image,
            conf=self.confidence,
            device=self.device,
            verbose=False,
        )
        
        if not results:
            return []
        
        result = results[0]
        detections: List[YoloObbDetection] = []
        
        # 检查是否有 OBB 结果
        if result.obb is None:
            logger.debug("未检测到 OBB 结果")
            return detections
        
        # 解析 OBB 结果
        for obb in result.obb:
            xywhr = obb.xywhr[0]  # [x_center, y_center, width, height, rotation]
            conf = float(obb.conf[0].item())
            
            x_center = float(xywhr[0].item())
            y_center = float(xywhr[1].item())
            width = float(xywhr[2].item())
            height = float(xywhr[3].item())
            angle = float(xywhr[4].item())
            
            # 计算角点
            corners = self._obb_to_corners(x_center, y_center, width, height, angle)
            
            detections.append(
                YoloObbDetection(
                    corners=corners,
                    confidence=conf,
                    angle=angle,
                    center=(x_center, y_center),
                )
            )
        
        logger.info("检测到 %d 个目标", len(detections))
        return detections
    
    @staticmethod
    def _obb_to_corners(
        cx: float, cy: float, w: float, h: float, angle_deg: float
    ) -> np.ndarray:
        """
        将 OBB 参数转换为 4 个角点坐标
        
        Args:
            cx, cy: 中心点坐标
            w, h: 宽度和高度
            angle_deg: 旋转角度（度）
            
        Returns:
            4x2 角点坐标数组
        """
        angle_rad = angle_deg * np.pi / 180.0
        
        # 定义未旋转的角点（相对于中心）
        corners = np.array([
            [-w / 2, -h / 2],
            [w / 2, -h / 2],
            [w / 2, h / 2],
            [-w / 2, h / 2],
        ], dtype=np.float32)
        
        # 旋转矩阵
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        rotation = np.array([
            [cos_a, -sin_a],
            [sin_a, cos_a]
        ], dtype=np.float32)
        
        # 应用旋转和平移
        rotated = corners @ rotation.T
        rotated[:, 0] += cx
        rotated[:, 1] += cy
        
        return rotated
```

**Step 3: Commit 实现**

```bash
git add src/ptcgp_auto_v2/infra/experiments/yolo_card/yolo_detector.py
git commit -m "feat(yolo): implement YOLO11 OBB detector using official pretrained model"
```

---

### Task 3: 编写测试脚本

**Files:**
- 创建: `scripts/test_yolo_detection.py`

**Step 1: 创建测试脚本**

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YOLO 卡牌检测测试脚本

使用方法:
    python scripts/test_yolo_detection.py --image path/to/screenshot.jpg
    python scripts/test_yolo_detection.py --dir path/to/screenshots/
"""

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

# 添加 src 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ptcgp_auto_v2.infra.experiments.yolo_card.yolo_detector import YoloObbDetector

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def draw_detections(image: np.ndarray, detections, color=(0, 255, 0)):
    """在图像上绘制检测结果"""
    result = image.copy()
    for i, det in enumerate(detections):
        corners = det.corners.astype(np.int32)
        
        # 绘制边界框
        cv2.polylines(result, [corners], True, color, 2)
        
        # 绘制中心点
        cx, cy = int(det.center[0]), int(det.center[1])
        cv2.circle(result, (cx, cy), 5, (0, 0, 255), -1)
        
        # 绘制标签
        label = f"#{i+1} conf={det.confidence:.2f}"
        cv2.putText(
            result, label, 
            (corners[0][0], corners[0][1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2
        )
    
    return result


def test_single_image(image_path: str, output_dir: str = None, device: str = None):
    """测试单张图片"""
    image_path = Path(image_path)
    
    if not image_path.exists():
        logger.error("图片不存在: %s", image_path)
        return False
    
    # 加载图像
    logger.info("加载图片: %s", image_path)
    image = cv2.imread(str(image_path))
    if image is None:
        logger.error("无法读取图片: %s", image_path)
        return False
    
    logger.info("图片尺寸: %dx%d", image.shape[1], image.shape[0])
    
    # 初始化检测器
    logger.info("初始化 YOLO 检测器...")
    detector = YoloObbDetector(
        model_source="yolo11n-obb.pt",
        confidence=0.1,
        device=device
    )
    detector.load()
    
    # 执行检测
    logger.info("执行检测...")
    detections = detector.detect(image)
    
    # 输出结果
    logger.info("=" * 50)
    logger.info("检测结果:")
    logger.info("=" * 50)
    logger.info("检测到 %d 个目标", len(detections))
    
    for i, det in enumerate(detections):
        logger.info("\n目标 #%d:", i + 1)
        logger.info("  置信度: %.3f", det.confidence)
        logger.info("  中心点: (%.1f, %.1f)", det.center[0], det.center[1])
        logger.info("  旋转角度: %.1f°", det.angle)
        logger.info("  角点坐标:")
        for j, corner in enumerate(det.corners):
            logger.info("    [%d] (%.1f, %.1f)", j, corner[0], corner[1])
    
    # 可视化
    vis_image = draw_detections(image, detections)
    
    # 保存结果
    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_path = output_dir / f"{image_path.stem}_detected.jpg"
        cv2.imwrite(str(output_path), vis_image)
        logger.info("\n可视化结果已保存: %s", output_path)
    else:
        # 显示结果（如果是本地环境）
        cv2.imshow("Detection Result", vis_image)
        logger.info("\n按任意键关闭窗口...")
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return len(detections) > 0


def test_directory(dir_path: str, output_dir: str, device: str = None):
    """测试目录中的所有图片"""
    dir_path = Path(dir_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 查找所有图片
    image_extensions = {".jpg", ".jpeg", ".png", ".bmp"}
    images = [
        f for f in dir_path.iterdir()
        if f.suffix.lower() in image_extensions
    ]
    
    logger.info("找到 %d 张图片", len(images))
    
    # 初始化检测器
    detector = YoloObbDetector(device=device)
    detector.load()
    
    # 统计
    total = len(images)
    success = 0
    detected_counts = []
    
    for image_path in images:
        logger.info("\n处理: %s", image_path.name)
        
        image = cv2.imread(str(image_path))
        if image is None:
            logger.warning("无法读取图片，跳过")
            continue
        
        detections = detector.detect(image)
        detected_counts.append(len(detections))
        
        if len(detections) > 0:
            success += 1
            vis_image = draw_detections(image, detections)
            output_path = output_dir / f"{image_path.stem}_detected.jpg"
            cv2.imwrite(str(output_path), vis_image)
    
    # 输出统计
    logger.info("\n" + "=" * 50)
    logger.info("批量测试统计:")
    logger.info("=" * 50)
    logger.info("总图片数: %d", total)
    logger.info("成功检测: %d (%.1f%%)", success, success / total * 100)
    logger.info("平均检测目标数: %.2f", sum(detected_counts) / len(detected_counts) if detected_counts else 0)
    logger.info("检测目标分布:")
    for count in sorted(set(detected_counts)):
        num = detected_counts.count(count)
        logger.info("  %d 个目标: %d 张图片 (%.1f%%)", count, num, num / total * 100)
    
    return success > 0


def main():
    parser = argparse.ArgumentParser(description="YOLO 卡牌检测测试")
    parser.add_argument(
        "--image", "-i",
        help="单张测试图片路径"
    )
    parser.add_argument(
        "--dir", "-d",
        help="测试图片目录"
    )
    parser.add_argument(
        "--output", "-o",
        default="_out/yolo_test",
        help="输出目录 (默认: _out/yolo_test)"
    )
    parser.add_argument(
        "--device",
        choices=["mps", "cpu"],
        default=None,
        help="运行设备 (mps=Mac GPU, cpu=CPU)"
    )
    
    args = parser.parse_args()
    
    if not args.image and not args.dir:
        parser.print_help()
        print("\n请提供 --image 或 --dir 参数")
        sys.exit(1)
    
    if args.image:
        success = test_single_image(args.image, args.output, args.device)
    else:
        success = test_directory(args.dir, args.output, args.device)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
```

**Step 2: 添加执行权限并 Commit**

```bash
chmod +x scripts/test_yolo_detection.py
git add scripts/test_yolo_detection.py
git commit -m "feat(yolo): add YOLO detection test script"
```

---

### Task 4: 创建示例测试数据

**Files:**
- 创建: `test_data/yolo_samples/README.md`

**Step 1: 准备测试数据说明**

```bash
mkdir -p test_data/yolo_samples
```

```markdown
# YOLO 检测测试数据

## 使用方法

1. 放置开包结果页截图到本目录
2. 运行测试脚本:
   ```bash
   python scripts/test_yolo_detection.py --dir test_data/yolo_samples/
   ```

## 期望结果

- 每张截图应检测到 5 张卡牌（开包结果）
- 检测框应准确贴合卡牌边框
- 置信度应 > 0.5

## 测试数据要求

- 格式: JPG 或 PNG
- 分辨率: 建议 1080x1920（或其他手机截图分辨率）
- 内容: PTCGP 开包结果页面
```

**Step 2: Commit**

```bash
git add test_data/yolo_samples/README.md
git commit -m "docs(yolo): add test data instructions"
```

---

### Task 5: 运行验证测试

**Files:**
- 输出: `_out/yolo_test/` 目录中的可视化结果

**Step 1: 下载模型并运行测试**

```bash
# 首次运行会自动下载 yolo11n-obb.pt（约 5MB）
python scripts/test_yolo_detection.py --image test_data/yolo_samples/screenshot_001.jpg
```

**Step 2: 评估结果**

**成功标准：**
- ✅ 模型成功加载
- ✅ 能检测到卡牌（数量合理）
- ✅ 检测框贴合卡牌边框
- ✅ 置信度 > 0.1

**失败标准：**
- ❌ 无法检测任何目标
- ❌ 检测框位置偏差过大
- ❌ 大量误检

**Step 3: 记录测试结果**

创建测试报告：
```markdown
# YOLO 验证测试报告

## 测试日期
2026-01-31

## 测试环境
- 模型: yolo11n-obb.pt (官方预训练)
- 设备: [Mac M1/M2 / CPU]
- 输入尺寸: 640x640

## 测试结果

### 测试用例 1: [截图文件名]
- 检测结果: [成功/失败]
- 检测数量: [N] 张卡牌
- 置信度范围: [min - max]
- 备注: [观察到的现象]

### 批量测试统计
- 总图片数: [N]
- 成功检测: [N] (xx%)
- 平均检测目标数: [x.x]

## 结论

[是否能直接使用官方模型 / 需要训练专用模型]
```

---

### Task 6: 根据结果决策

**Files:**
- 修改: `docs/needs/04-yolo-hash模型需求.md`

**Step 1: 更新需求文档**

根据测试结果更新文档：

**如果效果好：**
- 标记方案 A 可行
- 计划整合到主分支
- 编写使用文档

**如果效果不好：**
- 标记需要训练专用模型
- 启动方案 B（训练流程）
- 记录失败原因

**Step 2: Commit 文档更新**

```bash
git add docs/needs/04-yolo-hash模型需求.md
git commit -m "docs(yolo): update requirements with test results"
```

---

## 整合回主分支的计划（如果验证成功）

### Task 7: 合并到主分支

**Files:**
- 修改: `src/ptcgp_auto_v2/infra/card_recognizer.py`
- 修改: `requirements.txt`
- 删除: 旧的模板匹配代码（可选）

**Step 1: 回到主分支并合并**

```bash
# 回到主工作区
cd /Users/shelken/Code/MyRepo/ptcgp-auto

# 合并 yolo-verify 分支
git merge feature/yolo-verify --no-ff
```

**Step 2: 清理工作区**

```bash
git worktree remove .worktrees/yolo-verify
git branch -d feature/yolo-verify
```

---

## 测试用例设计

### 必须测试的场景

1. **标准开包结果页**
   - 5 张卡牌正常排列
   - 期望：检测 5 个边界框

2. **旋转卡牌**
   - 开包动画中倾斜的卡牌
   - 期望：OBB 能准确框选

3. **重叠卡牌**
   - 多张卡牌部分重叠
   - 期望：分别检测每个卡牌

4. **不同分辨率**
   - 不同手机型号的截图
   - 期望：自适应缩放，检测正常

### 评估指标

| 指标 | 合格线 | 优秀 |
|------|--------|------|
| 召回率 (Recall) | > 80% | > 95% |
| 准确率 (Precision) | > 80% | > 95% |
| 检测速度 | < 1s/张 | < 0.5s/张 |
| 误检率 | < 20% | < 5% |

---

## 风险与应对

| 风险 | 可能性 | 应对策略 |
|------|--------|---------|
| 官方模型无法检测卡牌 | 中 | 立即启动训练流程 |
| 模型下载失败 | 低 | 手动下载并放置到 models/ 目录 |
| 检测速度太慢 | 低 | 导出为 CoreML 加速 |
| 显存不足 | 低 | 使用 CPU 模式或降低 batch size |

---

## 时间安排

| 阶段 | 预计时间 | 任务 |
|------|---------|------|
| 准备 | 30 min | 创建工作区，安装依赖 |
| 开发 | 1-2 hrs | 实现检测器，编写测试脚本 |
| 测试 | 1-2 hrs | 运行验证，收集结果 |
| 决策 | 30 min | 评估结果，更新文档 |
| **总计** | **3-5 hrs** | |

---

## 成功标准

**方案 A 成功（使用官方模型）：**
- ✅ 能在 80% 的测试截图中检测到卡牌
- ✅ 检测框位置偏差 < 20%
- ✅ 处理速度 < 1 秒/张
- ✅ 无需训练即可使用

**方案 A 失败（需要训练）：**
- ❌ 检测召回率 < 50%
- ❌ 大量误检（误检率 > 30%）
- ❌ 无法检测旋转卡牌
