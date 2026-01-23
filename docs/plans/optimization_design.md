# 高性能图像识别架构设计方案

本文档旨在阐述如何将 `debug_tool` 中验证过的高性能匹配策略（快速筛选、多线程、ROI、自适应缩放）落地到生产级代码 (`src/ptcgp_auto_v2/`) 中，并提供灵活的配置化方案。

## 1. 核心设计理念

### 1.1 分层架构
我们将识别能力分为三层：
1.  **基础能力层 (Recognizer Core)**: 提供最底层的 OpenCV 封装（如 `matchTemplate`, `find_contours`）。
2.  **高级策略层 (Matching Strategy)**: 封装高性能匹配逻辑（Batch Match, Quick Reject, Threading），对上层屏蔽复杂的优化细节。
3.  **业务配置层 (Page Configuration)**: 为不同页面（Battle, Pack Opening, Home）定义专属的识别参数（ROI, Scale, Threshold）。

### 1.2 配置即代码 (Configuration as Code)
避免在业务逻辑中硬编码坐标和参数。所有识别相关的参数应通过配置对象管理，支持针对不同分辨率或设备动态调整。

---

## 2. 详细设计方案

### 2.1 增强 Recognizer 类

在 `src/ptcgp_auto/recognizer.py` 中扩展 `Recognizer` 类，增加批量匹配接口。

```python
class Recognizer(TemplateMatcherMixin, ...):

    def match_templates_batch(
        self,
        image: Image.Image,
        template_names: List[str],
        scale: float = 1.0,
        roi: Optional[Tuple[int, int, int, int]] = None,
        threshold: float = 0.8,
        use_quick_match: bool = True,
        max_workers: int = 4
    ) -> List[MatchResult]:
        """
        高性能批量匹配方法

        Args:
            roi: (x, y, w, h) 指定感兴趣区域，自动裁剪和坐标还原
            use_quick_match: 是否启用下采样快速筛选
            max_workers: 并行线程数
        """
        # 1. ROI 裁剪 (如有)
        # 2. 图像预处理 (转 cv2, 生成 small_image)
        # 3. ThreadPoolExecutor 并行执行
        # 4. 坐标还原 (Add ROI offset)
        # 5. 返回结果列表
```

### 2.2 定义页面识别配置 (Page Config)

为每个页面定义一个配置类，集中管理该页面下所有元素的识别参数。

```python
# src/ptcgp_auto_v2/config/pages.py

from dataclasses import dataclass

@dataclass
class RecognitionProfile:
    roi: Tuple[int, int, int, int] = None
    scale_range: Tuple[float, float] = (0.8, 1.2)
    base_scale: float = 1.0  # 基于当前设备的预估缩放比
    threshold: float = 0.8

class PackOpeningPageConfig:
    # 定义开包界面的卡牌识别区域 (忽略顶部状态栏和底部按钮)
    CARD_AREA_ROI = (0, 400, 1080, 1100)

    # 该页面下的卡牌通常显示的缩放比例
    CARD_SCALE = 0.67

    # 识别配置
    RECOGNITION = RecognitionProfile(
        roi=CARD_AREA_ROI,
        base_scale=CARD_SCALE,
        threshold=0.85 # 开包界面清晰，可提高阈值减少误判
    )

# 在业务逻辑中调用
# recognizer.match_templates_batch(screenshot, cards, **PackOpeningPageConfig.RECOGNITION.as_dict())
```

### 2.3 智能 ROI 与两阶段搜索

对于位置不固定的元素（如对战中对方出战的宝可梦），可以使用两阶段搜索策略：

1.  **粗略定位 (Coarse Search)**:
    *   将屏幕缩小 4-8 倍。
    *   全屏搜索，阈值调低。
    *   目的：快速找到大概位置（Candidate Regions）。
2.  **精细确认 (Fine Search)**:
    *   在候选区域附近（ROI）原图大小进行精确匹配。

```python
def smart_find(self, img, template):
    # Phase 1: Downscale search
    candidates = self.find_candidates_low_res(img, template)

    for roi in candidates:
        # Phase 2: Precise match in ROI
        match = self.match_template(img, template, roi=roi)
        if match:
            return match
```

### 2.4 动态缩放比例管理

不同设备（分辨率、DPI）对应的 `scale` 不同。不应写死 `0.67`。

*   **初始化阶段**：应用启动时，根据 `adb.get_screen_size()` 计算全局 `GLOBAL_SCALE_FACTOR`。
*   **基准分辨率**：所有模板基于 `1080x1920` 制作。
*   **运行时计算**：`actual_scale = config.base_scale * GLOBAL_SCALE_FACTOR`。

---

## 3. 生产代码重构路线图

1.  **Refactor Recognizer**: 将 `non_interactive.py` 中的 `ThreadPoolExecutor` 和 Quick Match 逻辑移入 `Recognizer` 类，使其成为通用能力。
2.  **Config Migration**: 将散落在各处的 ROI 和 Scale 硬编码提取到 `src/ptcgp_auto_v2/config/` 下的页面配置中。
3.  **Task Integration**: 在 `ScanPacksTask` 或 `BattleTask` 中，替换原有的循环匹配逻辑，改用新的 `match_templates_batch` 接口。

## 4. 总结

通过将**高性能计算**下沉到基础设施层，将**业务参数**上浮到配置层，我们可以实现：
*   **开发效率**：业务代码只需关注“找什么”，无需关心“怎么找最快”。
*   **运行效率**：所有业务自动享受到多线程和快速筛选的性能红利。
*   **可维护性**：调整 ROI 或 Scale 只需修改配置文件，无需改动逻辑代码。
