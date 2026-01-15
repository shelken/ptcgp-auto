# 新手教程解锁单人对战 设计文档

## 背景

新手账号的单人对战会被锁住（显示锁图标），必须完成玩法教程（00-06）才能解锁。

## 需求

1. 在对战菜单页面检测锁图标
2. 如果被锁住，点击"玩法"进入教程列表
3. 遍历完成 00-06 的所有教程
4. 教程完成后返回对战菜单，此时单人对战应已解锁

## 模板资源

- `icon_lock.png` - 锁图标，用于检测单人对战是否被锁住
- `wanfa_shalou.png` - 沙漏图标，用于检测教程是否未完成（有沙漏=未完成）
- `hand_pointer.png` - 手指图标，用于教学界面（后续添加）

## 页面规则

在 `locales/zh_Hant.py` 的 `PAGES` 中新增：

```python
# 对战菜单（锁定状态）- 优先级高于普通 battle_menu
"battle_menu_locked": {
    "identifiers": ["與他人對戰"],
    "templates": ["icon_lock"],
    "match_all": True,  # 必须同时满足文字和模板
    "action": "handle_tutorial_unlock",
    "priority": 54,  # 比 battle_menu(55) 优先级高
},

# 玩法列表页面
"tutorial_list": {
    "identifiers": ["玩法"],
    "templates": ["wanfa_shalou"],
    "action": "handle_tutorial_list",
    "priority": 40,
    "exclude_identifiers": ["與他人對戰"],  # 排除对战菜单
},

# 教学界面（后续完善）
"tutorial_teaching": {
    "templates": ["hand_pointer"],
    "action": "handle_tutorial_step",
    "priority": 35,
},
```

## 模块结构

新增 `actions/tutorial.py`：

```python
"""教程解锁动作 - 处理新手账号单人对战解锁"""

class TutorialActions:
    def __init__(self, adb, recognizer):
        self.adb = adb
        self.recognizer = recognizer

    def handle_tutorial_unlock(self, screenshot, match_info):
        """对战菜单检测到锁定 -> 点击玩法按钮"""
        pass

    def handle_tutorial_list(self, screenshot, match_info):
        """玩法列表 -> 找到有沙漏的任务并点击"""
        pass

    def handle_tutorial_step(self, screenshot, match_info):
        """教学步骤 -> 跟随手指点击（后续完善）"""
        pass
```

在 `handler.py` 中添加委托方法。

## 核心逻辑

### handle_tutorial_unlock

从 OCR 结果中找到"玩法"并点击。

### handle_tutorial_list

1. 检测 `wanfa_shalou` 模板
2. 如果有沙漏，点击该位置进入教程
3. 如果没有沙漏：
   - 检查 OCR 是否能看到 "06"
   - 如果能看到 06 且没有沙漏 -> 00-06 全部完成，按返回键
   - 如果看不到 06 -> 向上滑动继续查找

### handle_tutorial_step

后续完善。大部分情况跟随手指图标点击，部分情况需要拖动。

## 待办

- [ ] 实现基础框架
- [ ] 截取 `hand_pointer.png` 模板
- [ ] 实现教学界面交互逻辑
- [ ] 处理需要拖动的教学步骤（可能需要 ADB drag 操作）
