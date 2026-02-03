# 拥有卡牌列表页设计稿

日期：2026-02-03

## 用户原始诉求（原文）

现在需要增加账号当前拥有的卡牌列表，类似抽卡记录页面，展示的是对应的卡牌卡面。
我们这个卡牌列表叫作拥有的卡牌，即当前页面展示所有的账号的卡牌，但是不是按照账号分组，而是每张卡独一无二，但是能够显示对应关联哪几个账号拥有。
首先是视图上面，能够调整每行展示的卡牌列数，目前先按照每行5个（桌面web端）能够调整5个以上，5-9个。能够动态变化宽度。
卡牌默认按照rarity稀有度从高到底、然后是set_code的顺序排列。
筛选项有 稀有度、类型、还有 set_code(card_sets) 还有 子包选项（packs)
能量属性（element）
目前怎么展示卡牌关联账号我没想好，你可以提下建议。
然后这个列表页tab放在抽卡记录左边，管理中心右边。

## 目标与范围

- 新增“拥有卡牌”列表页（Tab），展示全量去重后的卡牌列表，并可查看关联账号。
- 支持筛选：稀有度、类型、set_code、子包、能量属性。
- 默认排序：稀有度降序 → set_code → number 升序。
- 列数可调（5-9），滑杆控制并记忆。
- 卡牌详情弹窗：左侧卡面，右侧账号列表（id、friend_id、昵称、数量），含统计行。

## 架构与组件

### 页面结构

- 在 `web/templates/index.html` 中新增 Tab：`owned-cards`，位置为“抽卡记录”左侧、“管理中心”右侧。
- 主内容容器：`tab-content-owned-cards`，内部使用 HTMX 加载 `partials/owned_card_list.html`。

### 后端路由

- `GET /api/owned-cards`：返回拥有卡牌列表（分页 + 无限滚动）。
- `GET /api/owned-cards/modal`：返回卡牌详情弹窗内容。

### 模板新增

- `templates/partials/owned_card_list.html`
- `templates/partials/modals/owned_card_detail.html`

### 样式

- 新增 `.owned-grid`，使用 CSS 变量 `--owned-grid-cols` 控制列数。
- 不硬编码颜色，沿用 `main.css` 主题变量与工具类。

## 数据与排序

### 数据来源

- 以 `account_cards` 关联表为基础，联表 `cards`、`card_sets`、`packs`、`card_packs`。
- 列表页聚合到 `card_id` 粒度，返回卡牌基础字段与“拥有账号数量”。
- 详情弹窗按 `card_id` 查询关联账号及数量。

### 图片规则

- 不使用 `image_url` 字段。
- 复用抽卡记录页的图片拼接规则：
  - `image_locale`：`zh-TW`（中文）或 `en-US`（英文）
  - `image_base_url`：`https://wsrv.nl/?url=raw.githubusercontent.com/shelken/ptcgp-assets/main/images/{locale}/cards-by-set`
  - `image_cdn_url`：`https://cdn.jsdelivr.net/gh/shelken/ptcgp-assets@main/images/{locale}/cards-by-set`
- 列表使用 `image_base_url`，详情使用 `image_cdn_url`。

### 排序规则

- 稀有度排序映射（同记录页）：C/U/R/RR/AR/SR/SAR/UR/IM/S/SSR。
- 次序：稀有度降序 → set_code → number 升序。

## 筛选与交互

- 筛选表单采用 HTMX：`hx-get` 触发 `/api/owned-cards`，`hx-target` 指向列表容器。
- 筛选项：稀有度、类型、set_code、子包、能量属性。
- set_code 与子包展示使用 `label_data` 本地化，元素/类型/稀有度走 `locales/*.json`。
- 列数滑杆（5-9）实时调整 `--owned-grid-cols` 并存入 `localStorage`。

## 弹窗详情

- 点击卡面触发 `/api/owned-cards/modal?card_id=...`。
- 左侧：卡面图（与列表一致的拼接规则）。
- 右侧：账号列表表格（id / friend_id / 昵称 / 数量）。
- 统计行：
  - 账号数量合计
  - 总拥有数量（count 求和）

## 分页与加载

- 采用无限滚动（HTMX `revealed`），后端返回 `next_page_url`。
- 每页固定条数（可配置），列表只回必要字段，详情再查全量账号。

## 异常与空态

- 列表无数据：显示本地化空态提示。
- 详情无数据：返回 404 文案并关闭按钮。
- 图片无法加载：保持空态占位，不使用 card_back 兜底图。

## 测试建议

- 后端查询测试：筛选、排序、分页。
- 模板渲染测试：空态、正常态、modal 内容字段完整性。

## 变更清单（预估）

- `src/ptcgp_auto_v2/web/app.py`：新增 owned-cards 路由与查询。
- `src/ptcgp_auto_v2/web/templates/index.html`：新增 Tab 与容器。
- `src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html`：列表模板。
- `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`：详情模板。
- `src/ptcgp_auto_v2/web/static/css/main.css`：新增网格样式与滑杆样式。
- `src/ptcgp_auto_v2/web/static/js/main.js`：列数滑杆逻辑与 localStorage。
- `src/ptcgp_auto_v2/web/locales/en.json`、`src/ptcgp_auto_v2/web/locales/zh_CN.json`：新增文案。
