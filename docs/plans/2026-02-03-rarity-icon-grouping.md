# 稀有度图标分组识别 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在卡牌列表页使用筛选面板定位高稀有度（SR/SAR/IM/UR/SSR），通过 YOLO+Hash 识别具体卡牌并写入 account_cards 关联表，同时提供可复用的小图标分组检测能力。

**Architecture:** 复用 TemplateMatcher 进行图标模板检测，按行聚类+间距分组输出 IconGroup；通过稀有度反向映射定位筛选按钮；筛选后调用 YOLO+Hash 识别卡牌；结果写入 account_cards（仅拥有/未拥有，count=1，localtime 时间戳）。

**Tech Stack:** Python, OpenCV, 现有 TemplateMatcher、ADB 缩放体系、YOLO+Hash 识别器、SQLModel/SQLite。

---

## 用户原始诉求（原文）

> 我打算做个功能，收集每个账号高稀有度卡牌信息
> 
> 目前有几个难点：
> 首先是中，稀有度都是由图标组成的，他的稀有度是一个星星组成，例如一星就是一颗星星，2星就是2个星星并排在一起，还有钻石图标。一共四个等级，一钻二钻三钻四钻。
> 
> 其实我可以直接截取对应的图来匹配，但是我在想是否可以通过一个星星，然后根据他们的距离远近判断是否是一组，最后能够汇总信息拿到每个稀有度的方位。
>
> 还有我觉得你得把这个分组小图标抽象出一些方法，例如有时候我希望统计当前页面出现几个[template_name], 或者统计某个template按照x个数量分组后，出现在哪个方位，出现几次。

---

## 页面与模板约定

### 页面流转（任务内 pages 规则）

- **卡牌页识别**：OCR 精确匹配“自己的卡牌”
- **筛选面板识别**：OCR 关键字“稀有度/OK/清除”等
- **排序面板识别**：OCR 关键字“排序/按卡牌獲得順序”等

### 模板清单

- **新增模板**：`icon_bottom_card`（底部卡牌入口）、`icon_search`（筛选按钮）、`icon_sort`（排序按钮）
- **已有模板**：`icon_arrow_up`（排序方向确认）
- **关闭弹窗**：复用已有通用关闭逻辑（不新增 btn_close）

---

### Task 1: 新增配置文件（稀有度图标与映射）

**Files:**
- Create: `src/ptcgp_auto_v2/config/rarity_icons.py`

**Step 1: 写入配置结构**
```python
# -*- coding: utf-8 -*-
"""稀有度图标配置（基于 1080x1920 基准像素）"""

# 模板路径（相对 templates/）
RARITY_ICON_TEMPLATES = {
    "diamond": "icon_diamond.png",
    "star": "icon_star.png",
    "shiny_star": "icon_shiny_star.png",
    "crown": "icon_crown.png",
}

# 分组参数（基于 1080x1920）
RARITY_GROUP_DEFAULTS = {
    "threshold": 0.8,
    "nms_iou": 0.3,
    "row_tol_px": 24,
    "gap_px": 60,
    "min_count": 1,
}

# 正向映射：检测结果 -> rarity_code
RARITY_CODE_MAP = {
    ("diamond", 1): "C",
    ("diamond", 2): "U",
    ("diamond", 3): "R",
    ("diamond", 4): "RR",
    ("star", 1): "AR",
    ("star", 2): "SR",
    ("star", 3): "IM",
    ("shiny_star", 1): "S",
    ("shiny_star", 2): "SSR",
    ("crown", 1): "UR",
}

# 反向映射：rarity_code -> (template_name, count)
RARITY_CODE_REVERSE = {
    "SR": ("star", 2),
    "SAR": ("star", 2),
    "IM": ("star", 3),
    "UR": ("crown", 1),
    "SSR": ("shiny_star", 2),
}
```

**Step 2: 注释说明缩放**
- 在配置文件注明：实际像素 = `adb.scaled_x/adb.scaled_y` 对基准像素缩放。

---

### Task 2: 实现通用小图标分组检测模块

**Files:**
- Create: `src/ptcgp_auto_v2/infra/icon_group_detector.py`

**Step 1: 定义数据结构**
```python
@dataclass
class IconHit:
    template_name: str
    score: float
    box: Tuple[int, int, int, int]
    center: Tuple[float, float]

@dataclass
class IconGroup:
    template_name: str
    count: int
    boxes: List[Tuple[int, int, int, int]]
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
```

**Step 2: 复用 TemplateMatcher 进行检测**
- 通过 `TemplateMatcher.load_template()` 载入 `RARITY_ICON_TEMPLATES` 中的模板
- 使用 `TemplateMatcher.find_all()` 获取匹配框与置信度
- 统一输出 `IconHit` 列表
- 仅在 ROI 区域内检测（ROI 输入由调用方提供）

**Step 3: 分组逻辑**
- 按 y 轴聚类为行（`row_tol_px`）
- 行内按 x 排序，按 `gap_px` 进行同组划分
- 输出 `IconGroup`（含 bbox 和中心点）

**Step 4: 对外查询接口**
```python
def count_icons(template_name: str, hits: List[IconHit]) -> int:
    return sum(1 for h in hits if h.template_name == template_name)

def group_icons(template_name: str, groups: List[IconGroup], min_count: int) -> List[IconGroup]:
    return [g for g in groups if g.template_name == template_name and g.count >= min_count]

def find_group_by_rarity(rarity_code: str, groups: List[IconGroup]) -> Optional[IconGroup]:
    # 通过 RARITY_CODE_REVERSE 反查 (template_name, count)
    # 返回排序后的最佳候选（优先置信度或左到右）
```

---

### Task 3: 新任务入口与筛选流程

**Files:**
- Create: `src/ptcgp_auto_v2/tasks/collect_account_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/__init__.py`（如需导出）

**Step 1: 页面识别规则（任务内 pages）**
- 首页：匹配模板 `icon_bottom_card`
- 卡牌页：OCR 精确匹配“自己的卡牌”
- 筛选面板：OCR 关键字“稀有度/OK/清除”
- 排序面板：OCR 关键字“排序/按卡牌獲得順序”

**Step 2: 页面处理流程**
1) 点击 `icon_bottom_card` 进入卡牌页
2) 点击 `icon_search` 打开筛选面板
3) 向下滑动一次，保证稀有度图标展示完整
4) 使用分组检测与反向映射选中 SR/SAR/IM/UR/SSR
5) 点击 OK 回到卡牌页
6) 点击 `icon_sort` 打开排序面板
7) 确保“按卡牌获得顺序”且 `icon_arrow_up` 存在（最新->最旧）
8) 关闭排序弹窗回到卡牌页
9) 两指缩放到一行 5 张卡牌（新增手势）
10) 执行 YOLO+Hash 识别与数据写入
11) 下滑直到 OCR 文本稳定（无变化）结束任务

> 说明：当前阶段不实现两指缩放，先按默认 3 列识别；后续引入多指注入工具再补充缩放手势。

---

### Task 4: 数据库表与仓库层

**Files:**
- Create: `src/ptcgp_auto_v2/db/models/account_card.py`
- Modify: `src/ptcgp_auto_v2/db/models/__init__.py`
- Create: `src/ptcgp_auto_v2/db/repositories/account_card_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/__init__.py`

**Step 1: 新表 account_cards**
- 使用 `TimestampMixin`（localtime）
- 字段：`id`, `account_id`, `card_id`, `count`

**Step 2: 仓库接口**
- `upsert(account_id, card_id, count=1)`
- 允许重复识别时更新 count（当前固定 1）

---

### Task 5: YOLO+Hash 识别接入

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/collect_account_cards.py`

**Step 1: 识别卡牌**
- 复用 `yolo_card_recognizer.py` 的现有识别方法
- 针对当前页面卡牌区域识别卡牌 ID

**Step 2: 写入 account_cards**
- 仅保存高稀有度识别结果（SR/SAR/IM/UR/SSR）
- 仅记录“拥有/未拥有”（count=1）

---

### Task 6: 单元测试（分组逻辑 + DAO）

**Files:**
- Create: `tests/test_icon_group_detector.py`
- Create: `tests/test_account_card_repository.py`

**Step 1: 写最小分组测试**
```python
def test_group_icons_by_row_and_gap():
    hits = [
        IconHit("diamond", 0.9, (0, 0, 10, 10), (5, 5)),
        IconHit("diamond", 0.9, (20, 0, 30, 10), (25, 5)),
        IconHit("diamond", 0.9, (60, 0, 70, 10), (65, 5)),
    ]
    groups = group_hits(hits, row_tol=6, gap=25)
    assert [g.count for g in groups] == [2, 1]
```

**Step 2: 写 DAO upsert 测试**
```python
def test_account_card_upsert(session):
    repo = AccountCardRepository(session)
    repo.upsert(account_id=1, card_id=10, count=1)
    repo.upsert(account_id=1, card_id=10, count=1)
    row = repo.get(account_id=1, card_id=10)
    assert row.count == 1
```

**Step 3: 运行测试**
Run: `pytest tests/test_icon_group_detector.py::test_group_icons_by_row_and_gap -v`
Run: `pytest tests/test_account_card_repository.py::test_account_card_upsert -v`

---

### Task 7: 文档更新

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Step 1: 记录新模块与配置**
- 增加 `config/rarity_icons.py`、`infra/icon_group_detector.py`、`account_cards` 表说明

---

### Task 8: 手工验证

**Step 1: 使用 debug_tool 观察模板匹配**
Run: `python debug_tool.py -a 127.0.0.1:[PORT] --template icon_diamond`

**Step 2: 验证分组数量**
- 运行任务后输出分组数量与坐标，确认与筛选面板一致

---

## 已知限制与后续改进

- 金色卡（crown）边框检测效果不佳，YOLO 在列表页可能无法稳定检测；后续通过训练更完善的模型解决。
