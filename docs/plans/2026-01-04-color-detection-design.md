# 颜色状态检测设计

## 背景

当前项目只能通过 OCR 文字和模板匹配来识别界面，无法判断按钮的选中/开关状态。例如对战界面的「自动对战」勾选框，开启时是绿色勾，关闭时是灰色空框。

## 目标

实现一个通用的、配置驱动的颜色状态检测功能。

## 设计方案

### 方案选型

**OCR 定位 + 颜色检测**

- 用 OCR 找到按钮文字位置（如「自動對戰」）
- 根据文字位置推算勾选框区域（文字左侧）
- 检测该区域内目标颜色（绿色）的像素占比
- 占比超过阈值则判定为「开启」状态

优点：
- 语言无关（不需要为每种语言准备不同模板）
- 配置驱动，易于扩展
- 使用 HSV 颜色空间，对光照变化更鲁棒

### 配置结构

在 `recognizer.py` 中定义：

```python
# 预定义颜色范围 (HSV)
COLORS = {
    "green": {"lower": (35, 80, 80), "upper": (85, 255, 255)},
    "gray": {"lower": (0, 0, 60), "upper": (180, 30, 200)},
}

# 颜色状态检测配置
COLOR_STATES = {
    "auto_battle": {
        "locator": {
            "type": "text_pattern",   # text_pattern 或 template
            "key": "auto_battle",     # TEXT_PATTERNS 的 key
        },
        "color_region": {
            "position": "left",       # left / right / above / below
            "offset": 0.01,           # 相对于屏幕宽度的比例
            "width": 0.04,            # 区域宽度（屏幕宽度比例）
            "height": 0.025,          # 区域高度（屏幕高度比例）
        },
        "color": "green",             # COLORS 中的预定义颜色名
        "threshold": 0.1,             # 颜色占比阈值
    },
}
```

### API 设计

在 `Recognizer` 类中新增方法：

```python
def check_color_ratio(
    self,
    screenshot: Image.Image,
    region: Tuple[int, int, int, int],
    hsv_lower: Tuple[int, int, int],
    hsv_upper: Tuple[int, int, int],
    threshold: float = 0.1
) -> bool:
    """检测区域内指定颜色占比是否超过阈值"""

def check_green(
    self,
    screenshot: Image.Image,
    region: Tuple[int, int, int, int],
    threshold: float = 0.1
) -> bool:
    """便捷方法：检测区域内是否有足够的绿色"""

def check_state(
    self,
    screenshot: Image.Image,
    state_name: str
) -> bool:
    """根据 COLOR_STATES 配置检测状态"""
```

### 实现细节

1. **颜色空间转换**：BGR → HSV
2. **掩码创建**：`cv2.inRange(hsv, lower, upper)`
3. **占比计算**：`np.count_nonzero(mask) / mask.size`
4. **区域计算**：使用屏幕比例而非像素，适配不同分辨率

```python
def check_color_ratio(self, screenshot, region, hsv_lower, hsv_upper, threshold=0.1):
    x1, y1, x2, y2 = region
    img = self.pil_to_cv2(screenshot)
    roi = img[y1:y2, x1:x2]
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lower), np.array(hsv_upper))
    ratio = np.count_nonzero(mask) / mask.size
    return ratio >= threshold
```

### Locale 变更

在各语言文件中添加 TEXT_PATTERNS：

```python
# locales/zh_Hant.py
TEXT_PATTERNS = {
    # ... 现有模式 ...
    "auto_battle": ["自動對戰"],
}

# locales/en_US.py
TEXT_PATTERNS = {
    # ... 现有模式 ...
    "auto_battle": ["Auto Battle"],
}
```

## 调试工具

在 `debug_tool.py` 中新增两个功能：

### 11. 颜色取样器

从截图指定位置/区域获取 HSV 值，帮助确定颜色范围。

```
>>> 颜色取样...
截图已保存: /tmp/.../for_color.png
输入坐标 (x,y) 或区域 (x1,y1,x2,y2): 150,300,190,340

区域 HSV 分析:
  主色调: H=65, S=180, V=200 (绿色)
  绿色像素占比: 78.5%
  建议范围: H=[55-75], S=[100-255], V=[150-255]
```

### 12. 颜色状态测试

测试 COLOR_STATES 配置是否正确。

```
可用的状态:
  1. auto_battle

选择状态: 1

>>> 检测 auto_battle 状态...
定位文字: "自動對戰" @ (200, 500)
检测区域: (156, 488, 196, 536)
绿色占比: 72.3%
判定结果: 开启 ✓
```

## 文件变更清单

| 文件 | 变更 |
|------|------|
| `recognizer.py` | 新增 COLORS、COLOR_STATES 常量；新增 check_color_ratio、check_green、check_state 方法 |
| `locales/zh_Hant.py` | TEXT_PATTERNS 新增 "auto_battle" |
| `locales/en_US.py` | TEXT_PATTERNS 新增 "auto_battle" |
| `debug_tool.py` | 新增菜单项 11（颜色取样器）、12（颜色状态测试） |
