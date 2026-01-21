# V2 待办任务

## 已完成

- [x] 核心框架：Scheduler、Executor、DevicePool、TaskBase
- [x] 数据库层：Account、TaskPlan、TaskInstance、PackRecord
- [x] 基础设施：ADB、OCR、模板匹配、页面检测
- [x] 账号同步：从设备提取 XML 文件 (`account_syncer.py`)
- [x] 开包任务：`open_pack.py`
- [x] 账号切换：XML 注入 (`account_switcher.py`) - 已测试通过
- [x] session_token_iat 追踪：确保保存最新 token

## 进行中

- [ ] `fetch_friend_id` 任务 - 通过 UI 获取 friend_id 和 nickname（参考 v1 `actions/user.py`）

## 高优先级

- [ ] 实现 friend_id 填充任务
- [ ] `send_gift` - 每日送礼任务

## 中优先级

- [ ] `add_friend` - 加好友任务
- [ ] `battle` - 自动对战任务（可复用 v1 逻辑）
- [ ] 任务失败通知（Webhook）

## 低优先级

- [ ] 非 Root 设备支持（仅通过 friend_id 识别账号，无法切换）
- [ ] 多语言 locales 完善（目前仅 zh_Hant）
- [ ] Web UI 管理界面
- [ ] 任务执行日志持久化
