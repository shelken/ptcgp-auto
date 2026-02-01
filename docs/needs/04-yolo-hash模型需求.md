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

## 当前进度（2026-02-01）

### 已完成的验证 ✅

**中文 PNG 资源验证完成（2026-02-01）**

✅ **YOLO 检测 + 感知哈希匹配管线验证通过**
- 使用繁体中文 PNG 资源（shelken/ptcgp-assets）
- YOLO 检测耗时：~100ms（9张卡牌）
- 哈希匹配耗时：~250ms（9张 × 226次比对）
- **匹配率：100%**（9/9 张正确匹配）
- 平均相似度：0.80+

**关键配置确认：**
| 配置项 | 数值 | 说明 |
|--------|------|------|
| **YOLO 置信度阈值** | **0.6** | 低于此值的检测框丢弃 |
| **哈希匹配阈值** | **0.68** | 生产环境建议 0.65-0.70 |
| **图片来源** | shelken/ptcgp-assets | 繁体中文 PNG |
| **哈希算法** | DCT + 感知哈希 | 96×96 resize，8×8 DCT |

**性能表现：**
- 端到端单次检测：~400ms（含截图、检测、匹配）
- 可视化输出：output/detection_result.jpg
- 绿色外框：YOLO 检测结果（置信度标注）
- 红色内框：哈希匹配成功卡牌（卡牌ID标注）

---

### 已完成 ✅（历史）

1. **创建独立训练项目** `yolo-card-training/`
   - 完全独立于主项目
   - 使用 flake + direnv + uv 管理环境
   - Python 3.12 + ultralytics 8.4.9

2. **下载素材**
   - ✅ 卡牌图片：**107 张**（多个系列，`data/raw/cards/`）
   - ✅ 背景图片：**50 张** sample-images（`data/raw/backgrounds/`）
     - 2026-01-31 更新：从 10 张扩充到 50 张，提升背景多样性

3. **实现双模式数据集生成器** ✅
   - **网格模式**（50%）：密集排列 50-300 张卡牌，训练密集场景检测
   - **随机模式**（50%）：1-15 张卡牌，包含小目标训练（0.08-0.15 缩放）
   - **缩放分级**：根据卡牌数量动态调整
     - 1 张：0.7-0.8（超大）
     - 2 张：0.35-0.45（大）
     - 3 张：0.25-0.35（中）
     - 8+ 张：0.08-0.15（小目标训练）
   - 参考实现：1vcian/Pokemon-TCGP-Card-Scanner/trainCreator.py
   - 位置：`scripts/generate_dataset.py`

4. **实现训练脚本**
   - `download_assets.py` - 并发下载卡牌（jsDelivr CDN）
   - `download_backgrounds.py` - 下载 sample-images 背景
   - `train.py` - YOLO 训练脚本（MPS 支持）

### 进行中 ⏳（由用户执行）

5. **生成数据集并训练**
   - 生成 300-1000 张双模式数据集
   - 训练 100 epochs（M3 MacBook Air，MPS 加速）
   - 验证 mAP50 指标

6. **整合到主项目** - 准备开始
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

### 1. 数据生成（双模式 v2）

**参考实现**：1vcian/Pokemon-TCGP-Card-Scanner/trainCreator.py

**双模式设计**（2026-01-31 实现）：

| 模式 | 占比 | 卡牌数量 | 缩放范围 | 用途 |
|-----|------|---------|---------|-----|
| 网格模式 | 50% | 50-300张 | 自适应 | 密集场景训练 |
| 随机-少量 | 15% | 1-3张 | 0.25-0.8 | 大目标检测 |
| 随机-多量 | 35% | 8-15张 | **0.08-0.15** | 小目标检测 |

**缩放分级**（原作者算法）：
- 1张卡：0.7-0.8（超大，旋转角度 ±5°）
- 2张卡：0.35-0.45（大）
- 3张卡：0.25-0.35（中）
- 8+张卡：**0.08-0.15**（小目标，旋转角度 ±15°）

**技术细节**:
- 网格系统：5×4 网格 + 随机偏移（±10像素）
- IoU 阈值：0.1（允许卡牌更接近）
- YOLO OBB 格式：`class x1 y1 x2 y2 x3 y3 x4 y4`
- 背景多样性：50张不同场景（室内/自然/纹理）
- 备选：纯色背景（当没有背景图片时）

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

## 下一步行动（由用户执行）

### 1. 生成完整数据集并训练

**进入工作目录**:
```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto/yolo-card-training
```

**完整训练（1000张 + 100 epochs，约1-2小时）**:
```bash
# 生成 1000 张数据集（约30-40分钟）
time uv run python scripts/generate_dataset.py --total 1000 --output data/synthetic_v2

# 训练 100 epochs（约30-80分钟）
time uv run python scripts/train.py \
    --data data/synthetic_v2/data.yaml \
    --epochs 100 \
    --batch 16 \
    --device mps
```

**执行后验证**:
```bash
# 检查生成的数据集
echo "Train: $(ls data/synthetic_v2/images/train/*.jpg | wc -l) 张"
echo "Val: $(ls data/synthetic_v2/images/val/*.jpg | wc -l) 张"
echo "Test: $(ls data/synthetic_v2/images/test/*.jpg | wc -l) 张"

# 查看最新训练结果
ls -lt runs/obb/ | head -5
tail -n 2 runs/obb/*/results.csv | head -n 1
```

### 2. 验证训练结果

```bash
# 查看最新训练结果
ls -lt runs/obb/ | head -5

# 检查 mAP50
tail -n 2 runs/obb/*/results.csv | head -n 1

# 查看训练曲线
ls runs/obb/*/results.png | tail -1
```

**预期指标**:
- mAP50 > 0.9：数据集质量良好，算法有效
- mAP50 > 0.7：可用，但可能需要调整
- mAP50 < 0.7：检查数据集和标注

### 3. 当前待解决问题（2026-01-31）

#### 立即执行

11. **清理旧文件并重新测试**
    - 删除 `yolo-card-training/output/test_crops/` 旧文件（透视变换生成的 480×670）
    - 修改脚本添加 `cv2.imwrite` 保存代码
    - 使用新命名规则：`card_1.jpg`, `card_2.jpg`...（去掉置信度）
    - 重新截图验证第 7 张卡牌（疑似 A1-227）

12. **调查哈希异常匹配**
    - 问题：A1-209 与疑似 A1-227 匹配度 0.7（颜色完全不同）
    - 可能原因：特殊稀有度卡有相似边框/特效
    - 需要：可视化对比两张卡的哈希差异

13. **补充缺失卡牌**
    - 数据库缺少 A1-227 等后续编号
    - 需要：确认当前画面是否包含非 A1 系列卡牌
    - 或：下载补充 A1-227 到数据库

#### 后续优化

14. **阈值调优**
    - 当前阈值 0.80，匹配率 71.4%（5/7 张）
    - 尝试阈值 0.78 提高召回率
    - 观察是否会引入误匹配

15. **模型定版**
    - 当前模型 mAP50 0.995，表现优秀
    - 建议生产阈值：0.80
    - 准备整合到主项目

### 4. 整合到主项目（后续）

待上述问题解决后：
1. 导出 CoreML 格式
2. 在 `feature/yolo-hash` 分支更新检测器
3. 完整 Pipeline 验证

---

## 关键代码文件（2026-02-01 更新）

### 核心检测与匹配脚本

| 文件 | 功能 | 关键配置 |
|------|------|----------|
| `test_massive_matching.py` | **主测试脚本** - YOLO检测 + 哈希匹配完整流程 | 阈值: 0.68, 排序: 从左到右从上到下 |
| `test_yolo_hash_match.py` | **哈希工具库** - 感知哈希计算与比对 | HASH_SIZE=96, FREQ_SIZE=8, 使用 scipy DCT |
| `generate_hash_db.py` | **数据库生成** - 遍历卡牌生成哈希数据库 | 支持 PNG/WebP/JPG, 使用 PIL 统一处理 |
| `download_assets.py` | **资源下载** - 从用户仓库下载中文 PNG 卡牌 | 来源: shelken/ptcgp-assets |

### 重要实现细节

**1. 颜色空间统一处理**
```python
# 所有图片统一使用 PIL 处理，确保一致性
def pil_to_color_pixels(pil_image):
    if pil_image.mode == 'RGBA':
        pil_image = pil_image.convert('RGB')
    pil_image = pil_image.resize((96, 96), Image.BICUBIC)
    # ... DCT 计算
```

**2. 双阈值系统**
```python
# YOLO 检测阈值（框选质量）
conf_threshold = 0.6  # 置信度 ≥ 0.6 的框才保留

# 哈希匹配阈值（身份确认）
similarity_threshold = 0.68  # 相似度 ≥ 0.68 才认为是同一张卡
```

**3. 终端可视化**
- 绿色外框：YOLO 检测框 + 置信度标注（框上方）
- 红色内框：哈希匹配成功 + 卡牌ID标注（框内居中）
- 高度：1000px（终端显示优化）

---

## 文件参考（历史）

**关键文件位置**：
- **双模式数据集生成器**：`yolo-card-training/scripts/generate_dataset.py`
  - 实现网格模式 + 随机模式
  - 支持 50 张背景，107 张卡牌
- **训练脚本**：`yolo-card-training/scripts/train.py`
- **数据集配置**：`yolo-card-training/data/synthetic_v2/data.yaml`
- **实际模型输出**：`runs/obb/*/weights/best.pt`
- **CoreML 输出**：`runs/obb/*/weights/best.mlpackage`

**工作目录**：`yolo-card-training/`
```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto/yolo-card-training
direnv allow  # 自动加载环境
```

**外部资源**：
- 参考项目：https://github.com/1vcian/Pokemon-TCGP-Card-Scanner
- 卡牌图片来源：https://github.com/marcelpanse/tcg-pocket-collection-tracker
- 背景图片来源：https://github.com/yavuzceliker/sample-images
- YOLO11 OBB 文档：https://docs.ultralytics.com/tasks/obb/
