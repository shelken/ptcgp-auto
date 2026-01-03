# Popup Detection in Scroll Loop Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复牌组列表滑动循环中弹窗遮挡导致的误标记完成问题

**Architecture:** 在 `handle_deck_list` 的滑动循环中添加弹窗检测逻辑。如果检测到 "OK" 按钮，先点击关闭弹窗并立即返回（让主循环重新检测页面），避免在弹窗遮挡时继续滑动导致误判

**Tech Stack:** Python 3.10+, Apple Vision OCR

---

## Bug 分析

### 现象

从日志可以看到：
```
-> 第1次滑动查找沙漏
OCR(5): "開放全新對戰！"@(362,514), ... "OK"@(505,1322)
[模板] 未找到 shalou, 最高置信度=0.46 (阈值=0.6)
-> 第2次滑动查找沙漏
...
-> 已滑动到底部，未找到沙漏
[状态] 精英 - 時空激鬥(25_100) 已标记为完成
```

弹窗 "開放全新對戰！" 覆盖在页面上，程序没有检测到弹窗，继续滑动。结果沙漏被遮挡无法检测，滑动到底部后误以为"没有沙漏 = 卡包已完成"。

### 根本原因

`handle_deck_list` 的滑动循环（第 108-132 行）没有检测弹窗。主循环的页面检测机制无法介入，因为滑动循环没有返回控制权。

### 修复方案

在滑动循环的每次迭代中检测是否出现弹窗（OCR 结果中是否有精确匹配的 "OK"）：
- 如果检测到 "OK" 按钮，点击关闭弹窗
- 立即 `return`，让主循环重新检测页面
- 不继续滑动，避免误判

---

## Task 1: 在滑动循环中添加弹窗检测

**Files:**
- Modify: `actions/deck.py:104-132`

**Step 1: 导入 close_popup 函数（如果尚未导入）**

检查导入部分，确保已导入 `close_popup`：

```python
from .utils import go_back, find_text_by_variants, close_popup
```

**Step 2: 在滑动循环内添加弹窗检测逻辑**

在循环的每次迭代中，在查找沙漏之前检测弹窗。修改第 108-132 行的循环：

```python
        # 循环滑动查找沙漏图标
        max_attempts = 10
        last_texts = set()

        for attempt in range(max_attempts):
            if attempt > 0:
                print(f"  -> 第{attempt}次滑动查找沙漏")
                self.adb.swipe_up(distance=400)
                time.sleep(0.8)
                screenshot = self.adb.screenshot()
                if screenshot:
                    ocr_results = self.recognizer.ocr_full_screen(screenshot)

            # 检测是否有弹窗遮挡（精确匹配 "OK"）
            for item in ocr_results:
                if item['text'].strip() == "OK":
                    print("  -> 检测到弹窗，点击 OK 关闭")
                    self.adb.tap_center(item['box'])
                    return  # 返回主循环重新检测页面

            # 查找沙漏图标
            shalou_box = self.recognizer.find_template(screenshot, "shalou", threshold=0.6)
            if shalou_box:
                print("  -> 找到沙漏，点击未完成牌组")
                self.adb.tap_center(shalou_box)
                return

            # 收集当前文字用于底部检测
            current_texts = set(item['text'].strip() for item in ocr_results)

            # 检测是否到底
            if attempt > 0 and current_texts == last_texts:
                print("  -> 已滑动到底部，未找到沙漏")
                break

            last_texts = current_texts
```

**Step 3: 运行测试验证修改**

Run: `python -c "from actions.deck import DeckActions; print('DeckActions import OK')"`
Expected: `DeckActions import OK`

**Step 4: Commit**

```bash
git add actions/deck.py
git commit -m "$(cat <<'EOF'
fix(deck): detect popup during scroll loop

在滑动查找沙漏的循环中检测弹窗，避免弹窗遮挡导致误标记卡包完成
EOF
)"
```

---

## Task 2: 验证修复

**Files:**
- Test: 手动测试或代码审查

**Step 1: 验证导入**

```bash
cd /Users/shelken/Code/MyRepo/ptcgp-auto && python -c "
from actions.deck import DeckActions
from actions.handler import ActionHandler
print('All imports OK')
"
```

**Step 2: 代码审查确认**

确认修改后的逻辑：
1. 在滑动循环的每次迭代中检测 "OK" 按钮
2. 如果检测到，点击关闭并返回主循环
3. 不会继续滑动，避免误判

**Step 3: (可选) 实际设备测试**

如果有设备可用，运行 `python main.py` 验证：
- 当弹窗出现时，程序应该检测到并点击 OK
- 不会错误地标记卡包为完成

---

## 注意事项

1. **精确匹配**: 使用 `item['text'].strip() == "OK"` 精确匹配，避免误匹配包含 "OK" 的其他文本
2. **立即返回**: 点击 OK 后立即 `return`，让主循环重新检测页面状态
3. **不修改标记逻辑**: 只有在正常滑动到底部且没有弹窗干扰时才标记卡包完成
