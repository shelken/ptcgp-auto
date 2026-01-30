# YOLO 卡牌检测训练流程

本文档记录从下载资源到训练完成的完整流程，方便后续复现。

## 前置准备

### 1. 进入工作目录

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto/yolo-card-training/
direnv allow  # 自动加载 nix 环境
```

**重要**：必须在 `yolo-card-training/` 目录下执行所有命令，使用 `uv run` 调用脚本。

---

## 第一步：下载卡牌图片

### 命令

```bash
uv run python scripts/download_assets.py
```

### 说明

- 下载 A4 系列卡牌（约 98 张）
- 使用 jsDelivr CDN 加速
- 耗时：约 2-3 分钟
- 输出：`data/raw/cards/`

### 结果检查

```bash
ls data/raw/cards/ | wc -l
# 预期：98 张左右
```

---

## 第二步：下载背景图片

### 命令

```bash
uv run python scripts/download_backgrounds.py
```

### 说明

- 从 sample-images 仓库下载 10 张背景
- 耗时：约 30 秒
- 输出：`data/raw/backgrounds/`

### 注意事项

当前只有 10 张背景，多样性不足。生产环境建议：
- 下载 50-100 张多样背景（室内、桌面、布料、自然风光）
- 参考原作者仓库获取更多背景源

---

## 第三步：生成合成数据集

### 命令

```bash
# 生成 100 张测试数据集（快速验证）
uv run python scripts/generate_dataset.py --num-images 100

# 或生成 10,000 张完整数据集（生产环境）
uv run python scripts/generate_dataset.py --num-images 10000
```

### 说明

- 合成数据位置：`data/synthetic/`
- 数据结构：
  ```
  data/synthetic/
  ├── images/
  │   ├── train/     # 80%
  │   ├── val/       # 10%
  │   └── test/      # 10%
  ├── labels/
  │   ├── train/
  │   ├── val/
  │   └── test/
  └── data.yaml      # YOLO 配置文件
  ```

### 耗时

- 100 张：约 1-2 分钟
- 10,000 张：约 30-60 分钟

### 当前问题

当前实现与原作者差异较大：
- 原作者：70% 密集场景（8-15 张卡），大量小目标训练（0.08-0.15 缩放）
- 当前：主要 1-5 张卡，0.15-0.35 缩放

**建议**：使用原作者算法重新生成（见 todos.md）

---

## 第四步：训练模型

### 命令

```bash
# 快速测试（50 epochs）
uv run python scripts/train.py --epochs 50 --batch 16

# 生产训练（100 epochs）
uv run python scripts/train.py --epochs 100 --batch 16
```

### 说明

- 设备：自动检测 MPS（Apple Silicon）或 CPU
- 早停：patience=20（20 轮无改善自动停止）
- 输出位置：`../runs/obb/output/models/card_obb/weights/`
  - `best.pt` - 验证集最佳模型
  - `last.pt` - 最后一轮模型

### 耗时

- 100 张数据集，50 epochs：约 10-15 分钟
- 10,000 张数据集，100 epochs：约 1-2 小时

### 训练监控

正常训练应该看到：
```
Epoch    GPU_mem   box_loss   cls_loss   dfl_loss angle_loss  Instances       Size
  1/50      4.17G      1.938      3.206      3.609     0.2202        ...        640
```

关键指标：
- `box_loss`/`cls_loss`/`angle_loss` 持续下降
- 验证集 mAP50 > 0.5（最好 > 0.9）

---

## 第五步：测试模型

### 5.1 测试本地图片

```bash
uv run python scripts/test_model.py \
  --model ../runs/obb/output/models/card_obb/weights/best.pt \
  --image /path/to/screenshot.png \
  --conf 0.6
```

### 5.2 测试 ADB 截图（自动连接设备）

```bash
uv run python scripts/test_model.py \
  --model ../runs/obb/output/models/card_obb/weights/best.pt \
  --conf 0.6
```

### 说明

- 检测到目标会显示置信度
- 通过 `--conf` 设置阈值过滤低置信度误检
- 结果图保存到当前目录（如 `screenshot_detected.jpg`）
- 支持 Kitty 终端内联显示（自动检测）

### 预期结果

开包场景（5 张卡）：
```
检测到 6 个目标 (置信度阈值: 0.6)
  [1] ✅ 置信度: 0.907
  [2] ✅ 置信度: 0.898
  [3] ✅ 置信度: 0.884
  [4] ✅ 置信度: 0.832
  [5] ✅ 置信度: 0.654
  [6] ❌ 置信度: 0.437   ← 阈值过滤掉
```

---

## 第六步：性能对比（PyTorch vs CoreML）

### 命令

```bash
uv run python scripts/benchmark.py
```

### 说明

- 对比 PyTorch (`.pt`) 和 CoreML (`.mlpackage`) 推理速度
- 各运行 10 次取平均
- 预期：CoreML 提速 2-3 倍

### 示例结果

```
PyTorch (.pt):     24.2ms ± 0.9ms
CoreML (.mlpackage): 10.0ms ± 1.7ms
✅ CoreML 更快，提速: 2.41x
```

---

## 第七步：导出 CoreML

### 命令

```bash
uv run python -c "
from ultralytics import YOLO
model = YOLO('../runs/obb/output/models/card_obb/weights/best.pt')
model.export(format='coreml', imgsz=640)
print('CoreML 导出完成！')
"
```

### 说明

- 输出：`best.mlpackage`（约 5.3 MB）
- 使用 Apple Neural Engine (ANE) 加速
- 适用于 macOS/iOS 部署

---

## 完整流程总结

```bash
# 1. 下载资源（约 3 分钟）
uv run python scripts/download_assets.py
uv run python scripts/download_backgrounds.py

# 2. 生成数据集（约 1-2 分钟 / 30-60 分钟）
uv run python scripts/generate_dataset.py --num-images 100

# 3. 训练模型（约 10-15 分钟 / 1-2 小时）
uv run python scripts/train.py --epochs 50 --batch 16

# 4. 测试模型
uv run python scripts/test_model.py --model ../runs/obb/output/models/card_obb/weights/best.pt --image /path/to/test.png --conf 0.6

# 5. 性能对比
uv run python scripts/benchmark.py

# 6. 导出 CoreML
uv run python -c "from ultralytics import YOLO; YOLO('../runs/obb/output/models/card_obb/weights/best.pt').export(format='coreml', imgsz=640)"
```

---

## 常见问题

### Q: 为什么模型输出到 `../runs/` 而不是 `output/`？

A: ultralytics 默认输出到 `runs/<task>/`，当前无法简单修改。建议：
- 训练后手动复制到 `output/models/`
- 或在脚本中使用 `../runs/...` 路径

### Q: 测试时提示 "No module named 'ultralytics'"？

A: 必须在 `yolo-card-training/` 目录下执行，且使用 `uv run`：
```bash
cd yolo-card-training/
uv run python scripts/xxx.py
```

### Q: 如何提升准确率？

A: 当前 100 张数据集不足以生产使用。建议：
1. 生成 1000-10000 张数据（原作者算法）
2. 下载 50-100 张多样背景
3. 训练 100 epochs
4. 参考 `todos.md` 中的数据集优化任务

---

## 参考资源

- 原作者项目：https://github.com/1vcian/Pokemon-TCGP-Card-Scanner
- YOLO11 OBB 文档：https://docs.ultralytics.com/tasks/obb/
- 踩坑记录：`docs/LESSONS_LEARNED.md`
- 待办事项：`todos.md`
