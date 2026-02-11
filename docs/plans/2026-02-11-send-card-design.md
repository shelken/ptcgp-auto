# 每日送卡功能设计（已确认）

## 用户原始诉求

> 先阅读一下我整理的需求，你看下如何设计这个送卡功能。

补充确认：
- 任务触发使用 TaskPlan。
- 配对关系在每日任务前做增量补齐。
- 奇数账号落单当日跳过。
- reset_type 默认使用 interval，间隔 86400 秒。
- 记录送卡时同步更新 account_cards 中该卡剩余数量。
- 新账号有 14 天冷冻期，期间不能进入分送页面。

## 目标与边界

- 目标：实现系统内账号的每日自动送卡，优先满足稳定获取每日沙子。
- 初版范围：
  - 自动配对关系（系统内账号）
  - 固定卡策略（A1-153 嘎啦嘎啦）
  - 好友前置依赖（通过 manage_friendship）
  - 送卡记录落库 + 库存同步
- 非目标（延后）：
  - 系统外账号人工关系维护
  - 动态选择“数量最多 RR 卡”策略

## 架构设计

### 1) 调度与任务

- 新任务：`send_card_daily`
- `reset_type`：`interval`（默认 86400 秒，由 TaskPlan 可覆盖）
- 任务执行前通过 `GiftPairingService` 增量补齐关系，再通过 `FriendPreHook` 保证好友关系。

### 2) 数据模型

- `account_gift_pairs`
  - 维护稳定送卡关系（账号 -> 目标）
  - 一账号仅保留一个有效目标
- `account_gift_records`
  - 维护每日送卡状态流水
  - 单日幂等：`(account_id, target_friend_id, biz_date_local)` 唯一

### 3) 关系策略

- 参与账号：有 friend_id 的系统账号
- 排序规则：SR/SAR 总数降序，账号 ID 升序兜底
- 增量补齐：已有稳定双向关系不改动，仅为未配对账号补新关系
- 奇数账号：最后一个账号当日不配对
- 冷冻期过滤：`created_at + 14天` 以内账号不参与配对

### 4) 送卡与库存同步

- 固定卡：A1-153
- 成功后更新 `account_gift_records` 为 success
- 同步 `account_cards.count`：优先使用 UI 识别到的 `after_count`，失败时降级为 `before_count-1` 或数据库值-1
- 无需执行 UI 的场景（冷冻期/无可用目标/当日已成功）按 `completed` 收敛，避免重启后被 `skipped` 重置重跑
- `fetch_account_info` 在冷冻期内直接将 `exchange_points=0` 并完成任务，避免无效进入交换页面
- 对于上述“完成即返回”场景，任务会携带 `complete_reason`，并写入任务实例展示信息，便于 Web 任务页查看原因
- 送卡成功后通过 post hook 唤醒目标账号：先置 `claim_gifts` 为 pending，再置 `send_card_daily` 为 pending，优先让目标账号领取后再回送

## 实施计划

1. 新增模型与仓储：gift pair / gift record
2. 新增服务：关系补齐与记录服务
3. 新增任务：`send_card_daily`
4. 本地化补齐：送卡相关 OCR 关键词
5. 验证：服务层单测 + 任务流程回归

## 进度

- [x] 方案确认
- [x] 文档落地
- [x] 核心开发（模型/仓储/服务/任务）
- [ ] 真机流程验证与参数调优
