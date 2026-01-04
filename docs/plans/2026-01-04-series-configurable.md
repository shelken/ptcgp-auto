# 系列（Series）配置化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将硬编码的 A/B 系列改为可配置列表，方便未来添加 C 或更多系列

**Architecture:** 在 locale 配置中新增 `SERIES` 列表定义系列顺序，TEXT_PATTERNS 中的 `series_a`/`series_b` 合并为 `series` 字典结构，代码按配置顺序遍历所有系列

**Tech Stack:** Python, 配置驱动

---

## Task 1: 修改 locale 配置

**Files:**
- Modify: `locales/zh_Hant.py`
- Modify: `locales/en_US.py`

**Step 1: 修改 zh_Hant.py**

在 `DECK_KEYWORD` 之后添加：

```python
# 系列列表（按此顺序遍历）
SERIES = ["A", "B"]
```

修改 TEXT_PATTERNS，将 `series_a` 和 `series_b` 合并为 `series` 字典：

```python
TEXT_PATTERNS = {
    "auto": ["自動"],
    "series": {
        "A": ["A系列"],
        "B": ["B系列"],
    },
    "skip_titles": ["選擇擴充組", "系列"],
    "no_battles": ["沒有可挑戰的對戰"],
}
```

**Step 2: 修改 en_US.py**

同样添加：

```python
SERIES = ["A", "B"]
```

修改 TEXT_PATTERNS：

```python
TEXT_PATTERNS = {
    "auto": ["Auto", "AUTO"],
    "series": {
        "A": ["A Series", "Series A"],
        "B": ["B Series", "Series B"],
    },
    "skip_titles": ["Select Expansion", "Series"],
    "no_battles": ["no battles available", "There are no battles"],
}
```

**Step 3: Commit**

```bash
git add locales/zh_Hant.py locales/en_US.py
git commit -m "refactor(locale): add SERIES config and merge series patterns

新增 SERIES 列表配置，将 series_a/series_b 合并为 series 字典"
```

---

## Task 2: 修改 config.py 加载 SERIES

**Files:**
- Modify: `config.py`

**Step 1: 添加 SERIES 变量**

在 `DECK_KEYWORD = None` 之后添加：

```python
SERIES = None
```

**Step 2: 修改 load_language() 加载 SERIES**

```python
def load_language(lang: str = None):
    """加载语言配置"""
    global LANGUAGE, _locale, BATTLE_LEVELS, PAGES, TEXT_PATTERNS, DECK_KEYWORD, SERIES
    if lang:
        LANGUAGE = lang
    _locale = import_module(f"locales.{LANGUAGE}")
    BATTLE_LEVELS = _locale.BATTLE_LEVELS
    PAGES = _locale.PAGES
    TEXT_PATTERNS = _locale.TEXT_PATTERNS
    DECK_KEYWORD = _locale.DECK_KEYWORD
    SERIES = _locale.SERIES
```

**Step 3: Commit**

```bash
git add config.py
git commit -m "refactor(config): load SERIES from locale"
```

---

## Task 3: 修改 actions/expansion.py 使用动态系列

**Files:**
- Modify: `actions/expansion.py`

**Step 1: 修改系列按钮检测逻辑**

将：

```python
has_series_button = {"A": None, "B": None}

series_a_patterns = config.TEXT_PATTERNS.get("series_a", [])
series_b_patterns = config.TEXT_PATTERNS.get("series_b", [])
```

改为：

```python
has_series_button = {s: None for s in config.SERIES}

series_patterns = config.TEXT_PATTERNS.get("series", {})
```

**Step 2: 修改 OCR 扫描逻辑**

将硬编码的 A/B 匹配：

```python
for pattern in series_a_patterns:
    if pattern in text:
        has_series_button["A"] = item['box']
        break
for pattern in series_b_patterns:
    if pattern in text:
        has_series_button["B"] = item['box']
        break
```

改为动态遍历：

```python
for series_name, patterns in series_patterns.items():
    for pattern in patterns:
        if pattern in text:
            has_series_button[series_name] = item['box']
            break
```

**Step 3: 修改系列状态判断逻辑**

将：

```python
if not tried_expansion_series:
    current_series = "init"
elif "A" in tried_expansion_series and "B" not in tried_expansion_series:
    current_series = "B"
elif "A" in tried_expansion_series and "B" in tried_expansion_series:
    # 所有系列都已检查
    ...
else:
    current_series = "A"
```

改为基于 config.SERIES 的动态判断：

```python
# 找出尚未尝试的系列
untried_series = [s for s in config.SERIES if s not in tried_expansion_series]

if not tried_expansion_series:
    current_series = "init"
elif not untried_series:
    # 所有系列都已检查
    print("  -> 所有系列都已检查，关闭扩充组选择")
    set_tried_expansion_series(set())
    set_all_packs_checked(True)
    self._close_expansion_select(screenshot, ocr_results)
    return
else:
    # 继续处理第一个未尝试的系列
    current_series = untried_series[0]
```

**Step 4: 修改 init 状态处理**

将：

```python
if current_series == "init":
    if has_series_button["A"]:
        print("  -> 点击 A 系列按钮确保在 A 系列")
        new_series = tried_expansion_series.copy()
        new_series.add("clicked_A")
        ...
```

改为：

```python
if current_series == "init":
    first_series = config.SERIES[0]
    if has_series_button[first_series]:
        print(f"  -> 点击 {first_series} 系列按钮确保在 {first_series} 系列")
        new_series = tried_expansion_series.copy()
        new_series.add(f"clicked_{first_series}")
        set_tried_expansion_series(new_series)
        self.adb.tap_center(has_series_button[first_series])
        return
    else:
        current_series = first_series
        new_series = tried_expansion_series.copy()
        new_series.add(f"clicked_{first_series}")
        set_tried_expansion_series(new_series)
```

**Step 5: 修改 clicked 状态判断**

将：

```python
if "clicked_A" in tried_expansion_series and "A" not in tried_expansion_series:
    current_series = "A"
```

改为：

```python
first_series = config.SERIES[0]
if f"clicked_{first_series}" in tried_expansion_series and first_series not in tried_expansion_series:
    current_series = first_series
```

**Step 6: 修改切换系列逻辑**

将：

```python
other_series = "B" if current_series == "A" else "A"
if other_series not in tried_expansion_series and has_series_button[other_series]:
```

改为：

```python
# 找下一个未尝试的系列
next_series = None
for s in config.SERIES:
    if s not in tried_expansion_series and s != current_series and has_series_button[s]:
        next_series = s
        break

if next_series:
    print(f"  -> {current_series} 系列无可用卡包，切换到 {next_series} 系列")
    self.adb.tap_center(has_series_button[next_series])
    return
```

**Step 7: Commit**

```bash
git add actions/expansion.py
git commit -m "refactor(expansion): use dynamic SERIES config

将硬编码的 A/B 系列改为遍历 config.SERIES"
```

---

## Task 4: 修改 state_manager.py 支持动态系列

**Files:**
- Modify: `state_manager.py`

**Step 1: 修改 _needs_migration() 检测逻辑**

将：

```python
# 如果 key 不以 a_ 或 b_ 开头（旧格式3），需要迁移
if not (key.startswith("a_") or key.startswith("b_")):
    return True
```

改为：

```python
# 检查 key 是否以任一已配置系列的小写前缀开头
valid_prefixes = [f"{s.lower()}_" for s in config.SERIES]
if not any(key.startswith(prefix) for prefix in valid_prefixes):
    return True
```

**Step 2: 修改 _create_default_state()**

将：

```python
"current_series": "A",  # 当前系列 A/B
```

改为：

```python
"current_series": config.SERIES[0] if config.SERIES else "A",  # 当前系列
```

**Step 3: 修改 get_current_series()**

将：

```python
return self.state.get("current_series", "A")
```

改为：

```python
default = config.SERIES[0] if config.SERIES else "A"
return self.state.get("current_series", default)
```

**Step 4: 修改 switch_to_next_series()**

将：

```python
def switch_to_next_series(self) -> Optional[str]:
    """切换到下一个系列，返回新系列名，如果没有更多系列返回 None"""
    current = self.get_current_series()
    if current == "A":
        self.set_current_series("B")
        return "B"
    return None  # B 之后没有更多系列
```

改为：

```python
def switch_to_next_series(self) -> Optional[str]:
    """切换到下一个系列，返回新系列名，如果没有更多系列返回 None"""
    current = self.get_current_series()
    try:
        current_index = config.SERIES.index(current)
        if current_index + 1 < len(config.SERIES):
            next_series = config.SERIES[current_index + 1]
            self.set_current_series(next_series)
            return next_series
    except ValueError:
        pass
    return None  # 没有更多系列
```

**Step 5: Commit**

```bash
git add state_manager.py
git commit -m "refactor(state): support dynamic SERIES config

将硬编码的 A/B 系列切换改为基于 config.SERIES 列表"
```

---

## Task 5: 验证和测试

**Step 1: 验证模块加载**

```bash
python -c "import config; print('SERIES:', config.SERIES); print('series patterns:', config.TEXT_PATTERNS.get('series', {}))"
```

预期输出：
```
SERIES: ['A', 'B']
series patterns: {'A': ['A系列'], 'B': ['B系列']}
```

**Step 2: 验证 state_manager**

```bash
python -c "
import config
from state_manager import StateManager
sm = StateManager('/tmp/test_state.json')
print('current_series:', sm.get_current_series())
print('next_series:', sm.switch_to_next_series())
print('next_series:', sm.switch_to_next_series())
"
```

预期输出：
```
current_series: A
next_series: B
next_series: None
```

**Step 3: 运行主程序测试**

```bash
python main.py -a 5555
```

验证扩充组页面能正确识别和切换系列。

---

## 总结

### 变更统计

| 项目 | 变更 |
|------|------|
| 新增配置项 | SERIES 列表 |
| TEXT_PATTERNS 结构 | series_a/series_b → series 字典 |
| 修改文件数 | 5 |
| 硬编码消除 | 所有 "A"/"B" 字面量 |

### 收益

1. **可扩展性**: 添加新系列只需在 SERIES 和 series patterns 中添加条目
2. **配置集中**: 系列定义统一在 locale 配置中
3. **代码健壮性**: 使用列表遍历代替硬编码判断
