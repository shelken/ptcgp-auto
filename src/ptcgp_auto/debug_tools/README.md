# PTCGP 调试工具 (Debug Tools) CLI 指南

本文档详细介绍了 `debug_tool.py` 提供的各种命令行功能，用于调试 PTCGP 自动化脚本的识别、模板匹配和资源管理。

## 基础用法

所有命令均支持 `-a` (或 `--address`) 参数来指定 ADB 连接地址。如果未指定，默认连接 `127.0.0.1:5555`。

```bash
# 连接默认端口 (5555)
python debug_tool.py --ocr

# 连接指定端口
python debug_tool.py -a 5615 --ocr
```

---

## 功能详解

### 1. OCR 识别测试 (`--ocr`)

截图并在终端输出当前画面的 OCR 识别结果（文本内容和坐标）。

```bash
python debug_tool.py -a 5615 --ocr
```

### 2. 截图 (`--screenshot`)

仅截图并保存到调试目录，不进行识别。

```bash
python debug_tool.py -a 5615 --screenshot
```

### 3. 单模板匹配 (`--template`)

在当前画面中查找指定的模板图片。支持自动缩放扫描。

**参数：**
*   `--template NAME`: 模板名称（不含路径和后缀）或文件路径。
*   `--scale FLOAT`: （可选）指定缩放比例。如果不指定，工具会自动尝试在 0.1-3.0 范围内扫描最佳缩放比例。
*   `--threshold FLOAT`: （可选）置信度阈值（默认 0.8）。

**示例：**

```bash
# 自动扫描缩放比例查找 "ok_button"
python debug_tool.py -a 5615 --template ok_button

# 指定缩放比例查找
python debug_tool.py -a 5615 --template ok_button --scale 1.0
```

### 4. 卡牌匹配与自动下载 (`--cards`)

这是最强大的功能，支持从数据库查询卡牌、自动下载图片资源、按稀有度筛选并进行匹配。

**参数：**
*   `--cards QUERY`: 查询字符串，支持三种模式：
    *   **系列模式**: `Series` (例如 `A1a`, `B1`) —— 下载并匹配该系列所有卡牌。
    *   **子包模式**: `Series/Pack` (例如 `A1a/Mew`) —— 下载并匹配该子包所有卡牌。
    *   **单卡模式**: `Series/Pack/Name` (例如 `A1a/Mew/001_Exeggcute`) —— 匹配特定卡牌。
*   `--rarity RARITY`: （可选）仅匹配指定稀有度的卡牌 (例如 `RR`, `AR`, `SAR`)。
*   `--select`: （可选）启用交互式菜单，手动选择要匹配的卡牌。
*   `--scale FLOAT`: （必选，除非是单卡模式）指定缩放比例。批量匹配时必须指定缩放以保证性能。
*   `--roi X,Y,W,H`: （可选）指定匹配区域 (Region of Interest)。格式为 x,y,w,h (例如 `0,500,1080,1000`)。仅在该区域内匹配可大幅提升速度。

**示例场景：**

#### 场景 A: 匹配 B1 系列中所有的 RR 卡牌
会自动下载缺失的图片资源。

```bash
python debug_tool.py -a 5615 --cards B1 --rarity RR --scale 0.69
```

#### 场景 B: 使用 ROI 加速匹配
如果您知道卡牌只会出现在屏幕中间（例如 y=500 到 y=1500），可以使用 `--roi` 进一步加速：

```bash
python debug_tool.py -a 5615 --cards A4b --scale 0.67 --roi 0,500,1080,1000
```

#### 场景 C: 交互式选择要测试的卡牌
```bash
python debug_tool.py -a 5615 --cards A1a/Mew --scale 0.69
```

#### 场景 C: 交互式选择要测试的卡牌
会弹出一个列表供选择，支持模糊搜索。选择后自动下载并匹配。

```bash
python debug_tool.py -a 5615 --cards B1 --rarity RR --select --scale 0.69
```

#### 场景 D: 匹配特定的一张卡 (自动扫描缩放)
单卡模式下可以不传 `--scale`，工具会自动计算最佳缩放。

```bash
python debug_tool.py -a 5615 --cards A1a/Mew/003_Celebi_ex
```

### 5. 性能统计与优化
执行 `--cards` 匹配时，工具会应用多种优化策略（快速筛选、多线程并发、ROI裁剪），并在最后输出详细的统计信息：

```text
Statistics:
  Total Duration   : 1.4410s    # 纯匹配耗时
  Templates Loaded : 379        # 加载的模板数量
  Match Attempts   : 379        # 总尝试次数
  Quick Skips      : 357        # 被快速筛选跳过的数量（极大节省时间）
  Match Hits       : 15         # 最终匹配命中的数量
```

**优化策略说明：**
1.  **快速筛选 (Quick Match)**: 自动将大图缩小 4 倍进行粗略匹配。只有通过筛选的模板才会进行原图精细匹配。这能过滤掉 90% 以上的不匹配项。
2.  **多线程并发 (Threading)**: 利用多核 CPU 并行处理匹配任务，显著减少总耗时。
3.  **区域裁剪 (ROI)**: 通过 `--roi` 参数指定关注区域，减少计算量（性能提升可达 2-3 倍）。

### 6. 模板制作工具

#### 交互式区域裁剪 (`--crop`)
截图后会打开一个 GUI 窗口，允许你框选区域并保存为新模板。

```bash
python debug_tool.py -a 5615 --crop
```

#### 专用卡包裁剪 (`--crop-pack`)
用于快速制作开包界面的卡包封面模板。

```bash
python debug_tool.py -a 5615 --crop-pack
```

---

## 常见问题

**Q: 为什么提示 "No templates loaded"?**
A:
1. 检查数据库中是否有对应系列的卡牌数据。
2. 检查 `--rarity` 是否正确（大小写敏感）。
3. 之前版本可能下载了带空格的文件名，新版本已自动修复。如果仍有问题，尝试手动删除 `templates/cards` 目录让其重新下载。

**Q: 如何确定 `--scale` 的值？**
A: 先用单卡模式（不加 `--scale`）匹配一张卡，工具会输出 `Found ... Scale=0.69`。然后将这个 `0.69` 用于该设备的批量匹配。不同设备/分辨率的 Scale 值不同。
