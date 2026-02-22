# Codebase Concerns

**Analysis Date:** 2026-02-23

## Tech Debt

**未实现的公共页面处理:**
- Issue: `common.py` 中存在两个 TODO 注释，`popup_clean_and_download` 和 `popup_auth_again` 页面处理未完善
- Files: `src/ptcgp_auto_v2/config/pages/common.py:13`, `src/ptcgp_auto_v2/config/pages/common.py:95`
- Impact: 游戏异常弹窗可能导致任务卡死或无限等待
- Fix approach: 完善弹窗处理逻辑，`auth_again` 需要通知机制触发人工介入

**Hook 基类未实现:**
- Issue: `Hook.run()` 方法抛出 `NotImplementedError`，要求子类必须实现
- Files: `src/ptcgp_auto_v2/core/hooks.py:63`
- Impact: 若直接实例化 `Hook` 基类会运行时崩溃
- Fix approach: 保持现状（ABC 抽象方法设计正确），但可考虑使用 `@abstractmethod` 替代手动抛出

**大型文件复杂度高:**
- Issue: 多个核心文件超过 500 行，维护成本高
- Files:
  - `src/ptcgp_auto_v2/core/scheduler.py` (1163 行)
  - `src/ptcgp_auto_v2/tasks/exchange_cards.py` (1029 行)
  - `src/ptcgp_auto_v2/tasks/manage_friendship.py` (922 行)
  - `src/ptcgp_auto_v2/core/executor.py` (860 行)
  - `src/ptcgp_auto_v2/tasks/init_account.py` (846 行)
  - `src/ptcgp_auto_v2/tasks/open_pack.py` (817 行)
  - `src/ptcgp_auto_v2/tasks/send_card_daily.py` (788 行)
- Impact: 理解难度大，测试覆盖难，修改风险高
- Fix approach: 考虑拆分为更小的模块，如 `scheduler.py` 可拆分为调度逻辑、任务生成、设备管理等

**v1 Legacy 代码残留:**
- Issue: v1 版本代码 (57 个 Python 文件) 仍保留在 `src/ptcgp_auto/` 目录
- Files: `src/ptcgp_auto/` 目录下全部文件
- Impact: 代码库膨胀，可能造成混淆，增加搜索噪音
- Fix approach: 若 v1 不再维护，考虑归档或移除；若需保留，添加 `# Deprecated` 注释

**停滞任务通知缺失:**
- Issue: `common_handlers.py` 中 TODO 注释表明停滞流程的通知机制未实现
- Files: `src/ptcgp_auto_v2/utils/common_handlers.py:117`
- Impact: 任务陷入停滞时无告警，用户无法感知
- Fix approach: 接入 Notifier 发送停滞告警

## Known Bugs

**无已知 Bug 记录:**
- 项目测试覆盖较好，未发现明显 bug 注释或 `BUG` 标记

## Security Considerations

**JWT Token 解码无签名验证:**
- Risk: `_decode_jwt_payload` 方法解码 JWT 但不验证签名，仅提取 payload
- Files: `src/ptcgp_auto_v2/infra/account_syncer.py:287-314`
- Current mitigation: 仅用于提取 `iat` 时间戳，不涉及敏感操作
- Recommendations: 保持现状，因为仅用于账号信息同步，无安全敏感操作

**环境变量文件存在:**
- Risk: `.env` 文件存在于项目根目录
- Files: `.env`
- Current mitigation: 已加入 `.gitignore`（需确认），有 `.env.example` 作为模板
- Recommendations: 确保 `.env` 不会被提交，定期检查 git 历史

**会话令牌存储:**
- Risk: `session_token_iat` 存储在数据库中
- Files: `src/ptcgp_auto_v2/db/models/account.py:30-44`
- Current mitigation: 仅存储 `iat` 时间戳，非完整 token
- Recommendations: 保持现状，存储的是签发时间而非敏感凭证

## Performance Bottlenecks

**大量 sleep 调用:**
- Problem: 代码中有 41 处 `time.sleep()` 调用，部分为固定等待时间
- Files: `src/ptcgp_auto_v2/infra/adb.py`, `src/ptcgp_auto_v2/core/scheduler.py`, `src/ptcgp_auto_v2/tasks/init_account.py` 等
- Cause: UI 操作需要等待响应、轮询间隔、账号切换等待
- Improvement path: 
  - 短等待 (0.5-2s) 可考虑改为条件轮询
  - 长等待 (如账号创建 8s) 需要结合实际业务场景优化
  - 轮询间隔已配置化 (`poll_interval`)，可调整

**卡牌 Hash 内存缓存:**
- Problem: `CardHashManager` 将所有系列 Hash 加载到内存
- Files: `src/ptcgp_auto_v2/infra/card_hash_manager.py:43-106`
- Cause: 避免每次匹配都从磁盘加载
- Current mitigation: 按系列懒加载，失败卡牌记录到内存缓存避免重试
- Improvement path: 大规模卡牌时可能内存占用高，可考虑 LRU 缓存策略

**YOLO 模型加载阻塞:**
- Problem: 首次识别时加载模型可能较慢
- Files: `src/ptcgp_auto_v2/infra/model_manager.py:43-203`
- Cause: 模型文件较大，加载需要时间
- Current mitigation: 支持后台异步加载 (`_model_ready` Event)
- Improvement path: 启动时预加载模型

## Fragile Areas

**页面识别依赖 OCR 准确性:**
- Files: `src/ptcgp_auto_v2/infra/page_detector.py`, `src/ptcgp_auto_v2/infra/ocr.py`
- Why fragile: OCR 结果受截图质量、游戏语言、分辨率影响
- Safe modification: 新增页面规则时必须提供多语言文本配置 (`locales/`)
- Test coverage: `infra/ocr.py` 和 `infra/page_detector.py` 均无单元测试

**账号切换逻辑:**
- Files: `src/ptcgp_auto_v2/infra/account_switcher.py`
- Why fragile: 依赖模拟器 UI 结构，不同版本模拟器可能表现不同
- Safe modification: 修改前需在目标模拟器版本测试
- Test coverage: 无单元测试，依赖集成测试验证

**交换卡牌状态机:**
- Files: `src/ptcgp_auto_v2/tasks/exchange_cards.py` (1029 行)
- Why fragile: 多状态 (sending/sended) 多页面流转，逻辑复杂
- Safe modification: 严格遵循 `AGENTS.md` 中"页面优先原则"，避免用状态拦截路由
- Test coverage: 有 `test_exchange_cards_task.py` (438 行) 覆盖核心分支

**好友选择流程:**
- Files: `src/ptcgp_auto_v2/tasks/utils/friend_selection_flow.py` (384 行)
- Why fragile: 滚动列表检测、好友状态判断、边界处理复杂
- Safe modification: 修改滚动逻辑需注意无限循环风险
- Test coverage: 有 `test_friend_selection_flow.py` 覆盖

## Scaling Limits

**设备池并发限制:**
- Current capacity: 默认 `max_workers=4`
- Limit: 受物理设备/模拟器数量限制
- Scaling path: 
  - 配置 `auto_scale_emulators` 支持自动扩缩容
  - 参数: `auto_scale_max_devices`, `auto_scale_min_idle_devices`

**数据库写入压力:**
- Current capacity: SQLite 单文件数据库
- Limit: 高频写入时可能遇到锁竞争
- Scaling path: 
  - 当前任务量下单实例足够
  - 大规模部署可考虑 PostgreSQL

**Web UI 并发:**
- Current capacity: FastAPI + uvicorn 单进程
- Limit: 计算密集型请求（如卡牌统计）可能阻塞
- Scaling path: 
  - 使用多 worker 启动: `uvicorn app:app --workers N`
  - 或引入异步任务队列

## Dependencies at Risk

**平台依赖 (macOS Only):**
- Risk: 依赖 Apple Vision Framework 进行 OCR，仅支持 macOS
- Files: `src/ptcgp_auto_v2/infra/ocr.py:60-66`
- Impact: 无法在 Linux/Windows 运行
- Migration plan: 保持现状（项目定位为 macOS 工具），或考虑 Tesseract OCR 替代方案

**ultralytics YOLO:**
- Risk: 深度学习框架，版本更新可能有 API 变更
- Current version: `>=8.3.0`
- Impact: 模型加载/推理失败
- Migration plan: 锁定具体版本号，升级前测试兼容性

**uiautomator2:**
- Risk: ADB 自动化库，依赖 Android Debug Bridge
- Current version: `>=3.5.0`
- Impact: 模拟器连接/控制失败
- Migration plan: 保持版本稳定，关注上游更新

## Missing Critical Features

**无关键功能缺失:**
- 项目功能完整，任务类型覆盖开包、领取、交换、好友管理等

## Test Coverage Gaps

**基础设施层无单元测试:**
- What's not tested: 10 个 infra 文件无对应测试
- Files:
  - `src/ptcgp_auto_v2/infra/account_syncer.py`
  - `src/ptcgp_auto_v2/infra/card_hash_manager.py`
  - `src/ptcgp_auto_v2/infra/model_manager.py`
  - `src/ptcgp_auto_v2/infra/icon_group_detector.py`
  - `src/ptcgp_auto_v2/infra/ocr.py`
  - `src/ptcgp_auto_v2/infra/page_detector.py`
  - `src/ptcgp_auto_v2/infra/template.py`
  - `src/ptcgp_auto_v2/infra/account_switcher.py`
  - `src/ptcgp_auto_v2/infra/yolo_card_recognizer.py`
  - `src/ptcgp_auto_v2/infra/adb.py`
- Risk: 核心基础设施修改可能导致回归
- Priority: 中（部分通过集成测试间接覆盖）

**大量 return None 模式:**
- What's not tested: 50+ 处 `return None` 模式，边界条件可能未覆盖
- Files: 遍布 infra 和 tasks 层
- Risk: None 值处理不当可能导致空指针异常
- Priority: 低（运行时已验证稳定）

**类型注解忽略:**
- What's not tested: 82 处 `# type: ignore` 或 `Any]` 模式
- Files: 遍布整个代码库
- Risk: 类型安全性降低，重构风险增加
- Priority: 低（渐进式类型改进）

## Code Quality Concerns

**宽泛异常捕获:**
- Issue: 30+ 处 `except Exception as e` 模式
- Files: `src/ptcgp_auto_v2/infra/account_syncer.py`, `src/ptcgp_auto_v2/infra/model_manager.py`, `src/ptcgp_auto_v2/tasks/open_pack.py` 等
- Impact: 可能隐藏具体错误类型，影响调试
- Fix approach: 逐步细化为具体异常类型，或添加明确的错误日志

**单例模式全局变量:**
- Issue: 多个单例使用模块级全局变量实现
- Files:
  - `src/ptcgp_auto_v2/infra/card_hash_manager.py:409-429`
  - `src/ptcgp_auto_v2/infra/model_manager.py:230-243`
  - `src/ptcgp_auto_v2/infra/notifier.py:434-442`
  - `src/ptcgp_auto_v2/db/connection.py:205-215`
  - `src/ptcgp_auto_v2/config/settings.py:276-292`
- Impact: 测试隔离困难，需手动清理状态
- Fix approach: 测试中使用 fixture 重置单例状态

**数据库无物理外键:**
- Issue: 所有物理外键约束已被移除，仅保留逻辑关系
- Files: `src/ptcgp_auto_v2/db/models/*.py`
- Impact: 数据一致性依赖应用层保证
- Note: 设计决策为保持灵活性，非缺陷
- Fix approach: 保持现状，在应用层确保数据完整性

---

*Concerns audit: 2026-02-23*
