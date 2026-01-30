# YOLO + 感知哈希模型需求

## 需求

### 背景

YOLO + 感知哈希方案旨在替代当前模板匹配的卡牌识别方式，实现：
1. **快速识别开包结果页卡牌**（当前痛点：模板匹配太慢）
2. **全账号卡牌盘点**（遍历账号卡牌列表，记录到数据库）

现有实验代码位于 `yolo-hash` 分支，已实现完整的 YOLO 检测 + 哈希匹配管线。

---

## 重要更新：官方模型验证结果（2026-01-31）

### 验证结果

| 验证项 | 结果 |
|-------|------|
| 模型加载 | ✅ `yolo11n-obb.pt` 成功加载 |
| 卡牌检测 | ❌ **检测到 0 个目标** |
| **结论** | ❌ **方案 A 失败，必须使用方案 B（训练专用模型）** |

**测试详情**:
- 使用官方 `yolo11n-obb.pt` 模型
- 输入：1080x1920 开包结果页截图
- 置信度阈值：0.1
- 检测结果：0 个边界框

**原因分析**:
- 官方模型训练于 DOTA、HRSC2016 等通用数据集
- 检测目标为飞机、船只、车辆等，不包含卡牌
- 无法泛化到 PTCGP 卡牌检测

**决策**: 必须训练专用模型

---

## 当前进度（2026-01-31）

### 已完成 ✅

1. **创建独立训练项目** `yolo-card-training/`
   - 完全独立于主项目
   - 使用 flake + direnv + uv 管理环境
   - Python 3.12 + ultralytics 8.4.9

2. **下载素材**
   - ✅ 卡牌图片：98 张 A4 系列（`data/raw/cards/`）
   - ✅ 背景图片：10 张 sample-images（`data/raw/backgrounds/`）

3. **实现训练脚本**
   - `download_assets.py` - 并发下载卡牌（jsDelivr CDN）
   - `generate_dataset.py` - 合成数据集生成（移植 trainCreator.py）
   - `train.py` - YOLO 训练脚本（MPS 支持）

4. **生成合成数据集**
   - ✅ 100 张测试数据集（80 train / 10 val / 10 test）
   - 位置：`data/synthetic/`
   - 配置：`data/synthetic/data.yaml`

### 进行中 ⏳

5. **整合到主项目** - 准备开始
   - 测试 CoreML 实际开包场景检测效果
   - 替换模板匹配为 YOLO + 哈希匹配

### 已完成 ✅

5. **模型训练** - 2026-01-31 完成
   - 工作目录：`yolo-card-training/`
   - 执行命令：`python scripts/train.py --epochs 50 --batch 16`
   - 结果：`runs/obb/output/models/card_obb/weights/best.pt`
   - mAP50: 0.995，召回率: 100%

6. **验证训练好的模型** - 2026-01-31 完成
   - 真实开包截图测试：检测到 6 个目标（含 1 个误检）
   - 阈值过滤后（0.6）：5 个目标（正确）

7. **导出 CoreML 格式** - 2026-01-31 完成
   - 输出：`runs/obb/output/models/card_obb/weights/best.mlpackage` (5.3 MB)
   - 性能对比：CoreML 10.0ms vs PyTorch 24.2ms（**提速 2.41 倍**）

---

## 项目结构

```
ptcgp-auto/
├── yolo-card-training/          # 🆕 独立训练子项目
│   ├── flake.nix               # nix 环境定义
│   ├── .envrc                  # direnv 配置
│   ├── pyproject.toml          # uv 依赖
│   ├── scripts/
│   │   ├── download_assets.py      # 下载卡牌
│   │   ├── download_backgrounds.py # 下载背景
│   │   ├── generate_dataset.py     # 生成合成数据
│   │   └── train.py                # 训练模型
│   ├── data/
│   │   ├── raw/
│   │   │   ├── cards/          # 98 张 A4 卡牌
│   │   │   └── backgrounds/    # 10 张背景
│   │   └── synthetic/          # 100 张合成数据集
│   ├── output/
│   │   └── models/             # 训练后的模型（待生成）
│   └── docs/
│       └── LESSONS_LEARNED.md  # 踩坑记录
│
├── .worktrees/
│   ├── yolo-verify/            # YOLO 验证实验（已完成）
│   └── yolo-training/          # 当前工作目录（符号链接）
│
└── docs/needs/
    └── 04-yolo-hash模型需求.md  # 本文件
```

**当前工作目录**：`/Users/shelken/Code/MyRepo/ptcgp-auto/yolo-card-training/`

**进入方式**：
```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto/yolo-card-training/
direnv allow  # 自动加载环境
```

---

## 技术实现细节

### 1. 数据生成

**参考实现**：1vcian/Pokemon-TCGP-Card-Scanner/trainCreator.py

**核心逻辑**：
- 随机背景 + 随机卡牌（1-5张）
- 随机旋转（-15° ~ +15°）
- 随机缩放（0.15-0.35 倍背景尺寸）
- 透视变换（模拟倾斜）
- YOLO OBB 格式标注：`class x1 y1 x2 y2 x3 y3 x4 y4`

**改进点**：
- 限制最大缩放比例，避免旋转后超出背景
- 支持 .webp 卡牌格式
- 支持纯色背景作为备选

### 2. 模型训练

**预训练模型**：`yolo11n-obb.pt`（YOLO11 Nano OBB）

**训练参数**（M3 MacBook Air）：
```python
model.train(
    data='data/synthetic/data.yaml',
    epochs=50,        # 测试用，正式建议 100
    imgsz=640,
    batch=16,
    device='mps',     # Metal Performance Shaders
    patience=20,      # 早停
)
```

**预期时间**：
- 100 张数据集，50 epoch：约 10-15 分钟
- 10,000 张数据集，100 epoch：约 1-2 小时

### 3. 踩坑记录

**详见 `yolo-card-training/docs/LESSONS_LEARNED.md`**

**本次新增错误（2026-01-31）**：

1. **目录混乱 + uv 使用错误**
   - **问题**：在 `yolo-card-training/` 子项目中执行命令，但没有 `cd` 进入目录
   - **错误示例**：`uv run python scripts/train.py`（实际在根目录执行）
   - **正确做法**：
     ```bash
     cd yolo-card-training/
     uv run python scripts/train.py
     ```
   - **关键**：每个子项目有自己的 `.venv/`，必须在项目目录内执行 `uv run`

2. **未正确处理 RGBA → BGR 转换**
   - **问题**：ADB 截图是 RGBA（4通道），YOLO 需要 BGR（3通道）
   - **错误**：直接 `np.array(image)` 传给模型
   - **正确**：`RGBA → RGB → BGR` 转换后再检测
   - **参考**：`yolo-hash` 分支使用 BGR 格式（OpenCV 默认）

3. **pyproject.toml 依赖管理混乱**
   - **问题**：`uv add coremltools` 只改了配置文件，没执行 `uv sync`
   - **表现**：虚拟环境中实际没有 coremltools
   - **正确做法**：修改 pyproject.toml 后必须 `uv sync`

4. **模型路径错误**
   - **问题**：脚本中硬编码路径 `output/models/card_obb/weights/best.pt`
   - **实际**：ultralytics 输出到 `runs/obb/output/models/card_obb/weights/best.pt`
   - **教训**：先 `find` 确认实际路径，再写脚本

5. **混淆工作目录**
   - **问题**：在 `ptcgp-auto/` 根目录运行 `uv run`，却期望使用 `yolo-card-training/.venv/`
   - **正确**：子项目必须 `cd` 进入，或使用完整路径 `uv run --project yolo-card-training ...`

### 4. 重要发现

**CoreML 性能提升显著**：
- 推理速度从 24.2ms 提升到 10.0ms（2.41 倍加速）
- 使用 Apple Neural Engine (ANE)
- 警告：`Torch 2.10.0` 未在 `coremltools` 中测试，但实际运行正常

---

## 下一步行动

### 立即执行（新会话）

**用户将执行训练，我来验证结果**：

```bash
cd yolo-card-training/
python scripts/train.py --epochs 50 --batch 16
```

**验证点**：
1. 训练是否正常启动（MPS 启用、数据集读取）
2. loss 是否正常下降
3. 最终 mAP 是否 > 0.5
4. 模型文件是否正确生成

### 下一步行动（新会话）

**整合 CoreML 到主项目**：

1. 在 `feature/yolo-hash` 分支更新 YOLO 检测器
   - 使用 `best.mlpackage` 替代 PyTorch 模型
   - 测试开包截图检测效果

2. 完整 Pipeline 验证
   - ADB 截图 → YOLO CoreML 检测 → 透视变换 → 感知哈希匹配
   - 对比模板匹配速度

3. 优化策略（根据测试结果）
   - 如果检测准确但速度不够 → 考虑批量检测优化
   - 如果检测不准确 → 需要更多真实场景数据重新训练
   - 如果整体可行 → 替换主项目卡牌识别模块

---

## 文件参考

**关键文件位置**：
- 训练脚本：`yolo-card-training/scripts/train.py`
- 数据集配置：`yolo-card-training/data/synthetic/data.yaml`
- 实际模型输出：`runs/obb/output/models/card_obb/weights/best.pt`
- CoreML 输出：`runs/obb/output/models/card_obb/weights/best.mlpackage`

**外部资源**：
- 参考项目：https://github.com/1vcian/Pokemon-TCGP-Card-Scanner
- 卡牌图片来源：https://github.com/marcelpanse/tcg-pocket-collection-tracker
- 背景图片来源：https://github.com/yavuzceliker/sample-images
- YOLO11 OBB 文档：https://docs.ultralytics.com/tasks/obb/
