# Pack Identifier Bug Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复卡包状态使用单一分母作为唯一标识符导致的 bug，改用左右分母组合作为主键

**Architecture:** 将状态管理中的 packs 结构从 `{右分母: {name, done}}` 改为 `{左分母_右分母: {name, done}}`（如 `20_81`），利用扩充组选择页面同一行的左右两个进度数字组合成唯一标识符

**Tech Stack:** Python 3.10+, Apple Vision OCR

---

## Bug 分析

### 现象

查看 `/tmp/ptcgp_auto_5575/state.json`:
```json
"packs": {
  "114": {"name": "", "done": true},
  "78": {"name": "", "done": true},
  "67": {"name": "異次元危機", "done": true},
  "102": {"name": "異次元危機", "done": true},
  "75": {"name": "異次元危機", "done": true},
  "81": {"name": "異次元危機", "done": true},
  ...
}
```

1. **名字对不上**: 多个不同分母都显示同一个卡包名 "異次元危機"
2. **有些分母为空**: 部分记录的 name 为空字符串

### 根本原因

**当前设计缺陷**: 仅使用右侧进度分母（如 `81`）作为卡包唯一标识符

问题出在 `expansion.py` 的逻辑：
- 扩充组选择页面每行显示两个进度：
  - **左侧**: `当前完成牌组数/总牌组数` (如 `5/20`)
  - **右侧**: `已收集卡数/总卡数` (如 `30/81`)
- 代码将 `right['total']`（右侧分母，总卡数）作为卡包标识符
- **但多个不同卡包可能有相同的总卡数**（如多个扩充包都有 81 张卡）

这导致：
- 标记一个卡包完成后，所有相同总卡数的卡包都被误认为已完成
- 状态记录时名字会被后来的记录覆盖

### 正确设计

应该使用**左右分母组合**作为唯一标识符：
- 格式: `{左分母}_{右分母}`（如 `20_81`）
- 左分母是总牌组数，右分母是总卡数
- 不同卡包的牌组数和卡数组合几乎不可能完全相同
- 无需依赖 OCR 识别卡包名称（更可靠）

---

## 扩充组选择页面布局分析

扩充组选择页面的布局：
```
┌─────────────────────────────────────────┐
│            選擇擴充組                    │
├─────────────────────────────────────────┤
│  [A系列]  [B系列]                        │
├─────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐ │
│  │   [卡包图片]   [卡包图片]            │ │
│  │   基因起源      神奧的光芒           │ │
│  │   5/20         8/25                 │ │  <- 左侧进度：牌组完成
│  │   30/81        45/81                │ │  <- 右侧进度：卡片收集
│  └─────────────────────────────────────┘ │
│  ┌─────────────────────────────────────┐ │
│  │   [卡包图片]   [卡包图片]            │ │
│  │   神秘小島      PROMO               │ │
│  │   3/15         2/10                 │ │
│  │   12/66        8/30                 │ │
│  └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

每个卡包卡片包含：
- 卡包图片
- 卡包名称（如 "基因起源"）
- 两个进度数字：
  - 上面是牌组完成进度（如 `5/20`）
  - 下面是卡片收集进度（如 `30/81`）

**唯一标识符**: `{牌组分母}_{卡片分母}` = `20_81`

---

## Task 1: 修改 StateManager 的 packs 数据结构

**Files:**
- Modify: `state_manager.py:105-145`

**Step 1: 更新类型注释和文档**

将 packs 结构从 `{右分母: {name, done}}` 改为 `{左分母_右分母: {name, done}}`

```python
    # ===== 卡包状态 =====
    # packs 结构: {"左分母_右分母": {"name": 卡包名, "done": bool}, ...}
    # 使用左右分母组合作为 key（如 "20_81"），因为不同卡包可能有相同的单一分母
    # 左分母 = 总牌组数，右分母 = 总卡数
```

**Step 2: 修改 is_pack_complete 方法**

```python
    def is_pack_complete(self, level: str, pack_id: str) -> bool:
        """检查指定等级的卡包是否完成（使用左右分母组合作为标识，如 '20_81'）"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            pack_info = packs.get(pack_id, {})
            return pack_info.get("done", False)
        return False
```

**Step 3: 修改 set_pack_complete 方法**

```python
    def set_pack_complete(self, level: str, pack_id: str, name: str = "", complete: bool = True):
        """标记卡包完成状态（使用左右分母组合作为标识，如 '20_81'）"""
        if level not in self.state["levels"]:
            self.state["levels"][level] = {"complete": False, "packs": {}}
        if pack_id not in self.state["levels"][level]["packs"]:
            self.state["levels"][level]["packs"][pack_id] = {"name": name, "done": False}
        self.state["levels"][level]["packs"][pack_id]["done"] = complete
        if name:
            self.state["levels"][level]["packs"][pack_id]["name"] = name
        if complete:
            pack_name = self.state["levels"][level]["packs"][pack_id].get("name", pack_id)
            print(f"[状态] {level} - {pack_name}({pack_id}) 已标记为完成")
        self.save()
```

**Step 4: 修改 get_pack_name 方法**

```python
    def get_pack_name(self, level: str, pack_id: str) -> Optional[str]:
        """获取卡包名称（通过左右分母组合）"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            pack_info = packs.get(pack_id, {})
            return pack_info.get("name")
        return None
```

**Step 5: 修改 get_incomplete_packs 方法**

```python
    def get_incomplete_packs(self, level: str) -> list:
        """获取指定等级未完成的卡包 ID 列表（左右分母组合）"""
        if level in self.state["levels"]:
            packs = self.state["levels"][level].get("packs", {})
            return [pack_id for pack_id, info in packs.items() if not info.get("done", False)]
        return []
```

**Step 6: 运行测试验证修改**

Run: `python -c "from state_manager import StateManager; print('StateManager import OK')"`
Expected: `StateManager import OK`

**Step 7: Commit**

```bash
git add state_manager.py
git commit -m "$(cat <<'EOF'
refactor(state): use combined totals as pack identifier

将卡包状态的主键从单一分母改为左右分母组合（如 20_81），避免不同卡包分母相同导致的冲突
EOF
)"
```

---

## Task 2: 修改 ActionHandler 状态变量

**Files:**
- Modify: `actions/handler.py:29-34, 114-144`

**Step 1: 将 current_pack_total 改为 current_pack_id**

```python
        # 状态变量
        self.current_pack_name = None      # 当前卡包名称（用于显示）
        self.current_pack_id = None        # 当前卡包 ID（左分母_右分母）
        self.tried_expansion_series = set()
        self.all_packs_checked = False
        self.needs_state_init = state.needs_initialization()
```

**Step 2: 修改 action_handle_deck_list 方法**

```python
    def action_handle_deck_list(self, screenshot, match_info: Dict):
        def set_all_packs_checked(val: bool):
            self.all_packs_checked = val
        def set_current_pack_name(name: str):
            self.current_pack_name = name
        self._deck.handle_deck_list(
            screenshot, match_info,
            self.needs_state_init,
            self.all_packs_checked,
            self.current_pack_id,
            self.current_pack_name,
            set_all_packs_checked,
            set_current_pack_name
        )
```

**Step 3: 修改 action_handle_expansion_select 方法**

```python
    def action_handle_expansion_select(self, screenshot, match_info: Dict):
        def set_tried_expansion_series(val: set):
            self.tried_expansion_series = val
        def set_all_packs_checked(val: bool):
            self.all_packs_checked = val
        def set_current_pack_id(val: str):
            self.current_pack_id = val
        self._expansion.handle_expansion_select(
            screenshot, match_info,
            self.tried_expansion_series,
            set_tried_expansion_series,
            set_all_packs_checked,
            set_current_pack_id
        )
```

**Step 4: 运行测试验证修改**

Run: `python -c "from actions.handler import ActionHandler; print('ActionHandler import OK')"`
Expected: `ActionHandler import OK`

**Step 5: Commit**

```bash
git add actions/handler.py
git commit -m "$(cat <<'EOF'
refactor(handler): use pack_id (combined totals) as identifier

使用 current_pack_id（左分母_右分母）替代 current_pack_total
EOF
)"
```

---

## Task 3: 修改 ExpansionActions 生成组合 ID

**Files:**
- Modify: `actions/expansion.py:20-30, 150-195, 224-254`

**Step 1: 修改方法签名**

```python
    def handle_expansion_select(
        self,
        screenshot,
        match_info: Dict,
        tried_expansion_series: Set[str],
        set_tried_expansion_series: Callable[[Set[str]], None],
        set_all_packs_checked: Callable[[bool], None],
        set_current_pack_id: Callable[[str], None]  # 改名
    ):
```

**Step 2: 修改分组逻辑说明**

当前 `_group_progress_by_row` 已经正确地将同一行的两个进度分为 left 和 right：
- left: 牌组完成进度（如 `5/20`）
- right: 卡片收集进度（如 `30/81`）

需要利用这两个值生成组合 ID。

**Step 3: 修改筛选逻辑生成组合 ID**

```python
            # 找到未完成的卡包
            incomplete_items = []
            if config.DEBUG:
                print(f"  [DEBUG] row_data 共 {len(row_data)} 行")

            for row in row_data:
                right = row['right']  # 卡片收集进度
                left = row['left']    # 牌组完成进度
                if not right:
                    continue

                # 如果左侧为空或者是 CLEAR，跳过该卡包（已完成所有牌组）
                if not left:
                    if config.DEBUG:
                        print(f"  [DEBUG] 跳过: 左侧进度为空 (right={right['progress_key']})")
                    continue

                # 生成组合 ID: 左分母_右分母
                left_total = str(left['total'])
                right_total = str(right['total'])
                pack_id = f"{left_total}_{right_total}"

                if config.DEBUG:
                    left_str = f"{left['current_val']}/{left['total']}"
                    print(f"  [DEBUG] 检查卡包: left={left_str}, right={right['current_val']}/{right['total']}, pack_id={pack_id}")

                if current_level and self.state.is_pack_complete(current_level, pack_id):
                    if config.DEBUG:
                        print(f"  [DEBUG]   -> 已标记为完成，跳过")
                    continue

                # 使用左侧进度判断是否未完成
                if left['current_val'] < left['total']:
                    incomplete_items.append({
                        'text': f"{left['progress_key']} | {right['progress_key']}",
                        'box': left['box'],
                        'remaining': left['total'] - left['current_val'],
                        'pack_id': pack_id,
                        'progress_key': f"{left['progress_key']} | {right['progress_key']}"
                    })
                    if config.DEBUG:
                        print(f"  [DEBUG]   -> 未完成，加入候选")

            if incomplete_items:
                incomplete_items.sort(key=lambda x: x['remaining'], reverse=True)
                item = incomplete_items[0]
                print(f"  -> 选择未完成卡包: {item['progress_key']} (pack_id={item['pack_id']}, 剩余 {item['remaining']})")
                set_current_pack_id(item['pack_id'])
                set_tried_expansion_series(set())
                set_all_packs_checked(False)
                self.adb.tap_center(item['box'])
                return
```

**注意**: 当前代码在收集进度项时已经有 `if 'CLEAR' in text.upper(): continue` 的逻辑，会跳过 CLEAR 文本。这意味着如果左侧显示的是 CLEAR，它不会被收集到 progress_items 中，导致 `row['left']` 为 None。上面的代码通过检查 `if not left` 来跳过这种情况。

**Step 4: 运行测试验证修改**

Run: `python -c "from actions.expansion import ExpansionActions; print('ExpansionActions import OK')"`
Expected: `ExpansionActions import OK`

**Step 5: Commit**

```bash
git add actions/expansion.py
git commit -m "$(cat <<'EOF'
fix(expansion): use combined totals as pack identifier

使用左右分母组合（如 20_81）作为卡包唯一标识符，修复多个卡包分母相同时的混淆问题
EOF
)"
```

---

## Task 4: 修改 DeckActions 使用组合 ID

**Files:**
- Modify: `actions/deck.py:20-30, 70-145`

**Step 1: 修改方法签名**

```python
    def handle_deck_list(
        self,
        screenshot,
        match_info: Dict,
        needs_state_init: bool,
        all_packs_checked: bool,
        current_pack_id: Optional[str],     # 组合 ID
        current_pack_name: Optional[str],   # 卡包名称（用于显示）
        set_all_packs_checked: Callable[[bool], None],
        set_current_pack_name: Callable[[str], None]
    ):
```

**Step 2: 修改 "没有可用对战" 处理逻辑**

```python
        # 检查是否没有可用对战
        no_battles_variants = config.TEXT_VARIANTS.get("no_battles_available", [])
        for item in ocr_results:
            text = item['text'].strip().lower()
            for variant in no_battles_variants:
                if variant.lower() in text:
                    print("  -> 当前难度没有可用对战，标记卡包完成并返回")
                    if current_level and current_pack_id:
                        pack_name = self._extract_pack_name(ocr_results) or ""
                        self.state.set_pack_complete(current_level, current_pack_id, pack_name, True)
                    # 点击扩充组查看更多卡包
                    expansion_item = find_text_by_variants(ocr_results, "expansion_button")
                    if expansion_item:
                        self.adb.tap_center(expansion_item['box'])
                        return
                    go_back(self.adb, self.recognizer, screenshot)
                    return
```

**Step 3: 修改卡包完成检查逻辑**

```python
        # 检查当前卡包是否已标记为完成
        if current_level and current_pack_id:
            if self.state.is_pack_complete(current_level, current_pack_id):
                print(f"  -> {current_pack_name or current_pack_id} 在 {current_level} 已完成，进入扩充组选择其他卡包")
                expansion_item = find_text_by_variants(ocr_results, "expansion_button")
                if expansion_item:
                    self.adb.tap_center(expansion_item['box'])
                    return
                go_back(self.adb, self.recognizer, screenshot)
                return
```

**Step 4: 修改滑动完成后的标记逻辑**

```python
        # 没有沙漏，标记当前卡包为完成
        if current_level and current_pack_id:
            pack_name_final = current_pack_name or ""
            self.state.set_pack_complete(current_level, current_pack_id, pack_name_final, True)
```

**Step 5: 运行测试验证修改**

Run: `python -c "from actions.deck import DeckActions; print('DeckActions import OK')"`
Expected: `DeckActions import OK`

**Step 6: Commit**

```bash
git add actions/deck.py
git commit -m "$(cat <<'EOF'
fix(deck): use pack_id for completion tracking

使用组合 ID（左分母_右分母）而非单一分母来跟踪完成状态
EOF
)"
```

---

## Task 5: 添加迁移逻辑处理旧状态文件

**Files:**
- Modify: `state_manager.py:20-42`

**Step 1: 在 _load_state 中添加迁移检测**

```python
    def _load_state(self) -> Dict:
        """加载状态文件"""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)

                    # 检查语言是否一致，不一致则重置
                    saved_lang = state.get("language")
                    if saved_lang and saved_lang != config.LANGUAGE:
                        print(f"语言已变更: {saved_lang} -> {config.LANGUAGE}")
                        print("重置状态文件...")
                        self.state_file.unlink()
                        return self._create_default_state()

                    # 检查是否需要迁移（旧格式使用单一数字作为 key）
                    if self._needs_migration(state):
                        print("检测到旧版本状态格式（单一分母），重置状态文件...")
                        self.state_file.unlink()
                        return self._create_default_state()

                    print(f"已加载状态: {self.state_file}")
                    return state
            except Exception as e:
                print(f"加载状态失败: {e}")

        # 初始化默认状态
        return self._create_default_state()
```

**Step 2: 添加迁移检测方法**

```python
    def _needs_migration(self, state: Dict) -> bool:
        """检测是否需要迁移（旧格式使用单一数字作为卡包 key，新格式使用 左分母_右分母）"""
        levels = state.get("levels", {})
        for level_data in levels.values():
            packs = level_data.get("packs", {})
            for key in packs.keys():
                # 如果 key 是纯数字（旧格式），需要迁移
                # 新格式是 "数字_数字" 的形式
                if key.isdigit():
                    return True
        return False
```

**Step 3: 运行测试验证修改**

Run: `python -c "from state_manager import StateManager; print('Migration check OK')"`
Expected: `Migration check OK`

**Step 4: Commit**

```bash
git add state_manager.py
git commit -m "$(cat <<'EOF'
feat(state): add migration detection for old format

自动检测旧版本状态格式（使用单一数字作为卡包 key）并重置
EOF
)"
```

---

## Task 6: 集成测试

**Files:**
- Test: 运行实际程序验证

**Step 1: 删除旧状态文件**

```bash
rm -f /tmp/ptcgp_auto_5575/state.json
```

**Step 2: 运行程序验证导入**

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto && python -c "
from actions.handler import ActionHandler
from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager
print('All imports OK')
"
```

**Step 3: 验证新状态文件格式**

运行程序后检查新生成的状态文件，确认卡包使用组合 ID 作为 key：

```json
"packs": {
  "20_81": {"name": "基因起源", "done": true},
  "25_81": {"name": "神奧的光芒", "done": false},
  ...
}
```

**Step 4: Commit 最终版本**

```bash
git add -A
git commit -m "$(cat <<'EOF'
fix: use combined totals as unique pack identifier

修复卡包状态使用单一分母作为唯一标识符导致的 bug：
- 不同卡包可能有相同的总卡数分母，导致状态混淆
- 改用左右分母组合（牌组数_卡数）作为主键，如 20_81
- 添加旧格式状态文件自动迁移检测
EOF
)"
```

---

## 注意事项

1. **组合 ID 格式**: `{左分母}_{右分母}`，如 `20_81`
   - 左分母 = 总牌组数（牌组完成进度的分母）
   - 右分母 = 总卡数（卡片收集进度的分母）
2. **向后兼容**: 添加了迁移检测，旧格式状态文件（纯数字 key）会被自动重置
3. **调试模式**: 开启 `config.DEBUG = True` 可以查看详细的组合 ID 生成日志
4. **状态文件位置**: `/tmp/ptcgp_auto_{port}/state.json`
