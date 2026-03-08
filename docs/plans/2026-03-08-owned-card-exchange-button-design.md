# 拥有卡牌弹窗交换按钮设计文档

## 原始需求（用户原话）

> http://192.168.6.10:8000/?lang=zh_CN#owned-cards
>
> 这个页面点开卡牌，交换卡牌操作，目前的交换卡牌按钮的地方，有哪些判断？就是出现交换卡牌按钮的规则？

## 用户澄清与约束（原话记录）

### 澄清 1：本次先做设计，不直接改代码

**用户原话：**
> 3

**上下文：**
- 选项 3 为“只先出设计，不改代码”

**结论：**
- 本轮先沉淀设计，不进入实现

### 澄清 2：设计方案采用服务层统一产出按钮状态

**用户原话：**
> 你先按方案1来

**上下文：**
- 方案 1 为“服务层统一产出禁用原因，模板只渲染”

**结论：**
- 交换按钮的可用性、禁用原因、tooltip 文案统一在 `owned_card_service` 内收敛
- 模板不再自行散落业务判断

### 澄清 3：账号展示需要按既有页面统一，不自定义新样式

**用户原话：**
> 显示规则 你参考其他地方，已经有其他地方写过了，统一。

**后续补充：**
> 不对，以账号管理那里为准

**结论：**
- 账号 id / 昵称 / 朋友id 的合并展示，以账号管理页 [`src/ptcgp_auto_v2/web/templates/partials/account_list.html`](src/ptcgp_auto_v2/web/templates/partials/account_list.html) 为唯一基线
- 不参考资源页样式，不发明第三套展示结构

### 澄清 4：新增交换点数列

**用户原话：**
> 然后账号对应的交换点数能够显示一个列。

**结论：**
- 拥有卡牌弹窗账号表格新增“交换点数”列
- 本次设计按账号资源 `account_stat.exchange_points` 展示，不使用 `account_pack_points`

### 澄清 5：关闭按钮需要避让统计信息

**用户原话：**
> 然后现在右上角的X关闭按钮也调整下，目前跟总数量重叠了

**结论：**
- 关闭按钮不能继续漂浮在 modal root 顶层
- 需要收回到右侧卡片头部的正常布局流，避免与统计信息重叠

## 目标

调整拥有卡牌弹窗中的交换账号列表与按钮交互，保证：

- 交换按钮的可用状态与禁用原因由服务层统一计算
- 不满足交换规则时，按钮仍展示但为禁用态，并在悬浮时显示原因
- 账号信息展示与账号管理页保持一致
- 表格新增账号交换点数列，方便筛查
- 关闭按钮布局修正，不再遮挡顶部统计信息

## 非目标

- 本次不直接实现基于 `account_pack_point + EXCHANGE_POINT_COSTS` 的前置点数不足禁用
- 本次不改动交换任务执行期 OCR 检测“点数不足”的现有逻辑
- 本次不修改数据库表结构
- 本次不引入新的前端组件体系或 tooltip 库

## 现状分析

### 1. 当前按钮规则分散在模板、服务层和前端 JS

当前拥有卡牌弹窗中的交换按钮由以下几处共同决定：

- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html)
  - 模板直接判断 `exchange_blocked`
  - 模板直接判断 `item.count > 0`
- [`src/ptcgp_auto_v2/web/services/owned_card_service.py`](src/ptcgp_auto_v2/web/services/owned_card_service.py)
  - 服务层为每个账号行计算 `has_active_request`
  - 服务层为整张卡计算 `exchange_blocked`
- [`src/ptcgp_auto_v2/web/static/js/modules/features/exchange_cards.js`](src/ptcgp_auto_v2/web/static/js/modules/features/exchange_cards.js)
  - 点击按钮后，如果账号有活跃请求，则展示警告并禁用提交按钮

问题：

- 规则来源分散，不利于继续扩展
- 模板承担了业务判断，后续再加规则会继续膨胀
- 现有“活跃请求”是在点击后才禁用提交，交互太晚

### 2. 当前账号展示不符合“复合字段统一”要求

当前交换账号表格将以下信息拆成三列：

- 账号 id
- 朋友id
- 昵称

这与 Web 规范中“复合字段合并展示原则”不一致，也与账号管理页现有展示基线不一致。

账号管理页的现有基线位于：

- [`src/ptcgp_auto_v2/web/templates/partials/account_list.html`](src/ptcgp_auto_v2/web/templates/partials/account_list.html)

该页面已经定义了统一的账号展示方式：

- 昵称主展示
- 账号 ID 次级展示
- 朋友id 独立块展示，并支持复制交互

因此拥有卡牌弹窗不应再维持独立的三列拆分结构。

### 3. 当前表格缺少账号交换点数信息

当前交换账号表格只展示：

- 账号身份信息
- 当前持有数量
- 操作按钮

但没有展示账号现有交换点数，导致人工判断账号是否具备交换条件时信息不足。

项目中已有账号级交换点数字段：

- [`src/ptcgp_auto_v2/db/models/account_stat.py`](src/ptcgp_auto_v2/db/models/account_stat.py)
  - `exchange_points`
- [`src/ptcgp_auto_v2/db/models/account.py`](src/ptcgp_auto_v2/db/models/account.py)
  - `Account.exchange_points` 属性

因此表格可以直接扩展一列，而不必引入额外模型改造。

### 4. 当前关闭按钮采用顶层浮动布局，容易压住统计信息

当前关闭按钮位于：

- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html)

按钮作为 modal root 顶层元素独立浮动，而右侧卡片头部又在顶部展示：

- 标题
- 总账号数
- 总持有数

这导致在当前布局下，关闭按钮与统计信息存在重叠风险。

## 方案选择

### 方案 A：服务层统一产出动作状态，模板只渲染

- 在 `owned_card_service` 中为每个账号行生成统一的 `exchange_action`
- 模板根据 `exchange_action` 决定按钮是否禁用、是否显示 tooltip
- JS 仅保留展开表单等行为，不再主导业务规则

**优点：**

- 规则单点维护
- 后续扩展“点数不足”“系列不匹配”时只需要改服务层
- 模板职责纯粹，结构更稳定

**缺点：**

- 需要调整上下文字段结构
- 需要补充服务层与模板测试

### 方案 B：继续在模板里追加判断

- 维持现有 `if/elif` 模板结构
- 继续把更多条件塞到 Jinja 模板

**优点：**

- 改动表面上最小

**缺点：**

- 规则继续发散
- 后续维护成本更高
- 模板可读性会持续下降

### 结论

采用方案 A。

## 最终设计

### 1. 服务层统一产出 `exchange_action`

在 [`src/ptcgp_auto_v2/web/services/owned_card_service.py`](src/ptcgp_auto_v2/web/services/owned_card_service.py) 中新增统一的账号行动状态构造函数，例如：

- `_build_exchange_action(card, item)`

每个账号行最终返回的数据结构中新增：

```python
{
    "account_id": 123,
    "friend_id": "1234567890123456",
    "nickname": "示例账号",
    "count": 2,
    "exchange_points": 15000,
    "has_active_request": True,
    "exchange_action": {
        "enabled": False,
        "reason_key": "has_active_request",
        "reason_text": "该账号有进行中的交换请求",
        "button_text": "交换卡牌",
        "tooltip": "该账号有进行中的交换请求，暂不可发起新的交换"
    }
}
```

模板后续只能消费 `exchange_action`，不再自行拼装业务判断。

### 2. 按钮判定规则统一为一条优先级链

按钮可用性统一在服务层按顺序命中第一条规则后返回，不在模板拼接多个原因。

推荐优先级：

1. 卡牌稀有度不可交换
   - 条件：`card.rarity in ExchangeCardService.NON_EXCHANGEABLE_RARITIES`
   - 文案：`该卡牌稀有度不可交换`

2. 当前账号没有可交换的此卡
   - 条件：`item.count <= 0`
   - 文案：`该账号没有可交换的此卡`

3. 当前账号已有进行中的交换请求
   - 条件：`item.has_active_request is True`
   - 文案：`该账号已有进行中的交换请求`

4. 默认可交换
   - 条件：前述规则均未命中
   - 结果：`enabled=True`

说明：

- 禁用按钮仍保留文案“交换卡牌”
- 禁用原因通过 `reason_text / tooltip` 暴露给模板
- 当前不在此处加入基于 `account_pack_point` 的点数不足前置拦截

### 3. 模板只负责渲染按钮状态，不再承担业务判断

调整文件：

- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html)

模板职责调整为：

- 如果 `item.exchange_action.enabled` 为真，渲染正常按钮
- 如果为假，渲染 `disabled` 按钮
- 禁用按钮设置 `title=item.exchange_action.tooltip`
- 不再直接使用 `exchange_blocked`
- 不再直接判断 `item.count > 0`

tooltip 交互策略：

- 第一版直接使用原生 `title`
- 不引入新的前端 tooltip 组件
- 若后续需要移动端更明显的提示，再单独扩展图标或说明文本

### 4. 账号展示以账号管理页为唯一基线

调整文件：

- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html)

账号列不再拆成：

- 账号 id
- 朋友id
- 昵称

而是合并为一个账号复合列，展示方式以账号管理页 [`src/ptcgp_auto_v2/web/templates/partials/account_list.html`](src/ptcgp_auto_v2/web/templates/partials/account_list.html) 为准：

- 使用 `account-identity-cell`
- 昵称作为主显示
- `账号ID: #xxx` 作为次级信息
- 朋友id 使用账号管理页现有的独立可复制展示结构
- 没有朋友id 时沿用账号管理页的兜底方式显示 `-`

这样可以保证：

- 页面风格统一
- 用户不需要重新学习另一套账号展示模式
- 表格列数收缩，为新增“交换点数”列腾出空间

### 5. 新增“交换点数”列

调整文件：

- [`src/ptcgp_auto_v2/db/repositories/account_card_repository.py`](src/ptcgp_auto_v2/db/repositories/account_card_repository.py)
- [`src/ptcgp_auto_v2/web/services/owned_card_service.py`](src/ptcgp_auto_v2/web/services/owned_card_service.py)
- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html)

数据来源：

- `account_stat.exchange_points`

设计要求：

- 仓储层在查询账号拥有该卡信息时，同时把账号级交换点数带出
- 服务层透传到页面上下文
- 模板新增独立列显示数值
- 空值统一显示 `-`

说明：

- 这里显示的是“账号交换点数”，不是系列级 `account_pack_points`
- 系列级点数若后续需要参与按钮前置禁用，应作为另一条规则扩展，不与本列混用

### 6. 关闭按钮收回到右侧卡片头部布局流

调整文件：

- [`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`](src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html)

头部布局调整为：

- 第一行：左侧标题，右侧关闭按钮
- 第二行：总账号数与总持有数

也就是从当前“关闭按钮脱离卡片头部单独浮动”的方式，改为：

- 关闭按钮属于右侧卡片 header 的正常元素
- 统计信息与关闭按钮不再占用同一视觉层

这样可以彻底避免：

- `X` 与统计信息重叠
- 依赖额外 `padding-right` 做硬规避

### 7. JS 只保留表单交互，不再承担主要业务限制

调整文件：

- [`src/ptcgp_auto_v2/web/static/js/modules/features/exchange_cards.js`](src/ptcgp_auto_v2/web/static/js/modules/features/exchange_cards.js)

调整原则：

- 可点击按钮才会触发表单展开
- 由于禁用态按钮已在列表阶段前置拦截，`has_active_request` 不再作为“点击后才禁用提交”的主路径
- 现有提交按钮禁用/警告逻辑可保留为兜底，但不再是主要交互入口

### 8. 后端兜底规则仍然保留

即使页面已经禁用按钮，后端仍必须保留最终兜底，避免被绕过。

兜底层次：

1. Web 服务层可选做同源复判，便于后续返回更明确的失败原因
2. 核心服务层 [`src/ptcgp_auto_v2/services/exchange_card_service.py`](src/ptcgp_auto_v2/services/exchange_card_service.py) 保持硬规则校验

当前已存在的核心硬规则：

- `IM / UR` 不可交换
- 同一发起账号存在活跃请求时不可重复创建

说明：

- 页面禁用只是前置体验优化，不替代后端校验

## 点数不足规则的后续扩展位

当前不实现“基于 `account_pack_point + EXCHANGE_POINT_COSTS` 的前置禁用”，原因是：

- 现有 Web 创建链路没有稳定的“卡牌 -> series”统一映射入口
- 如果没有明确系列映射，直接比较点数会形成假精确判断

未来若要补，应继续放在服务层同一个 `_build_exchange_action()` 规则链里，新增类似：

5. 当前账号对应系列包点数不足
   - 条件：`series_pack_points < EXCHANGE_POINT_COSTS[card.rarity]`
   - 前提：先补齐稳定的卡牌所属系列解析逻辑

同时，核心服务层也应补同源兜底，避免只靠前端禁用。

## 测试设计

### 1. 服务层测试

补充或调整：

- [`src/ptcgp_auto_v2/web/tests/services/test_owned_card_service_exchange_table.py`](src/ptcgp_auto_v2/web/tests/services/test_owned_card_service_exchange_table.py)

需要覆盖：

- 稀有度不可交换时返回禁用按钮与正确原因
- `count <= 0` 时返回禁用按钮与正确原因
- `has_active_request=True` 时返回禁用按钮与正确原因
- 正常可交换时返回启用按钮
- 多个条件同时命中时优先级正确
- `exchange_points` 字段正确进入上下文

### 2. 模板测试

验证：

- 启用态按钮正常渲染
- 禁用态按钮带 `disabled`
- 禁用态按钮带 `title`
- 账号复合列结构与账号管理页基线一致
- “交换点数”列正常显示

### 3. 路由/服务创建请求测试

验证：

- 页面禁用并不替代后端兜底
- 非法请求创建仍会被服务层/核心层拦截
- 返回消息能区分创建成功与创建失败

## 文档与实现约束

- 实现时必须同步更新相关测试
- 不得在模板和 JS 中重新散落业务规则
- 若后续引入“点数不足前置禁用”，必须先明确卡牌对应系列的稳定映射来源
- 若实现中调整了拥有卡牌弹窗结构，应同步检查相关说明文档与 `web/AGENTS.md` 是否需要更新
