# V2 待办任务

## 进行中

- [ ] 发起交换卡牌
- [ ] wonder_pick 第一次滑动前没有扫描

## 高优先级


## 中优先级

- [ ] 任务失败通知（Webhook）
- [ ] `battle` - 自动对战任务（可复用 v1 逻辑）
- [ ] 自动更新来自github的他人维护的基础数据(metadata)

## 低优先级

- [ ] 非 Root 设备支持（仅通过 friend_id 识别账号，无法切换）
- [ ] 多语言 locales 完善（目前仅 zh_Hant）
- [ ] 任务执行日志持久化

## 已完成

- [x] 核心框架：Scheduler、Executor、DevicePool、TaskBase
- [x] 数据库层：Account、TaskPlan、TaskInstance、PackRecord
- [x] 基础设施：ADB、OCR、模板匹配、页面检测
- [x] 账号同步：从设备提取 XML 文件 (`account_syncer.py`)
- [x] 开包任务：`open_pack.py`
- [x] 账号切换：XML 注入 (`account_switcher.py`) - 已测试通过
- [x] session_token_iat 追踪：确保保存最新 token
- [x] `fetch_account_info` 任务：自动获取 friend_id/nickname/level
- [x] 多分辨率支持：基准像素 + scaled_x/scaled_y 缩放
- [x] 对所有账号进行轮询每日任务
- [x] 领取所有任务奖励（每日）
- [x] 领取所有礼物（每日）
- [x] 任务批量执行改造（见 `docs/plans/batch-task-execution.md`）
  - 同一账号的任务在同一设备上按 task_plan 顺序连续执行
  - 减少账号切换，提高效率
- [x] daemon 模式异常任务自动恢复
  - 定期检测超时的 running/blocked/skipped/failed 任务
  - running/blocked 超时 10 分钟自动重置
  - skipped 超时 1 小时自动重置
  - failed 每次检查都重置（依赖重试次数限制）
- [x] 数据库层迁移到 SQLModel
  - 使用 SQLModel ORM 替代 dataclass + 原生 SQL
  - 详见 `src/ptcgp_auto_v2/db/README.md`
- [x] 加个手动指定adb切换账号功能（方便我手动检查账号的任务完成情况）
- [x] 重构代码
- [x] 让账号管理能够修改备注信息和显示
- [x] 卡牌相关
  - [x] 识别卡稀有度（使用模板匹配）
  - [x] 整合到开包任务的识别
  - [x] 账号开包记录到数据库（可配置记录哪些目标卡牌或哪些等级或哪些类型）
  - [x] 测试账号开包情况（已验证）
  - [x] 更新来自github的他人维护的基础数据（https://github.com/flibustier/pokemon-tcg-pocket-database）
  - [x] 完善卡种类（改造 sync_metadata）（改用cards.extra.json作为来源）（支援者为supporter）
  - [x] ~~完善支援者卡（目前仓库缺失，只有pokemon卡）~~ 没有缺失，数据是有的
  - [x] 搭建简单的web页面来展示所有账号开包记录情况，使用github他人维护的静态资源
  - [x] 开包点数记录，每个用户对应每个系列包有不同的开包点数
  - [x] 完善card-set（支持多语言名字，方便菜单显示）
- [x] 迁移到uv管理，方便多工作区数据共享
- [x] 获取当前账号交换点数，并在web端账号管理显示，在fetch_account_info的task中实现
- [x] 出现各种手指的情况下，直接点击手指位置（兜底处理）
- [x] 拆分repository
- [x] 彻底废弃账号的task_plan_id，使用多关联
- [x] 尝试删除shared_prefs看看什么效果(删掉后直接变成新账号流程，即使有xml也不行，还需要其他各种文件)
- [x] 网页端能够Edit Plan的时候进行排序任务
- [x] `init-account` [自动完成新账号流程](needs/01-自动完成新账号流程.md)
- [x] 修复管理页侧边栏状态不一致问题，确保抽卡记录等子页面在刷新后可通过 URL 正确恢复。
- [x] 修正 quick_tap 屏幕中心的时，出现误点的情况（目前有在开卡之后点开卡牌）
- [x] 改用公共资源的卡包封面，而不是当前手动裁剪
- [x] web 放大多角度展示卡牌
- [x] 数据库配置更新（新卡包出来时，每日抽的卡包更新） 直接使用最新release
- [x] 分析 yolo11 定位卡牌 + 哈希感知算法 匹配 方案
- [x] claim_rewards 优化，应该是领取完页面的全部领取，点主题收藏，然后退出来，识别。然后反复识别十次。
- [x] 训练yolo模型，感知hash匹配
- [x] 检查当前用户的高稀有度卡牌，并记录（点击底部卡牌icon->按获取顺序倒排->点搜索->选择稀有度->在卡牌页面缩放一次->识别->下滑后识别直到底部 判断标志是本次所有卡牌都在库中就算结束）
- [x] 新的识别机制识别该账号拥有的卡片（能够配置仅识别哪些稀有度的）
- [x] 修复开包点数错误
- [x] 多次出现认证错误情况，点完ok也没用，直接重启整个模拟器
- [x] `wonder_pick` - 自动得卡挑战(检查当前卡面的稀有度，只要2星以上)
- [x] 双手指缩放(uiautomator2)
- [x] `manage_friendship` - 管理好友关系任务
- [x] `give_cards` - 每日送卡任务
