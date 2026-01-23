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
1. open_pack 仍直接调用 template_matcher 与 ocr_engine，且存在多处“滑动/切换 + 重新截图 + 再匹配”的重复流程，尚未真正收敛为可复用函数。
2. page_detector 已有截图与 OCR 缓存，但任务层仍在自行截图与识别，缺乏统一入口。
3. 需要将模板/OCR 相关操作收敛到 page_detector 或 gesture 的封装函数，任务层只调用高层动作。

## 线索（来自现有扫描）
- src/ptcgp_auto_v2/tasks/open_pack.py
- src/ptcgp_auto_v2/tasks/claim_gifts.py
- src/ptcgp_auto_v2/tasks/claim_rewards.py
- src/ptcgp_auto_v2/infra/adb.py
- src/ptcgp_auto_v2/infra/page_detector.py
- src/ptcgp_auto_v2/utils/gesture.py
