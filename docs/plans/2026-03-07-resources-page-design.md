# 资源页拆分与排序设计文档

## 原始需求（用户原话）

> @src/ptcgp_auto_v2/db/models/account_stat.py
> @src/ptcgp_auto_v2/db/models/account_pack_point.py
>
> @src/ptcgp_auto_v2/web/templates/partials/account_list.html
>
> 想把资源列的资源移动到新的页面，方便我进行各种资源的排序
> 你看下应该怎么改。目前两张表可能有点麻烦。你看下什么方案更好？

## 用户澄清与约束（原话记录）

### 澄清 1：pack points 的排序交互

**用户原话：**
> 1

**上下文：**
- 初始选项 1 为“按选中的单个 series 排序（推荐）”

**后续反馈：**
> 1
> 看起来很怪。交互有点别扭。你仔细说说

**结论：**
- 不能采用“先进入独立资源页，再额外下拉选择 series，再排序”的交互
- 用户明确认为这种两段式操作别扭

### 澄清 2：拆子页面后的系列排序方式

**用户原话：**
> 如果是拆两个子页面，那么就不应该选择series了，你应该能够在表头直接点选系列排序。你看看表格的通用组件

**结论：**
- `pack points` 页面必须直接把 `series` 作为表头列
- 用户通过点击表头直接按对应 `series` 排序
- 不再保留额外的 `series` 选择器

### 澄清 3：资源页组织方式

**用户原话：**
> 可以

**上下文：**
- 上下文对应“一个资源入口，内部切 `账号资源 / 开包点数` 两个视图”的方案

**结论：**
- 管理页只新增一个 `resources` 入口
- 资源页内部切分为两个视图：`账号资源` 与 `开包点数`

## 目标

将当前账号列表中的资源列拆出到独立资源页，并保证：

- 账号列表职责回归账号管理，不再承担资源排序需求
- 账号级资源与系列级点数分开展示，避免同表混语义
- `AccountStat` 与 `AccountPackPoint` 两类资源都能排序
- `pack points` 采用表头直接点击系列列排序的交互
- 查询层不继续依赖全量 ORM 预加载 + Python 内存排序

## 非目标

- 不调整 `account_stats` 与 `account_pack_points` 的表结构
- 不新增新的资源汇总表或物化宽表
- 不改动任务采集资源数据的业务逻辑
- 不在本次引入复杂前端框架式局部路由
- 不为了小屏完全消除宽表横向滚动

## 现状分析

### 1. 数据模型天然分成两类资源

当前资源数据来自两张表：

- [`src/ptcgp_auto_v2/db/models/account_stat.py`](src/ptcgp_auto_v2/db/models/account_stat.py)
  - `account_id`
  - `exchange_points`
  - `pack_hourglass_count`
- [`src/ptcgp_auto_v2/db/models/account_pack_point.py`](src/ptcgp_auto_v2/db/models/account_pack_point.py)
  - 复合主键：`account_id + series`
  - `points`
  - `updated_at`

这意味着：

- `AccountStat` 是账号维度的单值资源，适合一行一个账号排序
- `AccountPackPoint` 是账号在多个 `series` 下的多值资源，不适合被当作单字段硬塞进同一资源列

### 2. 当前账号列表把两类资源混在同一列中

当前 [`src/ptcgp_auto_v2/web/templates/partials/account_list.html`](src/ptcgp_auto_v2/web/templates/partials/account_list.html) 的 `Resources` 列同时展示：

- `exchange_points`
- `pack_hourglass_count`
- 所有 `pack_points`

问题：

- 同一列里既有账号级资源，也有系列级资源
- 无法自然表达“按某个 `series` 排序”
- 账号列表因此承担了不属于账号管理本身的资源比较职责

### 3. 当前账号页排序方式不适合资源宽表

当前 [`src/ptcgp_auto_v2/web/services/account_service.py`](src/ptcgp_auto_v2/web/services/account_service.py) 的 `build_accounts_list_context()`：

- 通过 `AccountRepository.get_all()` 全量读取账号
- 在 Python 层完成搜索、排序、分页

而 [`src/ptcgp_auto_v2/db/repositories/account_repository.py`](src/ptcgp_auto_v2/db/repositories/account_repository.py) 的 `get_all()` 会预加载：

- `account_stat`
- `pack_points`
- `task_plan_associations`

这对当前账号管理页规模尚可，但对新资源页有两个问题：

- `pack points` 宽表排序无法继续依赖“把所有账号和所有点数都拉进内存再排序”
- 资源页已经是独立领域，应当拥有自己的查询层，而不是继续复用账号管理页上下文构造函数

### 4. 现有通用表格组件支持动态列排序

表格宏具备以下能力：

- [`src/ptcgp_auto_v2/web/templates/partials/macros/data_table.html`](src/ptcgp_auto_v2/web/templates/partials/macros/data_table.html) 中 `data_table_sort_button()` 允许模板层直接拼接任意排序 URL
- [`src/ptcgp_auto_v2/web/templates/partials/macros/tables.html`](src/ptcgp_auto_v2/web/templates/partials/macros/tables.html) 中 `table_container()` 支持通过 headers 列表动态生成表头

因此：

- `pack points` 的 `series` 列可以在模板层动态循环生成
- 不需要先改造通用表格宏本身

## 方案选择

### 方案 A：单独资源页，但 `pack points` 通过下拉选择 `series`

- 管理页新增资源页
- 页面里用户先选择某个 `series`
- 再按该 `series` 的点数排序

**优点：**
- 后端查询实现最简单
- 模板列数固定

**缺点：**
- 用户已明确认为交互别扭
- 页面语义已经是 `pack points` 时，再选一次 `series` 多余
- 用户无法直接在表头感知“有哪些系列可比”

### 方案 B：管理页拆两个独立入口：资源总览 / 开包点数

- 侧栏单独出现两个管理入口
- 每个入口各自一张表

**优点：**
- 语义最直接

**缺点：**
- 管理页侧栏继续膨胀
- 资源相关内容被分成两个入口，整体感弱

### 方案 C：管理页新增一个 `resources` 入口，内部切两个视图

- 侧栏新增单一 `resources` 入口
- 资源页内部切换：
  - `账号资源`
  - `开包点数`
- `开包点数` 视图直接把所有 `series` 展开为表头列，点击列头排序

**优点：**
- 管理页结构不继续膨胀
- 两类资源语义清晰分离
- `pack points` 交互符合用户要求
- 可以复用现有表格宏与管理页缓存/排序机制

**缺点：**
- `pack points` 视图会形成宽表
- 小屏体验主要依赖横向滚动

### 结论

采用方案 C。

## 最终设计

### 1. 管理页结构调整

管理页新增一个 `resources` 入口，位于现有侧栏中，与 `accounts/plans/tasks/...` 同级。

需要调整的文件：

- [`src/ptcgp_auto_v2/web/templates/index.html`](src/ptcgp_auto_v2/web/templates/index.html)
- [`src/ptcgp_auto_v2/web/static/js/modules/constants.js`](src/ptcgp_auto_v2/web/static/js/modules/constants.js)

具体要求：

- 侧栏增加按钮：`hx-get="/management/resources?lang={{ current_lang }}"`
- `data-hash` 新增 `resources`
- 管理页 hash 白名单同步加入 `resources`

这样可以保证：

- 刷新后仍能回到资源页
- 资源页与其他管理子页行为保持一致

### 2. 账号列表职责收敛

当前 [`src/ptcgp_auto_v2/web/templates/partials/account_list.html`](src/ptcgp_auto_v2/web/templates/partials/account_list.html) 中的 `Resources` 列移除。

调整后账号管理页只保留：

- 账号标识
- 计划信息
- 目标包
- 操作按钮

原因：

- 账号管理页应聚焦账号身份、计划、目标包配置
- 资源排序需求由独立资源页承担
- 避免账号页继续承担与资源比较相关的复杂查询与布局

### 3. 新资源页路由协议

新增路由：

- `GET /management/resources`

统一使用现有管理列表查询协议，扩展一个 `view` 参数：

- `view=stats|pack-points`
- `q`
- `sort_by`
- `sort_order`
- `page`
- `page_size`

默认值建议：

- `view=stats`
- `sort_by=id`
- `sort_order=asc`
- `page=0`
- `page_size=10`

约束：

- 不再拆出 `/management/resources/stats` 与 `/management/resources/pack-points` 两个独立路由
- 所有资源页状态都聚合到同一路由，方便缓存与恢复

### 4. 资源页模板组织

建议拆成三个 partial：

- `src/ptcgp_auto_v2/web/templates/partials/resource_list.html`
- `src/ptcgp_auto_v2/web/templates/partials/resource_stats_table.html`
- `src/ptcgp_auto_v2/web/templates/partials/resource_pack_points_table.html`

职责：

- `resource_list.html`
  - 外层自动刷新容器
  - 隐藏状态表单
  - 标题与 segmented 切换按钮
  - 承载当前视图表格
- `resource_stats_table.html`
  - 账号资源表
- `resource_pack_points_table.html`
  - 开包点数宽表

状态缓存建议：

- `data-filter-cache-key="ptcgp_filter:resources"`

状态字段至少包括：

- `view`
- `q`
- `sort_by`
- `sort_order`
- `page`
- `page_size`

### 5. `账号资源` 视图设计

`账号资源` 视图面向 `Account + AccountStat`，一行表示一个账号。

推荐列：

- `Account`
- `Exchange Points`
- `Pack Hourglass`
- `Updated At`

排序字段：

- `id`
- `nickname`
- `friend_id`
- `exchange_points`
- `pack_hourglass_count`
- `updated_at`

其中：

- `updated_at` 应优先表示资源更新时间，即 `AccountStat.updated_at`
- `NULL` 应稳定排在最后，避免未采集资源账号污染排序顶部

### 6. `开包点数` 视图设计

`开包点数` 视图面向 `Account + AccountPackPoint`，一行仍表示一个账号，但右侧展开所有 `series` 列。

列结构：

- 固定首列：`Account`
- 动态列：所有存在于 `account_pack_points.series` 中的 `series`

交互规则：

- 每个 `series` 列头直接使用 `data_table_sort_button()`
- 用户点击 `A1/A2/...` 即按该列排序
- 缺少某个 `series` 点数的账号显示 `-`

排序字段编码：

- 基础字段：`id`、`nickname`、`friend_id`
- 系列字段：`series:<series_code>`

例如：

- `series:A1`
- `series:A2`

这样做的原因：

- 明确区分账号字段排序与系列字段排序
- 避免引入额外的 `selected_series` 状态
- 模板拼接 URL 简单，服务层解析也直接

### 7. 查询层与服务层拆分

本次不复用 [`src/ptcgp_auto_v2/web/services/account_service.py`](src/ptcgp_auto_v2/web/services/account_service.py) 中的 `build_accounts_list_context()`。

新增模块：

- `src/ptcgp_auto_v2/web/queries/resource_queries.py`
- `src/ptcgp_auto_v2/web/services/resource_service.py`

#### 7.1 `账号资源` 查询

建议查询职责：

- `list_account_resources(...)`
- 基于 `Account LEFT JOIN AccountStat`
- 负责搜索、排序、分页

实现要求：

- 排序尽量在 SQL 层完成
- 搜索条件与账号页保持一致：账号 ID / nickname / friend_id / game_id
- `NULL` 资源值稳定排后

#### 7.2 `开包点数` 查询

不采用“全量 ORM + Python 排序”，也不采用“每次请求都为所有 series 生成完整动态透视 SQL”。

采用两阶段查询：

第一阶段：确定表头 `series` 列表

- 查询当前所有出现过的 `series`
- 按固定规则排序后返回模板

第二阶段：查询当前页账号数据

- 基于账号维度分页
- 若 `sort_by` 为 `series:<code>`，则仅将该 `series` 的点数 JOIN / 子查询进排序语句
- 当前页账号确定后，再批量查询这些账号的全部 `pack points`
- 组装为 `account_id -> {series -> points}` 的 map 供模板渲染

优点：

- 用户体验上表现为“所有 series 列都可排序”
- 实现上每次只让当前排序列参与 SQL 排序
- 避免动态透视 SQL 规模膨胀

### 8. 分页策略

两个资源视图都按账号分页：

- `账号资源`：按账号分页
- `开包点数`：仍按账号分页

原因：

- `pack points` 宽表已存在横向压力
- 如果再取消分页，会在纵向和横向同时膨胀
- 按账号分页更符合管理页现有列表行为

### 9. 前端交互与样式约束

资源页内部视图切换建议采用轻量 segmented 按钮，而非新建复杂嵌套路由。

要求：

- 切换 `view` 时仍走同一路由 `/management/resources`
- 通过隐藏字段写回 `view`
- 保持 `q/sort/page/page_size` 参数协议一致
- 不新增模板内联事件，继续使用 `data-action` + 现有事件委托模式

对于 `pack points` 宽表：

- 接受横向滚动
- 保持首列账号信息清晰可读
- 后续如需优化，可再加首列固定或滚动阴影提示，但不作为本次前置要求

### 10. 本地化与文案

新增资源页后，需要同步更新：

- `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- `src/ptcgp_auto_v2/web/locales/en.json`

至少新增：

- `menu_resources`
- `title_resources`
- `tab_resource_stats`
- `tab_resource_pack_points`
- 资源页空状态与列头文案

约束：

- 不直接硬编码中文/英文文本到模板
- `series` 代码本身可直接显示原值，不额外翻译

## 异常与边界处理

### 1. 账号没有 `AccountStat`

- `exchange_points` / `pack_hourglass_count` 显示 `-`
- 排序时应稳定排在后面

### 2. 账号没有某个 `series` 点数

- 宽表中显示 `-`
- 按该 `series` 排序时应稳定排在后面

### 3. 新增 `series`

- 资源页表头自动根据数据库中存在的 `series` 构建
- 不需要手工修改模板列定义

### 4. 资源页缓存恢复

- 恢复页面时必须带回 `view`
- 避免出现回到资源页后默认视图正确，但排序字段仍残留上次另一个视图的排序语义

建议：

- `view` 切换时，若当前 `sort_by` 不属于目标视图允许字段，则重置为该视图默认排序字段

## 代码去重原则

本次设计必须遵守以下收敛原则：

- 资源页查询逻辑独立收敛到 `resource_queries.py`
- 资源页上下文组装独立收敛到 `resource_service.py`
- 不在 `account_service.py` 中继续堆积资源页特判逻辑
- `stats` 与 `pack-points` 虽是两个视图，但分页、搜索、排序协议保持一致
- 表格交互继续复用现有 `data_table` / `tables` 宏，不重复发明组件

## 测试设计

建议新增以下测试：

1. 查询层测试
   - `账号资源` 排序与分页
   - `pack points` 按指定 `series` 排序
   - 缺失资源值与缺失 `series` 值时的排序行为

2. 服务层测试
   - 资源页上下文正确区分 `view`
   - `series` 列表构建正确
   - `sort_by=series:<code>` 被正确解析

3. 路由测试
   - `/management/resources` 可正常返回 partial
   - `view` 切换、分页、排序参数都能正确透传

4. 模板测试
   - `pack points` 表头能按 `series` 动态生成
   - 缺失值显示 `-`

## 验收标准

- 管理页新增 `resources` 入口并可正常恢复 hash
- `accounts` 页移除 `Resources` 列
- 新资源页可在 `账号资源 / 开包点数` 两个视图间切换
- `账号资源` 可按交换点数、开包沙漏等字段排序
- `开包点数` 可直接点击任意 `series` 列头排序
- 两个视图都按账号分页
- 查询层不再依赖全量 ORM 预加载后 Python 内存排序
- 本地化与测试同步补齐

## 实施建议

建议按以下顺序实施：

1. 先新增 `resource_queries.py` 与 `resource_service.py`
2. 再补路由与资源页 partial
3. 然后调整管理页入口与 `accounts` 页模板
4. 最后补测试与本地化
