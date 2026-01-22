# V2 待办任务

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
- [x] 数据库层迁移到 SQLModel + Alembic
  - 使用 SQLModel ORM 替代 dataclass + 原生 SQL
  - 集成 Alembic 支持自动生成迁移脚本
  - 详见 `src/ptcgp_auto_v2/db/README.md`

## 进行中

- [ ] 加个手动指定adb切换账号功能（方便我手动检查账号的任务完成情况）



## 高优先级

- [ ] 识别卡种类和等级（）
  - [ ] 使用相似度匹配匹配卡牌名字
  - [ ] 识别每次账号开包情况，并记录到数据库（可配置记录哪些目标卡牌或哪些等级或哪些类型）
  - [ ] 自动更新来自github的他人维护的基础数据（https://github.com/flibustier/pokemon-tcg-pocket-database）
  - [ ] 搭建简单的web页面来展示所有账号开包记录情况，使用github他人维护的静态资源
- [ ] `send_card` - 每日送卡任务

## 中优先级


- [ ] `add_friend` - 加好友任务
- [ ] 任务失败通知（Webhook）
- [ ] `battle` - 自动对战任务（可复用 v1 逻辑）

## 低优先级

- [ ] 非 Root 设备支持（仅通过 friend_id 识别账号，无法切换）
- [ ] 多语言 locales 完善（目前仅 zh_Hant）
- [ ] Web UI 管理界面
- [ ] 任务执行日志持久化
