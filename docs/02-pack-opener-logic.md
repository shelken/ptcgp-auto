# 开包逻辑 + 模式架构重构计划

> 创建时间：2026-01-16
> 状态：**Phase 2 进行中（工具已就绪，待截取模板）**
> 前置文档：`docs/01-daily-pack-feature.md`

## 1. 概述

1. 引入**模式（Mode）**概念，将 PAGES 配置按模式分离
2. 在模式架构基础上实现每日开包功能

---

## 2. 模式架构（已完成）

### 2.1 设计理念

引入**模式（Mode）**概念，将 PAGES 配置按模式分离，不同模式加载不同的页面集合。

### 2.2 三种模式

| 模式 | 入口 | 页面数 | 说明 |
|------|------|--------|------|
| `battle` | 默认 | 26 | 自动对战（含教程检测和用户信息获取） |
| `tutorial` | `-t` | 8 | 教程解锁模式 |
| `daily` | `--daily` | 10 | 每日开包模式 |

### 2.3 页面组合

```
battle:   COMMON(6) + USER_INFO(3) + BATTLE(15) + TUTORIAL(2) = 26
tutorial: COMMON(6) + TUTORIAL(2) = 8
daily:    COMMON(6) + USER_INFO(3) + DAILY(1+) = 10+
```

### 2.4 文件结构

```
src/ptcgp_auto/locales/
├── zh_Hant.py              # 主配置（BATTLE_LEVELS, SERIES, TEXT_PATTERNS, MODES）
├── zh_Hant_pages/          # 繁体中文页面配置
│   ├── __init__.py         # 导出所有 PAGES_*
│   ├── common.py           # PAGES_COMMON - 通用页面
│   ├── user_info.py        # PAGES_USER_INFO - 用户信息页面
│   ├── battle.py           # PAGES_BATTLE - 对战模式页面
│   ├── tutorial.py         # PAGES_TUTORIAL - 教程模式页面
│   └── daily.py            # PAGES_DAILY - 开包模式页面
└── en_US.py                # 英文配置（暂未拆分）
```

### 2.5 使用方式

```python
from ptcgp_auto import config

# 加载对战模式（默认）
config.load_mode("battle")

# 加载每日开包模式
config.load_mode("daily")

# 加载教程模式
config.load_mode("tutorial")

# 查看当前模式
print(config.CURRENT_MODE)  # "battle"
print(len(config.PAGES))    # 26
```

---

## 3. 开包流程探索（进行中）

### 3.1 已验证的模板

| 模板 | 状态 | 位置 |
|------|------|------|
| `icon_pack_open` | ✅ 匹配 | (966, 426) |
| `icon_free_pack_available` | ✅ 匹配 | (448, 1094) |

### 3.2 开包流程

```
主页 → 点击开包图标 → 系列选择页 → 卡包选择页 → 开包动画 → 返回主页
```

### 3.3 卡包常量与数据

**数据结构：**

```
data/packs.json              # 卡包数据（可通过脚本更新）
scripts/fetch_packs.py       # 从 pokemon-tcg-pocket-database 抓取
src/ptcgp_auto/constants/    # 常量模块
├── __init__.py
└── packs.py                 # 加载 JSON 并提供接口
```

**数据来源：** [flibustier/pokemon-tcg-pocket-database](https://github.com/flibustier/pokemon-tcg-pocket-database)

**卡包代码格式：**

| 代码 | 名称 | 子包 |
|------|------|------|
| A1 | Genetic Apex | Pikachu, Charizard, Mewtwo |
| A1a | Mythical Island | - |
| A2 | Space-Time Smackdown | Dialga, Palkia |
| B1 | Mega Rising | Mega Blaziken ex, Mega Gyarados ex, Mega Altaria ex |
| ... | ... | ... |

**模板路径规则：**

- 有子包：`templates/packs/{code}/{booster}.png` (如 `packs/A1/Pikachu.png`)
- 无子包：`templates/packs/{code}/{name}.png` (如 `packs/A1a/Mythical_Island.png`)

**更新卡包数据：**

```bash
python scripts/fetch_packs.py
```

### 3.4 交互式区域选择工具

为方便截取卡包封面模板，添加交互式区域选择功能：

**通用模板截取：**

```bash
python debug_tool.py -a 5705 --crop
# 操作：截图 → 显示窗口 → 鼠标框选 → 回车确认 → 输入名称保存
```

**卡包模板专用截取：**

```bash
python debug_tool.py -a 5705 --crop-pack
# 操作：选择扩充包 → 选择子包 → 截图框选 → 自动保存到正确路径
```

功能特性：
- **ROI 缓存**：记住上次选区，快速复用相同区域截取多个模板
- **模板存在状态**：子包列表显示 `[✓]`/`[✗]` 标记模板文件是否存在
- **批量检测模式**：输入 `d` 一次截图批量匹配所有子包，显示置信度和匹配结果
- **多尺度匹配**：输入 `s` 设置缩放比例，支持自动计算（输入 `c`）
- **终端图片预览**：支持 Kitty 终端直接预览截取的模板（使用 `kitten icat`）
- **即时验证**：保存后立即重新加载模板并验证匹配

**卡包模板缩放比例配置** (`config.py`):
```python
PACK_TEMPLATE_SCALES = {
    "pack_list": 0.22,      # 扩充包列表页（很小）
    "pack_select": 0.81,    # 子包选择页（中等）
    "pack_detail": 1.0,     # 单包详情页（最大）
}
```

实现文件：
- `src/ptcgp_auto/debug_tools/region_selector.py` - 区域选择和 ROI 缓存
- `src/ptcgp_auto/debug_tools/crop_pack.py` - 卡包模板截取主逻辑
- `src/ptcgp_auto/debug_tools/terminal_preview.py` - Kitty 终端图片预览
- `src/ptcgp_auto/recognizer_parts/template_matcher.py` - 多尺度模板匹配

### 3.5 免费包机制

| 属性 | 说明 |
|------|------|
| 刷新周期 | 每 12 小时刷新 1 个 |
| 每日上限 | 一天最多 2 个免费包 |
| 可用检测 | **仅在主页**检测 `icon_free_pack_available` 模板 |

### 3.6 待添加的页面

| 页面 | 说明 | 状态 |
|------|------|------|
| `game_home_main` | 游戏主页（开包入口） | ✓ 已定义 |
| `pack_series_select` | 系列选择页面 | 待探索 |
| `pack_list` | 卡包列表页面 | 待探索 |
| `pack_opening` | 开包动画页面 | 待探索 |

---

## 4. 实现步骤

### Phase 1: 重构 PAGES 配置 ✅ 已完成

1. ✅ 创建 `locales/zh_Hant_pages/` 目录
2. ✅ 将现有 PAGES 拆分到各文件
3. ✅ 修改 `zh_Hant.py` 导入页面模块
4. ✅ 修改 `config.py` 添加 `load_mode()`
5. ✅ 修改 `main.py` 在入口处调用 `load_mode()`
6. ✅ 测试模式加载正常
7. ✅ 提交: `wip: refactor PAGES config with mode-based architecture`

### Phase 2: 探索开包界面（进行中）

1. [x] 修复 region_selector.py 改用 OpenCV
2. [x] 添加 `--crop` 通用区域截取功能
3. [x] 添加 `--crop-pack` 卡包模板专用截取功能
4. [x] 创建卡包常量模块 (`constants/packs.py`)
5. [x] 创建卡包数据文件 (`data/packs.json`)
6. [x] 创建数据更新脚本 (`scripts/fetch_packs.py`)
7. [x] 使用 `--crop-pack` 截取卡包封面模板（20个子包已完成）
8. [ ] 分析系列选择页面和卡包选择页面
9. [ ] 补充 `daily.py` 页面定义

### Phase 3: 实现开包逻辑

1. [ ] 实现 `click_pack_icon` 动作
2. [ ] 实现系列/卡包选择动作
3. [ ] 实现开包动画等待
4. [ ] 修改 `pack_opener.py` 整合状态机
5. [ ] 测试完整开包流程

---

## 5. 验收标准

- [x] `locales/zh_Hant_pages/` 目录创建成功
- [x] 页面配置正确拆分到各文件
- [x] `config.load_mode("battle")` 加载对战模式页面
- [x] `config.load_mode("daily")` 加载开包模式页面
- [x] 交互式区域选择工具可用 (`--crop`, `--crop-pack`)
- [x] 卡包常量模块可用 (`constants/packs.py`)
- [ ] 卡包封面模板截取完成
- [ ] 开包界面页面定义完整
- [ ] 开包流程测试通过
