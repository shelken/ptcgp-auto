# Findings

## 说明
- 仅记录与 v2 重构相关的发现
- 每次发现重复逻辑或不合理依赖即记录

## 当前发现（Phase 1）
1. 任务层在多个阶段重复执行“截图 → 模板匹配/文本识别 → adb 点击/滑动”的通用流程，缺乏统一封装。
2. open_pack/claim_gifts/claim_rewards 中存在高度相似的逻辑路径：
   - 主页或列表页：模板匹配图标后点击。
   - 失败时退回或再次截图。
   - OCR 识别按钮文本后点击。
3. 直接操作底层细节的集中模块：
   - infra/adb.py：设备交互与坐标缩放。
   - infra/page_detector.py：截图 + OCR + 模板识别耦合。
   - utils/gesture.py：基于 OCR/模板结果进行点击/滑动的操作集合，但在任务中仍重复编排流程。
4. 任务模块倾向直接调用 template_matcher 与 adb 的细节，导致跨模块耦合提升，难以复用或替换底层实现。

## 当前状态补充（Phase 3）
1. open_pack 已将模板匹配/滑动/切换流程下沉到 gesture/page_detector，任务层不再直接操作底层细节。
2. claim_gifts/claim_rewards 已改为使用 page_detector.capture + find_template_with_scale，移除 recognizer + adb.screenshot 组合。
3. claim_rewards 已统一使用 page_detector.get_last_page_context，避免重复取 screenshot。
4. OCR 文本匹配已集中到 gesture.normalize_text/is_text_visible，减少任务层重复逻辑。
5. 图标模板匹配的 scale=1.0 明确改为默认参数形式，避免业务层冗余。
6. 模板阈值默认值统一为 0.7，代码中已移除与默认一致的显式传参。
7. executor 中任务构建与通用 handler 注册在 TaskExecutor / AccountBatchExecutor 之间存在重复。
8. ocr 中 find_text / find_all_text 存在相同的文本标准化与匹配逻辑，可集中抽取。
9. scheduler 中批量与单任务路径的前置任务插入与 executor 提交流程存在重复，可统一为 helper。
10. page_detector 的文本匹配逻辑与 ocr 的标准化/匹配重复，可统一复用。

## 线索（来自现有扫描）
- src/ptcgp_auto_v2/tasks/open_pack.py
- src/ptcgp_auto_v2/tasks/claim_gifts.py
- src/ptcgp_auto_v2/tasks/claim_rewards.py
- src/ptcgp_auto_v2/infra/adb.py
- src/ptcgp_auto_v2/infra/page_detector.py
- src/ptcgp_auto_v2/utils/gesture.py
