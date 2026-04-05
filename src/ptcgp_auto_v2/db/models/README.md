# db/models

本目录放的是数据库模型定义，不只是字段清单。

## 写法要求

- 每次改表结构，必须同时更新对应模型里的类说明和字段 `description`
- 字段说明不能只写“是什么”，还要写“为什么有这个字段”“谁会读它”“它不该承担什么语义”
- 如果某个字段是兼容历史保留、派生缓存、运行时快照，也必须直接写明
- 改了表结构但没补字段逻辑说明，视为改动不完整

## 当前关键关系

### `AccountGiftPair`

- 作用：固定送卡配对表
- 一条记录表示：账号 `account_id` 在 `send_card_daily` 里应该送给谁
- 真实语义：缺失时可以补建，建立后默认保持稳定，不在任务运行时自动重排或失效
- 约束：每个 `account_id` 只能有一条当前配对
- `target_account_id` 是系统内目标账号，给回送唤醒和 Web 配对展示用
- `target_friend_id` 是页面操作时真正要匹配的 friend_id 执行快照；目标账号更新 friend_id 后应同步刷新
- `is_active` 现在只是兼容历史字段，固定为 `True`

### `AccountGiftRecord`

- 作用：每日送卡执行记录表
- 一条记录表示：某账号在某个业务日，对某个目标执行了一次送卡流程
- 与 `AccountGiftPair` 的关系：
  - `AccountGiftPair` 决定今天应该送给谁
  - `AccountGiftRecord` 记录今天实际执行到了哪一步、是否成功
- 约束：`(account_id, target_friend_id, biz_date_local)` 唯一，保证同一目标每天只有一条记录
- `target_friend_id` 保留的是执行当时的目标快照，后续配对变化不回写历史

### `TaskInstance`

- 作用：账号级长期任务状态表
- 一条记录表示：某账号的一种任务当前运行到什么状态
- 时间字段分工必须分开：
  - `status_changed_at`：只管状态切换时间，给 running/blocked/failed/skipped 超时回收用
  - `schedule_anchor_at`：只管 completed 后的调度锚点
  - `last_completed_at`：只管展示“上次完成”
  - `updated_at`：只管“这行最近写过”，不再承载状态语义

## 本次涉及的实际规则

- `send_card_daily` 先查 `AccountGiftPair`，拿到固定目标后再执行送卡
- 如果固定配对缺失，可以补建一次；补建目标来自既有排序规则
- 已有固定配对默认不改，不因为运行时检查自动失效
- 送卡是否成功、失败原因、库存变化，都写进 `AccountGiftRecord`
