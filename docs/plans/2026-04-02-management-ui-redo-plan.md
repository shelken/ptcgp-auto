# 管理页与拥有卡牌问题重做计划

> 本文档先记录问题、重要发现、旧实现参考、根因判断、改法和验证口径。后续发现继续直接补在这里，避免遗漏。

## 目标

把这批管理页和拥有卡牌页面的问题按旧版有效行为重新做对：
- 表单输入项补齐 `id/name`
- 计划编辑 interval 恢复为天/小时/分钟/秒，并修掉拖选输入时误触排序、无法清零
- 通知中心总记录数改为真实总数，通知内容列去掉重复图片
- 表格宽度策略重做，避免窄屏时文字被压成竖排
- 每日送卡日期回到旧版业务日逻辑，修掉首次点击日期不生效
- 拥有账号列表交换流程恢复成旧版交互
- tooltip 恢复成“只显示补充信息、不挡交互、不被边框裁掉”
- 账号列统一回到旧版表达

## 用户这次额外纠正

- `lessons.md` 只能记实际犯错，不能写成泛化规则清单。
- 这次不要子 agent，全部由主会话完成。
- 重要发现必须写文档，不等收尾再补。

## 当前已确认的重要发现

### 1. 计划编辑拖选输入会误触排序，根因已确认

- 当前 React 实现把整张任务卡都设成了 `draggable`：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/index.css`
- 这会导致在 interval 输入框里拖动选中文字时，也触发卡片拖拽排序。
- 旧版不是整卡可拖，而是只有单独拖拽手柄可拖：
  - `src/ptcgp_auto_v2/web/templates/partials/modals/edit_plan.html`（旧版）
- 结论：
  - 排序必须改成“专用拖拽手柄”或只保留上下移动按钮。
  - 不能让输入框所在整卡继续 `draggable`。

### 2. 计划编辑 interval “0 无法清零”根因已确认

- 当前 React 实现 `updateIntervalPart()` 会强制 `Math.max(1, mergeIntervalSeconds(...))`：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
- 这会让用户输入全 0 时永远被改回至少 1 秒。
- 旧版 HTMX/JS 实现允许 interval 总和为 0：
  - `src/ptcgp_auto_v2/web/templates/partials/modals/edit_plan.html`（旧版）
  - `src/ptcgp_auto_v2/web/static/js/modules/features/plan_editor.js`（旧版）
- 结论：
  - 前端编辑态必须允许四段输入为 0，并原样合成 0。
  - 是否允许后端保存 0，要继续核对接口和服务端处理；如果后端不接受，必须在提交时明确报错，不能前端偷偷改数值。

### 3. 账号列 tooltip 乱包，根因已确认

- 当前 `AccountIdentityCell` 把整块账号单元格都包进了 `Tooltip`：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management/shared.tsx`
- 这会带来两个问题：
  - 鼠标经过整块账号区域都弹 tooltip，信息密度和交互都很差。
  - 复制朋友 ID、点按钮、点文本时，hover 反馈被整块 tooltip 抢走。
- 旧版账号展示不是整块包 tooltip，而是：
  - 主账号文本直接显示
  - 朋友 ID 可复制
  - `game_id` 作为朋友 ID 的 tooltip 补充信息
  - 参考：`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`（旧版）
- 结论：
  - 账号列 tooltip 只能挂在具体补充信息节点上，不能包整块。
  - 当前 `AccountIdentityCell` 要重做，不是小修。

### 3.1 浏览器已确认账号列 tooltip 的实际错误表现

- 在当前页面 `#/management/daily-gift` 的浏览器快照里，账号单元格被读取成：
  - `#342 skn342 ... ID #342 | skn342 | 游戏 ID ...`
- 这说明当前可访问树里，整块账号格都带着 tooltip 文本，不只是局部信息。
- 这和用户要求不一致，也和旧版“只给补充信息挂 tooltip”的方式不一致。

### 4. 当前 tooltip 实现天然会被容器裁掉，根因已确认

- 当前 React tooltip 是绝对定位在触发元素内部：
  - `src/ptcgp_auto_v2/web/frontend/src/components/ui/tooltip.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/index.css`
- 这种写法只要外层有滚动容器、边框容器、裁剪上下文，就会被挡住或截断。
- 旧版已经有一套更稳的方案：
  - 悬浮层直接挂到 `body`
  - 固定定位，按视口重新定位
  - `z-index` 极高
  - 参考：
    - `src/ptcgp_auto_v2/web/static/css/components/tooltips.css`（旧版）
    - `src/ptcgp_auto_v2/web/static/js/modules/features/tooltips.js`（旧版）
- 结论：
  - 这次 tooltip 不能继续用“元素内 absolute 泡泡”。
  - 要改成 portal/fixed layer 方案，至少行为上对齐旧版。

### 5. 每日送卡日期旧版逻辑和现实现有差异，已确认

- 旧版每日送卡日期选择器特点：
  - 默认用业务日，不读旧缓存
  - 选日期后直接提交
  - “今天”按钮使用后端给的 `current_biz_date_local`
  - 参考：
    - `src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`（旧版）
    - `src/ptcgp_auto_v2/web/static/js/modules/features/daily_gift.js`（旧版）
- 当前 React 实现：
  - 初始值用 `currentGameBizDate()`，这是前端自己算的
  - 再用接口返回的 `selected_biz_date_local` 回填
  - 参考：`src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
- 这意味着当前日期来源有两套：
  - 前端本地推算
  - 后端接口回填
- 结论：
  - 日期的唯一真源要收敛。
  - 后续要重点排查“第一次点日期不生效”是不是来源切换、关闭时机、或请求参数回填打架。

### 6. 日期首次点击不生效，当前怀疑点已记录

- 当前 `DatePicker` 用 `useDismissibleLayer()` 在 `window.pointerdown` 上处理外部关闭：
  - `src/ptcgp_auto_v2/web/frontend/src/components/ui/date-picker.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/hooks/use-dismissible-layer.ts`
- 当前代码里单日点击逻辑本身很简单：`onChange(dayValue)` 后 `setOpen(false)`。
- 仅从代码静态看，问题还没完全坐实，但有几个重点嫌疑：
  - 点击关闭与值更新时序冲突
  - 面板重新渲染时 `viewMonth` / `value` 同步覆盖
  - 页面查询回填把第一次选择又刷回旧值
- 结论：
  - 这个问题不能靠猜，必须浏览器复现并记录事件链路。

### 6.1 浏览器当前已确认的日期面板结构

- 当前 `DatePicker` 弹层里 42 个日期按钮都是真按钮，点击逻辑直接挂在每个按钮上。
- 当前选中日期 `2026-04-01`，面板中 `1` 是 `is-selected`，`2` 是 `is-today`。
- 这说明至少从 DOM 结构上看，不是“根本没渲染可点日期”，问题更可能出在：
  - 事件时序
  - 状态回填覆盖
  - 选择后请求与返回值打架

### 6.2 浏览器已确认日期回跳，请求链路也抓到了

- 浏览器里直接点选 `2026-04-03` 后，按钮文字能先变成 `2026-04-03`，说明第一次点击本身是触发了的。
- 但网络里紧接着出现了这条顺序：
  - `biz_date_local=2026-04-03`
  - `biz_date_local=2026-04-01`
  - `biz_date_local=2026-04-03`
- 这说明当前不是“点击没打上去”，而是第一次点选后又被旧状态拉回去，再重新切回来。
- 可疑同步代码已经定位：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - 当前存在：
    - `if (selectedBizDateLocal && selectedBizDateLocal !== date) { setDate(selectedBizDateLocal) }`
- 根因判断已经足够明确：
  - 新查询发出去之前，页面上还保留着上一轮查询结果里的 `selected_biz_date_local=2026-04-01`
  - 这段回填逻辑把本地刚选中的 `2026-04-03` 又改回旧值
  - 所以用户体感就是“第一次没反应”或“要点第二次”

### 7. 拥有账号列表当前实现和旧版交互不一致，已确认

- 旧版行为：
  - 顶部先出现交换表单
  - 行内点击“交换卡牌”只负责选中来源账号
  - 目标朋友 ID 只在顶部统一输入一次
  - 行内朋友 ID 仅展示和复制
  - 参考：
    - `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`（旧版）
    - `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`（旧版）
- 当前 React 虽然已经改成“顶部统一输入一次”，但仍有两个明显偏差：
  - 顶部“来源账号”展示太弱，只显示昵称和 `#id`，没按旧版账号表达统一
  - 行内账号列退化成只显示昵称，没有统一账号列样式，也没带朋友 ID / game_id 规则
- 结论：
  - 不是只修表单位置，还要把整个表结构和账号表现重新对齐旧版。

### 8. 表格压缩问题的根因已经看到一半

- 当前统一表格样式：
  - `table-wrap` 只做 `overflow-x: auto`
  - `grid-table` 设成 `width: max-content; min-width: 100%`
  - 单元格统一 `min-width: 6rem`
  - 参考：`src/ptcgp_auto_v2/web/frontend/src/index.css`
- 这比“无限压扁”好一些，但还不够，因为：
  - 所有列都一刀切 `min-width: 6rem`
  - 中文长标题列、状态列、时间列、动作列、账号列的宽度需求完全不同
  - 结果是有的列还是挤，有的列又浪费
- 旧版没有用这套统一死规则，而是很多表按列职责配 `colgroup` 或单独宽度：
  - 参考：`src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`（旧版）
- 结论：
  - 需要统一表格策略，但不是“一套固定最小宽度吃所有表”。
  - 后续要设计按列类型分组的宽度策略。

### 8.1 当前页面里表格与 tooltip 的冲突已确认

- 当前页面在表格里大量使用：
  - 账号列 tooltip
  - 相对时间 tooltip
- 但 tooltip 仍然挂在单元格内部的绝对定位层上。
- 这意味着只要碰上：
  - 横向滚动容器
  - 带边框的表格外壳
  - 模态框里的局部滚动区域
  就会继续有遮挡风险。

### 9. 通知内容列“有图又有 markdown 图片”问题，旧版思路已确认

- 当前通知内容已经做了字符串层面的图片 markdown 清理，但还要继续核对两个面：
  - 通知中心抽屉
  - 通知管理表格
- 旧版通知抽屉本来就是“缩略图 + 文本摘要”分离：
  - `src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html`（旧版）
- 结论：
  - 最终目标不是“把 markdown 文本修剪得能看”，而是彻底固定成“图像列 + 文字列”的稳定结构。

## 旧实现参考清单

- 计划编辑 interval 与拖拽
  - `src/ptcgp_auto_v2/web/templates/partials/modals/edit_plan.html`
  - `src/ptcgp_auto_v2/web/static/js/modules/features/plan_editor.js`
- 每日送卡日期与业务日
  - `src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`
  - `src/ptcgp_auto_v2/web/static/js/modules/features/daily_gift.js`
- tooltip 浮层
  - `src/ptcgp_auto_v2/web/static/css/components/tooltips.css`
  - `src/ptcgp_auto_v2/web/static/js/modules/features/tooltips.js`
- 拥有卡牌弹窗交换流程
  - `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
  - `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`
- 任务列表旧 tooltip 使用点
  - `src/ptcgp_auto_v2/web/templates/partials/task_list.html`

## 待继续确认的问题

- 每日送卡“第一次点日期不生效”的精确复现链路。
- 旧版账号列在资源页、任务页、好友页、交换页的具体统一形式，是否都带朋友 ID + game_id tooltip。
- 旧版通知管理表格中账号列、时间列、状态失败原因 tooltip 的具体表现。
- interval 为 0 时，当前后端是否接受；如果不接受，要用什么报错方式。

## 准备实施的解决方案

### A. Tooltip 体系重做

- 目标：
  - tooltip 只显示补充信息
  - 不包整块复杂交互区
  - 不被表格边框、滚动容器、模态框裁掉
- 改法：
  - 把当前 `Tooltip` 改成 portal/fixed layer 方案，对齐旧版 `body` 浮层思路。
  - 触发节点只保留在：
    - 相对时间文本
    - 失败原因按钮
    - 朋友 ID 复制按钮
    - `game_id` 文本或极小补充节点
    - 截断文本
  - 禁止继续把整个账号格、整个表格单元格、整块行内操作区包进 tooltip。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/components/ui/tooltip.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/index.css`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management/shared.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management/notifications-section.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/owned-cards-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/components/notification-drawer.tsx`

### B. 账号列统一组件重做

- 目标：
  - 一列内完成展示
  - 主行只放 `#ID + 昵称`
  - 第二行放可复制朋友 ID 和 `game_id`
  - 不出现“朋友id:”文案
  - 朋友 ID 用 `1234-5678-...` 形式展示
- 改法：
  - `AccountIdentityCell` 不再包整块 tooltip。
  - `CopyableFriendId` 改成破折号分组显示。
  - `game_id` 单独作为 tooltip 或次级文本，不抢主信息。
  - 各页面账号列全部回到这套表达。
- 重点页面：
  - 任务状态
  - 每日送卡
  - 好友关系
  - 交换记录
  - 通知管理
  - 拥有卡牌弹窗

### C. 计划编辑重做

- 目标：
  - interval 仍是天/小时/分钟/秒四段输入
  - 输入框拖选数字不触发排序
  - 四段都能输入 0
  - 提交前再统一合成秒数
- 改法：
  - 去掉整卡 `draggable`。
  - 增加专用拖拽手柄，或只保留上下按钮。
  - interval 编辑态允许 0，不再前端强制 `Math.max(1, ...)`。
  - 提交时再按后端可接受格式校验。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/index.css`

### D. 每日送卡日期状态重做

- 目标：
  - 重新进入页面总是显示当天业务日
  - 第一次点击日期就稳定生效，不回跳
  - “今天”按钮和默认日期都只走业务日口径
- 改法：
  - 页面初始值只在进入时设一次。
  - 后端 `selected_biz_date_local` 只用于初始化或 hash 变更后的重置，不做持续回填。
  - 去掉会把本地新选择覆盖回旧查询值的 effect。
  - 复查最近日期按钮和弹层日期选择，共用同一套状态更新路径。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/components/ui/date-picker.tsx`
  - 如有必要：`src/ptcgp_auto_v2/web/services/daily_gift_service.py`

### E. 拥有卡牌弹窗重做

- 目标：
  - 交互回到旧版：
    - 行内按钮只负责选来源账号
    - 顶部统一显示来源账号
    - 顶部统一输入目标朋友 ID
  - 行内朋友 ID 只负责展示和复制
  - 行内账号列使用统一账号样式
- 改法：
  - 顶部来源账号显示改成统一账号块，而不是仅昵称字符串。
  - 表格第一列改成统一账号列。
  - 第二列维持朋友 ID 展示/复制，不再混入错误默认值。
  - 不可交换原因继续保留 tooltip，但只挂按钮。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/pages/owned-cards-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/styles/owned-layout.css`

### F. 通知内容列与抽屉重做

- 目标：
  - 图片只显示一次
  - 缩略图尺寸统一，别再又小又乱
  - footer 总记录数是真总数，不是当前请求条数
- 改法：
  - 通知内容先彻底去掉 markdown 图片残留，再走固定的“图 + 文”布局。
  - 缩略图保持固定画框，图片 `contain`。
  - 抽屉和通知表格共用同一套图片清理逻辑。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/components/notification-drawer.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management/notifications-section.tsx`
  - `src/ptcgp_auto_v2/web/services/notification_service.py`

### G. 表格宽度策略重做

- 目标：
  - 稍微缩窄时优先横向滚动
  - 文字正常换行，不挤成竖排
  - 不同列按职责有不同宽度策略
- 改法：
  - 保留横向滚动外壳。
  - 把账号列、动作列、时间列、状态列、长文本列分开设宽度策略，不再统一 `min-width: 6rem`。
  - 必要时给重点表补 `colgroup` 或列级 class。
- 预计涉及文件：
  - `src/ptcgp_auto_v2/web/frontend/src/index.css`
  - `src/ptcgp_auto_v2/web/frontend/src/styles/management-layout.css`
  - `src/ptcgp_auto_v2/web/frontend/src/styles/owned-layout.css`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management-page.tsx`
  - `src/ptcgp_auto_v2/web/frontend/src/pages/management/notifications-section.tsx`

### H. 表单字段 `id/name` 补齐

- 目标：
  - 浏览器不再报“表单字段元素应具有 ID 或名称”
- 改法：
  - 所有输入控件统一补齐 `id` 和 `name`
  - 包括：
    - 搜索框
    - checkbox
    - interval 四段输入
    - modal 内输入
    - 通知配置项

## 验收清单

- 计划编辑：
  - interval 显示为天/小时/分钟/秒
  - 输入框里拖选文字时不会触发排序
  - 四段全 0 可以保留为 0
- 每日送卡：
  - 刷新页面默认显示当天业务日
  - 第一次点新日期就稳定切换，不回跳
  - 最近日期按钮和弹层日期按钮行为一致
- 账号列：
  - 所有管理页都统一一列展示
  - 朋友 ID 可复制，显示为 `1234-5678-...`
  - 不出现“朋友id:”字样
- tooltip：
  - 失败原因、相对时间、朋友 ID / game_id 补充信息能正常显示
  - 不会被表格边框、滚动容器、弹窗裁掉
  - 不会整块罩住账号单元格
- 拥有卡牌弹窗：
  - 顶部先选来源账号，再统一填目标朋友 ID
  - 行内不再出现默认写死的目标朋友 ID 输入框
- 通知：
  - 总记录数显示真实总数
  - 内容列不再重复图片
  - 缩略图尺寸稳定

## 接下来的执行顺序

1. 继续浏览器复现并补全文档里的根因记录。
2. 完成这份文档的“最终改法”和“验收清单”。
3. 再开始改代码，优先顺序：
   - tooltip 体系
   - 账号列统一组件
   - 计划编辑
   - 每日送卡日期
   - 拥有卡牌弹窗
   - 通知内容列
   - 表格宽度策略
4. 改完后重新补文档里的“实际改动结果”和“验证结果”。

## 已实施改动

### 1. Tooltip 体系已重做

- React `Tooltip` 已改成挂到 `body` 的 portal 浮层。
- 定位方式改成 `fixed`，滚动和 resize 时会重新算位置。
- tooltip 不再被表格边框、滚动容器和模态框内部裁掉。
- 账号列不再整块包 tooltip，只保留局部补充信息节点：
  - `gid`
  - 相对时间
  - 截断文本
  - 错误原因等补充信息

### 2. 账号列已统一到旧版表达

- `AccountIdentityCell` 统一成两行：
  - 第一行 `#账号ID + 昵称`
  - 第二行 `朋友ID可复制 + gid提示`
- 朋友 ID 已改成每四位分组显示，如 `1234-5678-9012-3456`。
- 已去掉 `朋友id:` 这类多余文案。
- 拥有卡牌弹窗、通知页、任务页、每日送卡、好友关系、交换记录等位置都已接入这套样式。

### 3. 计划编辑已按问题重做

- 整张任务卡不再可拖。
- 现在只有拖拽手柄 `⋮⋮` 可以拖动排序。
- interval 已恢复成天/小时/分钟/秒四段输入。
- 四段输入允许直接清成 `0`，不会再被前端强行改回 `1`。
- 保存链路也已修正：
  - `0` 会真实提交给后端
  - 重新打开编辑器时，已保存的 `0` 不会再被前端偷偷改回 `3600`

### 4. 每日送卡日期逻辑已重做

- 页面进入时默认日期重新回到业务日口径。
- 去掉了会把本地新选择覆盖回旧查询结果的持续回填逻辑。
- `DatePicker` 增加 `todayValue`，每日送卡的“今天”按钮和默认日期统一走业务日。
- 当前时间点下，业务日按 14:00 重置，`2026-04-02` 上午重新进入时显示 `2026-04-01` 属于预期。

### 5. 拥有卡牌弹窗已按旧交互恢复

- 顶部只保留一个目标朋友 ID 输入框。
- 行内不再出现“每行一个目标朋友 ID 输入框”的错误结构。
- 行内按钮只负责选中来源账号。
- 顶部来源账号改成统一账号块展示，不再只是裸昵称。
- 账号表格第一列也改成统一账号列。

### 6. 通知内容列与抽屉已优化

- markdown 图片残留清理逻辑已加强。
- 通知内容列已改成“缩略图 + 文本”结构。
- 同一条通知不会再出现“左边有图，正文里还再来一张 markdown 图片”。
- 缩略图尺寸、画框和留白已统一，图片显示更稳定。
- 抽屉页脚“总记录数”已改成后端返回的真实总数，不再等于当前请求页条数。

### 7. 表格动态宽度策略已重做第一版

- `grid-table` 不再所有列一刀切。
- 现在按列职责拆了统一类：
  - `table-col-account`
  - `table-col-time`
  - `table-col-status`
  - `table-col-actions`
  - `table-col-image-text`
  - `table-col-error`
- 窄一点时优先横向滚动，不再把中文长文本硬挤成竖排。
- 任务表等重点页面已经接入列宽类。

### 8. 表单字段 `id/name` 已补齐本轮确认范围

- `SearchableSelect` 内部搜索框已补 `id/name`。
- 计划编辑四段 interval 输入已补 `id/name`。
- 每日送卡、通知配置、拥有卡牌弹窗等本轮排查到的 React 输入框都已补 `id/name`。

### 9. 用户二次指正后的补做项

- 朋友 ID 复制按钮补成了真正的点击态，不再是像普通文本一样的鼠标反馈。
- 点击复制后会弹底部 toast，明确提示“已复制”或“复制失败”。
- 计划编辑拖拽补上了整行源项反馈，不再只有手柄自己在拖。
- 拖拽开始时，拖拽预览改成整张任务卡，不再只是一个小手柄。
- 任务状态的失败原因改挂到状态 badge 的 tooltip 上，不再只放在单独错误列里。
- 拥有卡牌弹窗里“选择来源账号”的按钮文案改得更明确，同时把漏掉的本地化 key 补齐，避免英文 fallback。

## 本轮额外发现

### 1. 计划编辑的 `0` 之前只修到一半

- 前一轮虽然把前端输入改成了允许 `0`，但保存时仍然只在 `> 0` 时才提交 interval。
- 同时，重新打开编辑器时又把 `0` 当成非法值改回了 `3600`。
- 这会导致用户看到“能清零”，但保存再打开后又恢复。
- 这轮已经把保存和回显两条链路一起修掉。

### 2. 本地页面验证不要再用 `curl`

- 当前环境里 `curl http://127.0.0.1:8000` 连不上，不代表页面没启动。
- `playwright-cli` 可以正常打开本地页面并完成交互验证。
- 这轮后续页面验收统一使用浏览器实际操作，不再拿 `curl` 当页面是否可用的判断依据。

### 3. `ctx7` 当前不可用

- 这轮尝试时返回 `Invalid API key`。
- 所以这次没有继续依赖 `ctx7` 查文档。

### 4. `pre-commit` 在沙箱里会被权限拦住

- 已遇到 `.git/index.lock: Operation not permitted`。
- 这不是代码本身报错，而是当前沙箱权限限制。
- 后续提交前检查需要直接提权运行。

## 浏览器验收结果

### 1. `#/management/tasks`

- 账号列已经不是整块 tooltip。
- 可访问树读出来是 `#id + 昵称 + Copy + gid`，没有再把 tooltip 文本整块塞进去。
- 表格缩窄后优先进入横向滚动，列宽表现明显比之前稳定。

### 2. `#/management/plans`

- 任务卡本身已不再带 `draggable`。
- 可以看到独立拖拽手柄 `⋮⋮`。
- interval 四段输入能清成 `0`，不会立刻被改回 `1`。
- 页面上的间隔摘要会按 `0` 状态显示为 `-`。

### 3. `#/management/daily-gift`

- 默认业务日显示为 `2026-04-01`。
- 这是在 `2026-04-02` 上午、按 14:00 重置口径下的正确值。
- 点击快捷日期一次即可生效。
- 打开日期面板后，第一次点一个新日期就会切换并关闭，不再需要点第二次。

### 4. `#/management/notifications`

- 通知正文里已没有 markdown 图片残留。
- 抽屉页脚显示 `总记录: 830`，不是当前页条数。
- 内容列的缩略图尺寸和布局已稳定。

### 5. `#/owned-cards`

- 弹窗顶部只保留一个目标朋友 ID 输入框。
- 顶部来源账号会跟随当前选中行正确显示统一账号块。
- 行内不再有“每行一个输入框”的错误结构。
- 账号列表已使用统一账号列样式。

## 本轮代码级验证

- 前端构建通过：
  - `bun run --cwd src/ptcgp_auto_v2/web/frontend build`
- 未使用代码检查通过：
  - `bun run --cwd src/ptcgp_auto_v2/web/frontend knip`

## 剩余确认点

- 这轮已经把用户列出的主要问题全部重做完，并做了浏览器验收。
- 剩下只差提交前再跑一遍完整检查，然后提交。
