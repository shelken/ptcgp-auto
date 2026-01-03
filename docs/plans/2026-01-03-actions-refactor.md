# Actions.py 重构实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 819 行的 `actions.py` 拆分为模块化架构，提取公共逻辑，提升可维护性

**Architecture:**
- 按功能域拆分为独立模块：基础动作、对战、等级选择、牌组列表、扩充组选择
- 提取通用工具：滚动查找器、OCR 文本匹配器、底部检测器
- 保持 `ActionHandler` 作为门面类，委托给各子模块

**Tech Stack:** Python 3.10+, 现有依赖（adbutils, PIL）

---

## 模块拆分设计

```
actions/
├── __init__.py          # 导出 ActionHandler
├── handler.py           # ActionHandler 门面类
├── base.py              # 基础动作 (click_identifier, click_continue, wait 等)
├── battle.py            # 对战相关 (start_battle)
├── level.py             # 等级选择 (select_level, _find_and_click_level)
├── deck.py              # 牌组列表 (handle_deck_list)
├── expansion.py         # 扩充组选择 (handle_expansion_select)
└── utils/
    ├── __init__.py
    ├── scroll.py        # 滚动查找器 (scroll_and_find, detect_bottom)
    ├── ocr_helpers.py   # OCR 工具 (find_text_by_variants, extract_progress)
    └── navigation.py    # 导航工具 (go_back, close_popup)
```

---

## Task 1: 创建 actions 包结构

**Files:**
- Create: `actions/__init__.py`
- Create: `actions/handler.py`

**Step 1: 创建 actions 目录和 __init__.py**

```bash
mkdir -p actions
```

```python
# actions/__init__.py
"""动作处理器模块"""
from .handler import ActionHandler

__all__ = ['ActionHandler']
```

**Step 2: 创建空的 handler.py 骨架**

```python
# actions/handler.py
"""动作处理器 - 门面类"""

from typing import Dict

from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager


class ActionHandler:
    """动作处理器门面类，委托给各子模块"""

    def __init__(
        self,
        adb: AdbController,
        recognizer: Recognizer,
        state: StateManager
    ):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        # 状态变量
        self.current_pack_name = None
        self.current_pack_total = None
        self.tried_expansion_series = set()
        self.all_packs_checked = False
        self.needs_state_init = state.needs_initialization()

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作"""
        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            print(f"  -> 未知动作: {action}")
```

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): create actions package skeleton

初始化 actions 模块包结构，创建 ActionHandler 门面类骨架"
```

---

## Task 2: 提取滚动工具类

**Files:**
- Create: `actions/utils/__init__.py`
- Create: `actions/utils/scroll.py`
- Test: 手动验证

**Step 1: 创建 utils 目录结构**

```bash
mkdir -p actions/utils
```

```python
# actions/utils/__init__.py
"""动作工具模块"""
from .scroll import ScrollHelper

__all__ = ['ScrollHelper']
```

**Step 2: 实现 ScrollHelper 类**

分析原代码中的滚动模式：
- `_find_and_click_level`: 滑动查找等级
- `action_handle_deck_list`: 滑动查找沙漏
- `action_handle_expansion_select`: 滑动查找卡包
- `_sync_level_complete_status`: 滑动同步状态

共同模式：
1. 循环滑动
2. 每次滑动后重新截图和 OCR
3. 使用文本集合检测是否到底
4. 最多滑动 N 次

```python
# actions/utils/scroll.py
"""滚动查找工具"""

import time
from typing import Callable, TypeVar, Optional, Set, List, Dict

T = TypeVar('T')


class ScrollHelper:
    """滚动查找辅助类"""

    def __init__(self, adb, recognizer, max_attempts: int = 10, distance: int = 400, delay: float = 0.8):
        """
        Args:
            adb: AdbController 实例
            recognizer: Recognizer 实例
            max_attempts: 最大滑动次数
            distance: 每次滑动距离
            delay: 滑动后等待时间
        """
        self.adb = adb
        self.recognizer = recognizer
        self.max_attempts = max_attempts
        self.distance = distance
        self.delay = delay

    def scroll_and_find(
        self,
        finder: Callable[[any, List[Dict]], Optional[T]],
        screenshot,
        ocr_results: List[Dict],
        on_scroll: Callable[[int], None] = None
    ) -> Optional[T]:
        """滑动查找，直到找到目标或到底

        Args:
            finder: 查找函数，接收 (screenshot, ocr_results)，返回找到的结果或 None
            screenshot: 初始截图
            ocr_results: 初始 OCR 结果
            on_scroll: 滑动时的回调，接收滑动次数

        Returns:
            找到的结果，或 None
        """
        last_texts: Set[str] = set()

        for attempt in range(self.max_attempts):
            if attempt > 0:
                if on_scroll:
                    on_scroll(attempt)
                self.adb.swipe_up(distance=self.distance)
                time.sleep(self.delay)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)
                else:
                    continue

            # 尝试查找
            result = finder(screenshot, ocr_results)
            if result is not None:
                return result

            # 检测是否到底
            current_texts = {item['text'].strip() for item in ocr_results}
            if attempt > 0 and current_texts == last_texts:
                break
            last_texts = current_texts

        return None

    def is_at_bottom(self, current_texts: Set[str], last_texts: Set[str]) -> bool:
        """检测是否已滑动到底部"""
        return bool(last_texts) and current_texts == last_texts
```

**Step 3: 验证导入正常**

Run: `python -c "from actions.utils import ScrollHelper; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/utils/
git commit -m "feat(actions): add ScrollHelper utility

提取通用滚动查找逻辑，支持自定义查找函数和底部检测"
```

---

## Task 3: 提取 OCR 辅助工具

**Files:**
- Create: `actions/utils/ocr_helpers.py`
- Modify: `actions/utils/__init__.py`

**Step 1: 实现 OCR 辅助函数**

分析原代码中的 OCR 模式：
- 使用 `TEXT_VARIANTS` 查找文本
- 提取进度数字 `(\d+)\s*/\s*(\d+)`
- 按 Y 坐标分组（同一行判断）

```python
# actions/utils/ocr_helpers.py
"""OCR 辅助工具"""

import re
from typing import List, Dict, Optional, Tuple

import config


def find_text_by_variants(ocr_results: List[Dict], variant_key: str) -> Optional[Dict]:
    """根据 TEXT_VARIANTS 配置查找文本

    Args:
        ocr_results: OCR 结果列表
        variant_key: TEXT_VARIANTS 中的 key

    Returns:
        找到的 OCR item，包含 text 和 box
    """
    variants = config.TEXT_VARIANTS.get(variant_key, [])
    for item in ocr_results:
        text = item['text'].strip()
        for variant in variants:
            if variant in text:
                return item
    return None


def find_all_by_variants(ocr_results: List[Dict], variant_key: str) -> List[Dict]:
    """根据 TEXT_VARIANTS 配置查找所有匹配的文本"""
    variants = config.TEXT_VARIANTS.get(variant_key, [])
    results = []
    for item in ocr_results:
        text = item['text'].strip()
        for variant in variants:
            if variant in text:
                results.append(item)
                break
    return results


def extract_progress(text: str) -> Optional[Tuple[int, int]]:
    """从文本中提取进度数字

    Args:
        text: 包含进度的文本，如 "21/30"

    Returns:
        (current, total) 元组，或 None
    """
    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None


def find_items_on_same_row(
    ocr_results: List[Dict],
    reference_y: int,
    tolerance: int = 150
) -> List[Dict]:
    """查找与参考 Y 坐标在同一行的所有项目

    Args:
        ocr_results: OCR 结果列表
        reference_y: 参考 Y 坐标
        tolerance: Y 坐标容差

    Returns:
        同一行的项目列表
    """
    results = []
    for item in ocr_results:
        item_y = (item['box'][1] + item['box'][3]) // 2
        if abs(item_y - reference_y) < tolerance:
            results.append(item)
    return results


def group_by_row(ocr_results: List[Dict], tolerance: int = 100) -> List[List[Dict]]:
    """按 Y 坐标将 OCR 结果分组为行

    Args:
        ocr_results: OCR 结果列表
        tolerance: 同一行的 Y 坐标容差

    Returns:
        分组后的行列表，每行按 X 坐标排序
    """
    if not ocr_results:
        return []

    # 按 Y 坐标排序
    items = sorted(ocr_results, key=lambda x: (x['box'][1] + x['box'][3]) // 2)

    rows = []
    current_row = []
    row_start_y = None

    for item in items:
        item_y = (item['box'][1] + item['box'][3]) // 2
        if row_start_y is None or abs(item_y - row_start_y) < tolerance:
            current_row.append(item)
            if row_start_y is None:
                row_start_y = item_y
        else:
            if current_row:
                # 按 X 坐标排序
                current_row.sort(key=lambda x: (x['box'][0] + x['box'][2]) // 2)
                rows.append(current_row)
            current_row = [item]
            row_start_y = item_y

    if current_row:
        current_row.sort(key=lambda x: (x['box'][0] + x['box'][2]) // 2)
        rows.append(current_row)

    return rows
```

**Step 2: 更新 utils/__init__.py**

```python
# actions/utils/__init__.py
"""动作工具模块"""
from .scroll import ScrollHelper
from .ocr_helpers import (
    find_text_by_variants,
    find_all_by_variants,
    extract_progress,
    find_items_on_same_row,
    group_by_row,
)

__all__ = [
    'ScrollHelper',
    'find_text_by_variants',
    'find_all_by_variants',
    'extract_progress',
    'find_items_on_same_row',
    'group_by_row',
]
```

**Step 3: 验证导入正常**

Run: `python -c "from actions.utils import find_text_by_variants, extract_progress; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/utils/
git commit -m "feat(actions): add OCR helper utilities

提取 OCR 文本查找、进度提取、行分组等通用逻辑"
```

---

## Task 4: 提取导航工具

**Files:**
- Create: `actions/utils/navigation.py`
- Modify: `actions/utils/__init__.py`

**Step 1: 实现导航辅助函数**

```python
# actions/utils/navigation.py
"""导航辅助工具"""

from typing import List, Dict


def go_back(adb, recognizer, screenshot):
    """返回上一页

    优先使用返回按钮模板，否则使用系统返回键
    """
    if screenshot:
        back_btn = recognizer.find_template(screenshot, "btn_back", threshold=0.6)
        if back_btn:
            adb.tap_center(back_btn)
            return
    adb.back()


def close_popup(adb, recognizer, screenshot, ocr_results: List[Dict]):
    """关闭弹窗

    优先查找 X 按钮，否则使用返回键
    """
    # 尝试 OCR 查找 X 按钮
    for item in ocr_results:
        text = item['text'].strip()
        if text in ['×', 'X', 'x', '✕']:
            adb.tap_center(item['box'])
            return

    # 尝试模板匹配
    close_btn = recognizer.find_template(screenshot, "btn_close", threshold=0.6)
    if close_btn:
        adb.tap_center(close_btn)
        return

    # 使用返回键
    go_back(adb, recognizer, screenshot)
```

**Step 2: 更新 utils/__init__.py**

```python
# actions/utils/__init__.py
"""动作工具模块"""
from .scroll import ScrollHelper
from .ocr_helpers import (
    find_text_by_variants,
    find_all_by_variants,
    extract_progress,
    find_items_on_same_row,
    group_by_row,
)
from .navigation import go_back, close_popup

__all__ = [
    'ScrollHelper',
    'find_text_by_variants',
    'find_all_by_variants',
    'extract_progress',
    'find_items_on_same_row',
    'group_by_row',
    'go_back',
    'close_popup',
]
```

**Step 3: 验证导入正常**

Run: `python -c "from actions.utils import go_back, close_popup; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/utils/
git commit -m "feat(actions): add navigation utilities

提取返回和关闭弹窗的通用导航逻辑"
```

---

## Task 5: 创建基础动作模块

**Files:**
- Create: `actions/base.py`
- Modify: `actions/handler.py`

**Step 1: 实现基础动作类**

```python
# actions/base.py
"""基础动作模块"""

import time
from typing import Dict

import config
from .utils import find_text_by_variants


class BaseActions:
    """基础动作处理"""

    def __init__(self, adb, recognizer):
        self.adb = adb
        self.recognizer = recognizer

    def click_identifier(self, screenshot, match_info: Dict):
        """点击识别到的文字位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击: {match_info.get('identifier', 'unknown')}")
            self.adb.tap_center(box)

    def click_continue(self, screenshot, match_info: Dict):
        """点击屏幕中央继续"""
        print("  -> 点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_cancel(self, screenshot, match_info: Dict):
        """点击取消按钮"""
        ocr_results = match_info.get("ocr_results", [])
        cancel_item = find_text_by_variants(ocr_results, "cancel")
        if cancel_item:
            print("  -> 点击取消")
            self.adb.tap_center(cancel_item['box'])
            return
        # 如果没找到取消，尝试点击屏幕继续
        print("  -> 未找到取消按钮，点击屏幕继续")
        self.adb.tap(config.SCREEN_WIDTH // 2, config.SCREEN_HEIGHT // 2)

    def click_template(self, screenshot, match_info: Dict):
        """点击模板位置"""
        box = match_info.get("box")
        if box:
            print(f"  -> 点击模板: {match_info.get('template', 'unknown')}")
            self.adb.tap_center(box)

    def wait(self, screenshot, match_info: Dict):
        """等待（对战中）"""
        print("  -> 对战中，等待...")
        time.sleep(config.WAIT_BATTLE_CHECK_INTERVAL)
```

**Step 2: 更新 handler.py 使用 BaseActions**

```python
# actions/handler.py
"""动作处理器 - 门面类"""

from typing import Dict

from adb_controller import AdbController
from recognizer import Recognizer
from state_manager import StateManager
from .base import BaseActions


class ActionHandler:
    """动作处理器门面类，委托给各子模块"""

    def __init__(
        self,
        adb: AdbController,
        recognizer: Recognizer,
        state: StateManager
    ):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        # 状态变量
        self.current_pack_name = None
        self.current_pack_total = None
        self.tried_expansion_series = set()
        self.all_packs_checked = False
        self.needs_state_init = state.needs_initialization()
        # 子模块
        self._base = BaseActions(adb, recognizer)

    def execute(self, action: str, screenshot, match_info: Dict):
        """执行动作"""
        handler = getattr(self, f"action_{action}", None)
        if handler:
            handler(screenshot, match_info)
        else:
            print(f"  -> 未知动作: {action}")

    # ==================== 基础动作（委托） ====================

    def action_click_identifier(self, screenshot, match_info: Dict):
        self._base.click_identifier(screenshot, match_info)

    def action_click_continue(self, screenshot, match_info: Dict):
        self._base.click_continue(screenshot, match_info)

    def action_click_cancel(self, screenshot, match_info: Dict):
        self._base.click_cancel(screenshot, match_info)

    def action_click_template(self, screenshot, match_info: Dict):
        self._base.click_template(screenshot, match_info)

    def action_wait(self, screenshot, match_info: Dict):
        self._base.wait(screenshot, match_info)
```

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add BaseActions module

提取基础动作到独立模块，handler 作为门面委托调用"
```

---

## Task 6: 创建对战动作模块

**Files:**
- Create: `actions/battle.py`
- Modify: `actions/handler.py`

**Step 1: 实现对战动作类**

```python
# actions/battle.py
"""对战相关动作模块"""

import time
from typing import Dict, Callable

import config
from .utils import find_text_by_variants, go_back


class BattleActions:
    """对战相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        """
        Args:
            should_switch_checker: 检查是否应该切换等级的回调函数
        """
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker

    def start_battle(self, screenshot, match_info: Dict, needs_state_init: bool):
        """开始对战 - 先开启自动，再点击对战按钮

        Returns:
            bool: 是否需要返回上级
        """
        ocr_results = match_info.get("ocr_results", [])

        # 如果需要初始化状态且当前等级未设置，返回上级页面
        if needs_state_init and not self.state.get_current_level():
            print("  -> 需要初始化状态，返回上级页面")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            go_back(self.adb, self.recognizer, screenshot)
            return True

        # 检查自动模式状态
        auto_box = None
        has_off = False
        auto_variants = config.TEXT_VARIANTS.get("auto", [])

        for item in ocr_results:
            text = item['text'].strip()
            text_upper = text.upper()
            for variant in auto_variants:
                if variant in text or variant.upper() in text_upper:
                    auto_box = item['box']
                    break
            if 'OFF' in text_upper:
                has_off = True

        # 如果自动模式是 OFF，先点击开启
        if auto_box and has_off:
            print("  -> 开启自动模式")
            self.adb.tap_center(auto_box)
            time.sleep(0.5)

        # 点击对战按钮
        battle_box = match_info.get("box")
        if battle_box:
            print("  -> 点击对战")
            self.adb.tap_center(battle_box)

        return False
```

**Step 2: 更新 handler.py**

在 `ActionHandler.__init__` 中添加：

```python
from .battle import BattleActions

# 在 __init__ 中
self._battle = BattleActions(
    adb, recognizer, state,
    self._should_switch_to_higher_priority_level
)
```

添加方法：

```python
def action_start_battle(self, screenshot, match_info: Dict):
    self._battle.start_battle(screenshot, match_info, self.needs_state_init)

def _should_switch_to_higher_priority_level(self) -> bool:
    """检查是否应该切换到更高优先级的等级"""
    current_level = self.state.get_current_level()
    if not current_level:
        return False

    for level in config.BATTLE_LEVELS:
        if not self.state.is_level_complete(level):
            if level != current_level:
                print(f"  [优先级检查] 当前 {current_level}，但 {level} 未完成且优先级更高")
                return True
            else:
                return False
    return False
```

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add BattleActions module

提取对战相关逻辑到独立模块"
```

---

## Task 7: 创建等级选择模块

**Files:**
- Create: `actions/level.py`
- Modify: `actions/handler.py`

**Step 1: 实现等级选择类**

```python
# actions/level.py
"""等级选择动作模块"""

import re
import sys
import time
from typing import Dict, List, Callable

import config
from .utils import ScrollHelper, go_back


class LevelActions:
    """等级选择相关动作处理"""

    def __init__(self, adb, recognizer, state, should_switch_checker: Callable[[], bool]):
        self.adb = adb
        self.recognizer = recognizer
        self.state = state
        self._should_switch_to_higher_priority_level = should_switch_checker
        self._scroll_helper = ScrollHelper(adb, recognizer, max_attempts=10, distance=400)

    def select_level(self, screenshot, match_info: Dict, needs_state_init: bool, on_init_complete: Callable):
        """选择未完成的等级"""
        ocr_results = match_info.get("ocr_results", [])

        # 如果需要初始化，先同步所有等级状态
        if needs_state_init:
            self._sync_level_complete_status(ocr_results, screenshot)
            on_init_complete()

        # 检查是否应该切换到更高优先级的等级
        if self._should_switch_to_higher_priority_level():
            print("  -> 返回上级页面以选择更高优先级等级")
            self.state.set_current_level(None)
            go_back(self.adb, self.recognizer, screenshot)
            return

        # 按优先级逐个查找等级
        for level in config.BATTLE_LEVELS:
            if self.state.is_level_complete(level):
                continue

            found = self._find_and_click_level(level, ocr_results, screenshot)
            if found:
                return

        # 所有等级都已完成
        print("  -> 所有等级都已完成！")
        print("=" * 50)
        print("恭喜！所有分级对战任务已完成！")
        print("=" * 50)
        sys.exit(0)

    def _find_and_click_level(self, level: str, ocr_results: List[Dict], screenshot) -> bool:
        """查找并点击指定等级"""
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"  -> 滑动查找 {level} (第{attempt}次)")
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)
                else:
                    continue

            current_texts = set(item['text'].strip() for item in ocr_results)

            # 在当前 OCR 结果中查找该等级
            for item in ocr_results:
                text = item['text'].strip()
                if level in text:
                    level_y = (item['box'][1] + item['box'][3]) // 2

                    for other_item in ocr_results:
                        other_y = (other_item['box'][1] + other_item['box'][3]) // 2
                        if abs(other_y - level_y) < 150:
                            other_text = other_item['text'].strip()

                            if 'COMPLETE' in other_text.upper():
                                self.state.set_level_complete(level, True)
                                return False

                            if re.search(r'\d+\s*/\s*\d+', other_text):
                                print(f"  -> 选择等级: {level} ({other_text})")
                                self.state.set_current_level(level)
                                self.adb.tap_center(item['box'])
                                return True

            if attempt > 0 and current_texts == last_texts:
                print(f"  -> 已滑动到底部，未找到 {level}")
                break

            last_texts = current_texts

        return False

    def _sync_level_complete_status(self, ocr_results: List[Dict], screenshot):
        """同步所有等级的完成状态"""
        print("  [初始化] 正在同步等级完成状态...")

        synced_levels = set()
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            current_texts = set(item['text'].strip() for item in ocr_results)

            for item in ocr_results:
                text = item['text'].strip()
                for level in config.BATTLE_LEVELS:
                    if level in text and level not in synced_levels:
                        level_y = (item['box'][1] + item['box'][3]) // 2
                        is_complete = False
                        for other in ocr_results:
                            other_y = (other['box'][1] + other['box'][3]) // 2
                            if abs(other_y - level_y) < 150:
                                if 'COMPLETE' in other['text'].upper():
                                    is_complete = True
                                    break
                        if is_complete:
                            self.state.set_level_complete(level, True)
                            print(f"  [初始化] {level} = COMPLETE")
                        else:
                            print(f"  [初始化] {level} = 进行中")
                        synced_levels.add(level)

            if attempt > 0 and current_texts == last_texts:
                print("  [初始化] 已滑动到底部")
                break

            last_texts = current_texts

        self.adb.swipe_down(distance=800)
        time.sleep(0.5)

        print(f"  [初始化] 同步完成，共 {len(synced_levels)} 个等级")
```

**Step 2: 更新 handler.py**

添加导入和初始化，添加委托方法。

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add LevelActions module

提取等级选择逻辑到独立模块，包含状态同步"
```

---

## Task 8: 创建牌组列表模块

**Files:**
- Create: `actions/deck.py`
- Modify: `actions/handler.py`

**Step 1: 实现牌组列表类**

提取 `action_handle_deck_list` 和相关辅助方法到 `DeckActions` 类。

**Step 2: 更新 handler.py**

添加委托方法。

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add DeckActions module

提取牌组列表处理逻辑到独立模块"
```

---

## Task 9: 创建扩充组选择模块

**Files:**
- Create: `actions/expansion.py`
- Modify: `actions/handler.py`

**Step 1: 实现扩充组选择类**

提取 `action_handle_expansion_select` 到 `ExpansionActions` 类。
这是最复杂的动作，需要保持状态变量的管理。

**Step 2: 更新 handler.py**

添加委托方法，确保状态变量正确传递。

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add ExpansionActions module

提取扩充组选择逻辑到独立模块"
```

---

## Task 10: 创建主页动作模块

**Files:**
- Create: `actions/home.py`
- Modify: `actions/handler.py`

**Step 1: 实现主页动作类**

提取 `action_find_incomplete` 和 `action_click_solo_battle`。

```python
# actions/home.py
"""主页相关动作模块"""

import re
from typing import Dict

from .utils import find_text_by_variants


class HomeActions:
    """主页相关动作处理"""

    def __init__(self, adb):
        self.adb = adb

    def find_incomplete(self, screenshot, match_info: Dict):
        """在单人对战主页寻找未完成任务"""
        ocr_results = match_info.get("ocr_results", [])

        # 查找分级对战入口
        ranked_item = find_text_by_variants(ocr_results, "ranked_battle")
        if ranked_item:
            print("  -> 进入分级对战")
            self.adb.tap_center(ranked_item['box'])
            return

        # 查找有进度数字的任务
        for item in ocr_results:
            text = item['text'].strip()
            if re.search(r'\d+\s*/\s*\d+', text):
                print(f"  -> 找到未完成任务: {text}")
                self.adb.tap_center(item['box'])
                return

        print("  -> 未找到可操作的任务")

    def click_solo_battle(self, screenshot, match_info: Dict):
        """在主菜单点击单人对战"""
        ocr_results = match_info.get("ocr_results", [])

        solo_item = find_text_by_variants(ocr_results, "solo_battle")
        if solo_item:
            print("  -> 点击单人对战")
            self.adb.tap_center(solo_item['box'])
            return

        print("  -> 未找到单人对战入口")
```

**Step 2: 更新 handler.py**

**Step 3: 验证导入正常**

Run: `python -c "from actions import ActionHandler; print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add actions/
git commit -m "feat(actions): add HomeActions module

提取主页相关逻辑到独立模块"
```

---

## Task 11: 完成 handler.py 集成

**Files:**
- Modify: `actions/handler.py`
- Modify: `actions/__init__.py`

**Step 1: 完成所有模块的集成**

确保 `ActionHandler` 正确初始化所有子模块，并委托所有动作。

**Step 2: 验证完整功能**

Run: `python -c "from actions import ActionHandler; h = type('Mock', (), {'needs_initialization': lambda: False})(); print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add actions/
git commit -m "feat(actions): complete handler integration

完成所有子模块的集成，handler 作为统一入口"
```

---

## Task 12: 更新 main.py 导入

**Files:**
- Modify: `main.py`

**Step 1: 更新导入路径**

```python
# 原来
from actions import ActionHandler

# 新的（保持不变，因为 actions/__init__.py 已导出）
from actions import ActionHandler
```

**Step 2: 运行主程序验证**

Run: `python main.py --help`
Expected: 显示帮助信息，无导入错误

**Step 3: Commit**

```bash
git add main.py
git commit -m "chore: update imports after actions refactor

更新 main.py 使用新的 actions 模块结构"
```

---

## Task 13: 删除旧的 actions.py

**Files:**
- Delete: `actions.py`

**Step 1: 确认新模块功能完整**

运行完整测试流程确保无问题。

**Step 2: 删除旧文件**

```bash
git rm actions.py
```

**Step 3: Commit**

```bash
git commit -m "refactor(actions): remove legacy actions.py

删除旧的单文件实现，完成模块化重构"
```

---

## Task 14: 最终验证和清理

**Step 1: 运行程序验证**

```bash
python main.py --help
python -c "from actions import ActionHandler; print('All modules loaded successfully')"
```

**Step 2: 检查代码质量**

确保没有未使用的导入、重复代码等。

**Step 3: 创建合并提交**

```bash
git log --oneline -10  # 查看提交历史
```

---

## 重构前后对比

### 重构前
```
actions.py (819 行单文件)
└── ActionHandler 类
    ├── 基础动作 (5 个方法)
    ├── 对战相关 (1 个方法)
    ├── 等级选择 (2 个方法)
    ├── 单人对战主页 (2 个方法)
    ├── 牌组列表 (1 个方法)
    ├── 扩充组选择 (1 个方法)
    └── 辅助方法 (6 个方法)
```

### 重构后
```
actions/
├── __init__.py          (~10 行)
├── handler.py           (~100 行) - 门面类
├── base.py              (~60 行)  - 基础动作
├── battle.py            (~70 行)  - 对战
├── level.py             (~120 行) - 等级选择
├── deck.py              (~150 行) - 牌组列表
├── expansion.py         (~200 行) - 扩充组选择
├── home.py              (~50 行)  - 主页
└── utils/
    ├── __init__.py      (~20 行)
    ├── scroll.py        (~60 行)  - 滚动工具
    ├── ocr_helpers.py   (~80 行)  - OCR 工具
    └── navigation.py    (~30 行)  - 导航工具
```

**优势：**
1. 单一职责：每个模块专注一个功能域
2. 可复用：utils 工具可被其他模块使用
3. 可测试：各模块可独立测试
4. 可维护：修改一个功能不影响其他模块
5. 可扩展：新增功能只需添加新模块
