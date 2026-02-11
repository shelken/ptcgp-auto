# 每日送卡管理中心接入实施计划

> 用户原始诉求（原文保留）：
> 目前已经完成了 @src/ptcgp_auto_v2/tasks/send_card_daily.py
>
> 现在需要把 @src/ptcgp_auto_v2/db/models/account_gift_record.py
> @src/ptcgp_auto_v2/db/models/account_gift_pair.py
>
> 两个表的记录搬到 @src/ptcgp_auto_v2/web/ 的管理中心，
> 左tab栏就叫每日送卡，我需要看到每日送卡情况，和目前账号的配对情况。
> 配对情况不是每个两两的配对记录直接显示在列表，不够直观，需要更加直观的显示谁跟谁目前是配对关系。

## 目标

在管理中心新增“每日送卡”页面：

1. 默认展示今天的送卡执行情况，并支持按业务日期切换。
2. 以“配对卡片（A <-> B）”展示当前稳定配对关系。
3. 对异常/不完整配对关系单独分组展示，避免混在主视图中。

## 范围

- 仅改 `src/ptcgp_auto_v2/web/` 展示链路与对应查询/服务。
- 不改任务调度逻辑，不改数据库表结构。

## 实施步骤

### 1) 测试先行（TDD Red）

- 新增 `tests/test_daily_gift_queries.py`
  - 验证按 `biz_date_local` 查询送卡记录。
  - 验证仅返回 `is_active=true` 的配对记录。
- 新增 `tests/test_daily_gift_service.py`
  - 验证双向配对合并为单个关系卡片。
  - 验证单边/互指不一致进入异常分组。

### 2) 查询层

- 新增 `src/ptcgp_auto_v2/web/queries/daily_gift_queries.py`
  - `list_daily_gift_records(session, biz_date_local, limit)`
  - `list_active_gift_pairs(session)`
  - `list_accounts_by_ids(session, account_ids)`

### 3) 服务层

- 新增 `src/ptcgp_auto_v2/web/services/daily_gift_service.py`
  - `build_daily_gift_context(session, lang, biz_date_local)`
  - 统计：总记录/成功/失败/等待。
  - 配对可视化：把 `(a->b, b->a)` 合并为 `a<->b`。
  - 异常分组：单边关系、互指不一致、target 缺失。

### 4) 路由层

- 新增 `src/ptcgp_auto_v2/web/routers/daily_gift.py`
  - `GET /management/daily-gift`
  - 参数：`lang`、`biz_date_local`（默认当天）

### 5) 模板层

- 新增 `src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`
  - 区块 A：日期筛选 + 刷新
  - 区块 B：每日送卡记录表
  - 区块 C：当前配对卡片网格（直观显示谁跟谁）
  - 区块 D：异常关系列表

### 6) 主页面接入

- 修改 `src/ptcgp_auto_v2/web/templates/index.html`
  - 管理中心左侧新增“每日送卡”入口。
- 修改 `src/ptcgp_auto_v2/web/static/js/modules/tabs.js`
  - 管理页 hash 白名单加入 `daily-gift`。
- 修改 `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`
  - 初始 hash 自动激活逻辑加入 `daily-gift`。
- 修改 `src/ptcgp_auto_v2/web/app.py`
  - 注册 `daily_gift` 路由。

### 7) 文案与多语言

- 修改：
  - `src/ptcgp_auto_v2/web/locales/zh_CN.json`
  - `src/ptcgp_auto_v2/web/locales/en.json`
- 新增页面标题、区块标题、空态、统计与异常原因文案。

### 8) 验证

- 运行：
  - `PYTHONPATH=src pytest tests/test_daily_gift_queries.py tests/test_daily_gift_service.py -v`
- 若通过，再进行页面联调验证。

## 风险与约束

- 配对展示以 `target_account_id` 为核心，若数据仅有 friend_id 无系统账号映射，会进入异常区。
- 时间语义保持“本地日期”一致，不混用 UTC。
