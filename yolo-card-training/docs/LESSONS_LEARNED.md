# 训练项目踩坑记录

## 错误 1：flake 与 direnv 使用不当

**问题**：在 `.envrc` 中写 shell 逻辑（`uv venv`, `uv pip install`）

**错误代码**：
```bash
# .envrc - 错误！
export UV_PROJECT_DIR="$PWD"
if [[ ! -d "$PWD/.venv" ]]; then
    uv venv "$PWD/.venv"
fi
source "$PWD/.venv/bin/activate"
uv pip install -r requirements.txt  # 错误：应该使用 flake.nix
```

**原因**：使用 nix flake 时，环境定义应在 `flake.nix` 中，`.envrc` 只应有一行 `use flake`

**正确做法**：
```nix
# flake.nix
shellHook = ''
  uv sync
  source .venv/bin/activate
'';
```

```bash
# .envrc - 正确！
use flake
```

---

## 错误 2：混用 pip 和 uv

**问题**：用户明确说用 uv，但我还在用 pip

**错误代码**：
```bash
source .venv/bin/activate && pip list  # 错误！
```

**正确做法**：
```bash
source .venv/bin/activate && uv pip list  # 正确
```

---

## 错误 3：没有提前告知耗时操作

**问题**：运行下载脚本前没有告知需要 2-3 分钟，导致超时

**必须提前告知**：
- 下载 100 张卡牌：约 2-3 分钟
- 生成 10,000 张合成数据：约 30-60 分钟
- 训练模型（100 epoch）：约 1-2 小时

---

## 错误 4：假设错误的 API 结构

**问题**：没有验证就假设 URL 结构是 `A4/collection.json`

**实际结构**：
```
# 错误假设
https://raw.githubusercontent.com/.../A4/collection.json
https://raw.githubusercontent.com/.../A4/{card_id}.png

# 实际结构
https://raw.githubusercontent.com/.../en-US/A1-1.webp
https://raw.githubusercontent.com/.../en-US/{set}-{num}.webp
```

**教训**：
1. 先用 curl/API 查看实际结构
2. 不要假设，要验证
3. 文件格式可能是 webp 不是 png

---

## 错误 5：没有明确 YOLO 在当前项目的具体作用

**问题**：没有理解核心需求，误以为要检测"单张卡牌"，实际需要检测"图中所有卡牌（数量不限）"

**错误理解**：
- 以为：YOLO 检测 → 得到1张卡牌 → 识别它
- 实际：YOLO 检测 → 得到N个边界框 → 截取N张 → 逐个识别

**根本原因**：
没有先问清楚：
1. 检测单张还是多张？
2. 数量固定还是不定？
3. 输出干什么用？（截取后做哈希匹配）

**正确做法**：
- 先问清楚需求场景
- 明确 YOLO 的作用是"检测所有卡牌位置"，不是"识别卡牌内容"
- 理解整个 pipeline：检测 → 透视变换 → 哈希匹配

---

## 错误 6：uv 使用不当 - 目录混乱

**问题**：在子项目中执行命令，但没有 `cd` 进入正确目录，导致使用了错误的虚拟环境

**错误示例**：
```bash
# ❌ 错误：在根目录执行，使用了根目录的 .venv/
cd /Users/shelken/Code/active/ptcgp-auto
uv run python yolo-card-training/scripts/train.py

# ❌ 错误：修改 pyproject.toml 后没有 sync
uv add coremltools
# 直接运行，发现依赖不存在
```

**正确做法**：
```bash
# ✅ 必须先进入项目目录
cd /Users/shelken/Code/active/ptcgp-auto/yolo-card-training

# ✅ 使用 uv run（会自动使用当前目录的 .venv/）
uv run python scripts/train.py

# ✅ 添加依赖后必须 sync
uv add coremltools
uv sync

# ✅ 或者直接使用完整路径
uv run --project yolo-card-training python scripts/train.py
```

**关键原则**：
1. 每个子项目有自己的 `.venv/`，必须在项目目录内执行 `uv run`
2. 修改 `pyproject.toml` 后必须执行 `uv sync` 同步到虚拟环境
3. 不确定时，先用 `pwd` 确认当前目录

---

## 错误 7：RGBA 转 BGR 通道错误

**问题**：ADB 截图是 RGBA（4通道），直接传给 YOLO 导致错误

**错误代码**：
```python
# ❌ 错误：RGBA 4 通道直接传给模型
img = Image.open(screenshot_path)  # RGBA
results = model(img)  # RuntimeError: expected 3 channels, got 4
```

**正确做法**：
```python
# ✅ 先转 RGB，再转 BGR（YOLO/OpenCV 格式）
import cv2
import numpy as np
from PIL import Image

img = Image.open(screenshot_path)  # RGBA
img_array = np.array(img)

# RGBA -> RGB -> BGR
if img_array.shape[2] == 4:
    img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

results = model(img_bgr)
```

---

## 错误 8：混淆模型输出路径

**问题**：脚本中硬编码路径 `output/models/...`，但 ultralytics 实际输出到 `runs/`

**错误**：
```python
# ❌ 错误：假设输出到指定路径
model.train(
    project="output/models",  # 这个参数被 ultralytics 忽略或覆盖了
    name="card_obb",
)
# 实际输出到：runs/obb/output/models/card_obb/weights/best.pt
```

**解决方案**：
1. 训练前先用 `find` 确认实际输出路径
2. 脚本中使用相对路径 `../runs/...` 或动态查找
3. 或修改 ultralytics 配置改变默认输出目录（不推荐）

---

## 错误 9：无脑复制低效算法（DCT 性能灾难）

**问题**：直接复制 yolo-hash 分支的 DCT 实现，使用纯 Python 四重循环，导致每张卡牌哈希计算需要 ~1500ms

**错误代码**（四重循环版）：
```python
def _compute_dct(pixels: list) -> list:
    """纯 Python 嵌套循环 - 极慢！"""
    n = int(np.sqrt(len(pixels)))
    result = [0.0] * (FREQ_SIZE * FREQ_SIZE)
    
    for u in range(FREQ_SIZE):        # 8 次
        for v in range(FREQ_SIZE):    # 8 次
            total = 0.0
            for y in range(n):        # 96 次
                for x in range(n):    # 96 次
                    total += pixels[y * n + x] * np.cos(...) * np.cos(...)
            result[u * FREQ_SIZE + v] = ((2 * cu * cv) / n) * total
    
    return result
# 总运算量: 8 × 8 × 96 × 96 = 589,824 次浮点运算/通道
# 每张卡 (3通道): ~1.8M 次运算
# 实际耗时: 1500ms × 3 = 4500ms/张
```

**性能灾难**：
- 7 张卡牌识别总耗时: **~10.5 秒**
- 用户反馈: "为什么这么慢？？"

**优化方案**（scipy FFT）：
```python
def _compute_dct(pixels: list) -> list:
    """scipy FFT 加速版 - 快 1800 倍！"""
    from scipy.fftpack import dct
    
    n = int(np.sqrt(len(pixels)))
    img = np.array(pixels, dtype=np.float32).reshape(n, n)
    
    # scipy 使用 Cooley-Tukey FFT 算法 + SIMD 优化
    dct_rows = dct(img, type=2, norm='ortho', axis=0)
    dct_2d = dct(dct_rows, type=2, norm='ortho', axis=1)
    
    return dct_2d[:FREQ_SIZE, :FREQ_SIZE].flatten().tolist()
# 时间复杂度: O(n² log n) vs O(n⁴)
# 实际耗时: 0.8ms × 3 = 2.4ms/张 (快 1800 倍！)
```

**优化后性能**：
- 7 张卡牌识别总耗时: **~5.6 毫秒**
- 速度提升: **1775 倍**

**对比结果**（实际测试）：
```
卡牌 #1:
  🔴 原始 DCT: 1509.0ms
  🟢 Scipy DCT: 0.8ms
  ⚡ 速度提升: 1775x
```

**根本原因**：
1. **无脑复制** yolo-hash 分支代码，没有思考算法效率
2. **没有性能基准**，不知道"慢"是相对于什么
3. **没有预先调研**，不知道 scipy 有 FFT 优化

**正确做法**：
1. **先查标准库**：scipy/numpy 是否有现成实现？
2. **性能优先**：图像处理必须用 SIMD/FFT 优化
3. **对比测试**：保留原始实现用于验证正确性
4. **预留优化空间**：接口设计要能切换算法

**教训**：
- 图像/信号处理算法必须用优化库（scipy, opencv, fftw）
- 不要自己实现 DCT/DFT/卷积等基础算法，除非你是专家
- Python 纯循环比 C/优化库慢 100-1000 倍是常态

---

## 检查清单（下次避免）

- [ ] 确认使用纯 uv（不用 pip）
- [ ] 确认 flake.nix 定义环境，.envrc 只有 `use flake`
- [ ] 提前告知所有耗时操作
- [ ] 验证 URL/API 结构（用 curl 测试）
- [ ] 不在 Plan Mode 中执行命令
- [ ] 保持与根项目 flake 风格一致
- [ ] 复制代码前先验证算法效率，不要无脑复制
- [ ] 图像/信号处理优先使用 scipy/opencv 等优化库

---

## 正确的项目结构

```
yolo-card-training/
├── flake.nix          # 定义完整环境（uv sync + source .venv）
├── .envrc             # 只有一行: use flake
├── pyproject.toml     # uv 依赖定义
└── ...
```

**flake.nix 模板**（与根目录保持一致）：
```nix
{
  description = "...";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    utils.url = "github:numtide/flake-utils";
  };
  outputs = { self, nixpkgs, utils, ... }:
    utils.lib.eachDefaultSystem (system:
      let pkgs = import nixpkgs { inherit system; };
      in {
        devShells.default = pkgs.mkShell {
          packages = with pkgs; [ python312 uv ];
          UV_PYTHON_DOWNLOADS = "never";
          shellHook = ''
            uv sync
            source .venv/bin/activate
            echo "Environment ready"
          '';
        };
      });
}
```
