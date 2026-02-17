# Owned Card Modal Unified Table Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 owned-card modal 的滚动/穿透与交互问题，并建设“能力统一、布局可差异”的表格组件体系，逐步收敛管理类列表页面到统一协议与交互。

**Architecture:** 前端采用 `data_table` 宏作为“能力组件”，统一提供 `toolbar/table/pager` 骨架与行为，不强制页面采用同一排版。页面通过 slot 与声明式筛选配置（`priority/span/min_width`）定义自身筛选组合与顺序，并按容器宽度自动换行。后端统一列表查询参数（`page/page_size/q/sort_by/sort_order`）并在服务层做白名单校验；视觉层允许按页面密度与场景差异化。

**Tech Stack:** FastAPI, Jinja2 macros, HTMX, SQLModel, ES modules

---

## 用户原始诉求（原文保留）

1. owned-card modal 在长列表时滚动难用，列表会在标题上方穿透，出现透明 gap。
2. “创建请求”交互不合理，应改成“交换卡牌”，且输入朋友id不应在列表最底部。
3. modal 内列表需要支持分页请求、排序、简单搜索、刷新。
4. 不希望 modal 内继续长列表滚动，应固定容量并支持传统翻页。
5. 后续整合所有地方的列表页面，融合进统一组件。

## Task 1: 先补测试（TDD 红灯）

**Files:**
- Create: `tests/test_owned_card_modal_exchange_table.py`
- Modify: `tests/conftest.py`（仅在需要 fixture 扩展时）

**Steps:**
1. 新增测试：`build_owned_card_modal_context` 返回的交换列表支持 `q` 搜索。
2. 新增测试：支持排序白名单（如 `count desc`、`account_id asc`）。
3. 新增测试：支持固定 `page_size` 的分页切片与总数。
4. 运行：`PYTHONPATH=src pytest tests/test_owned_card_modal_exchange_table.py -v`，确认失败（功能尚未实现）。

## Task 2: 实现 owned-card modal 交换账号查询能力

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/account_card_repository.py`
- Modify: `src/ptcgp_auto_v2/web/services/owned_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/routers/owned_cards.py`

**Steps:**
1. Repository 增加 `get_owned_card_accounts_page(...)`，返回 `items/total/has_prev/has_next`。
2. Service 增加 `build_owned_card_exchange_accounts_context(...)`，做排序白名单和参数规范化。
3. Router 新增 `GET /api/owned-cards/modal/exchange-accounts`，返回仅表格 partial。
4. 运行 Task 1 测试，确认绿灯。

## Task 3: 重构 owned-card modal UI（修复滚动与表单位置）

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
- Create: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_exchange_accounts_table.html`
- Modify: `src/ptcgp_auto_v2/web/static/css/components/modal.css`
- Modify: `src/ptcgp_auto_v2/web/static/css/components/owned-cards.css`

**Steps:**
1. 把交换表单上移到列表上方并默认可见，按钮文案改为“交换卡牌”。
2. 列表改为 HTMX partial，支持搜索、排序、刷新、上一页/下一页。
3. modal 采用“单滚动策略”：避免 header sticky + 负边距造成穿透。
4. 人工验证：长列表下标题不穿透，表单无需滚到底。

## Task 4: 重构 data_table 为可插槽能力组件，并按页面差异化接入 management

**Files:**
- Create: `src/ptcgp_auto_v2/web/templates/partials/macros/data_table.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/exchange_card_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/friendship_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/task_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/account_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/plan_list.html`

**Steps:**
1. 将 `data_table` 改为可插槽能力组件，最少抽象 `toolbar/table/pager`，保证组件只负责骨架与交互，不强绑页面布局。
2. 为筛选行引入声明式布局配置（如 `priority/span/min_width`），页面可自行定义筛选项顺序和组合，组件负责按容器宽度自动换行。
3. 尺寸策略改为响应式 token（`clamp()` + 容器类 `compact/regular` + 密度模式 `dense/normal`），避免固定像素。
4. 统一范围限定为“协议与交互”（`q/sort_by/sort_order/page/page_size` + 排序/分页/刷新/透传），视觉布局允许页面差异化。
5. 按顺序迁移并验证：`exchange -> friendship -> daily_gift -> tasks`；每迁一页做 DevTools 对比，确保“布局可差异，交互统一”。
6. 管理类页面排序交互统一使用“表头点击排序 + 隐藏字段透传”，禁止将排序降级为筛选区下拉框。

## Task 5: 文案、规则、回归

**Files:**
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Modify: `src/ptcgp_auto_v2/web/AGENTS.md`

**Steps:**
1. 统一“创建请求”相关文案为“交换卡牌”。
2. 回填 AGENTS：统一列表组件规范、modal 禁止双滚动规范。
3. 运行：`PYTHONPATH=src pytest tests -v`。

---

## 进度记录

- [x] Task 1：完成（`web/tests` 新增并通过 owned-card exchange 表格测试）
- [x] Task 2：完成（新增 `/api/owned-cards/modal/exchange-accounts` 与服务层分页/搜索/排序）
- [x] Task 3：完成（owned-card modal 去标题、固定模式、表单上移并默认隐藏、传统翻页）
- [x] Task 5：完成（文案与 `web/AGENTS.md` 规则回填）
- [x] Task 4：完成（`data_table` 已重构为可插槽能力组件并落地响应式 token；`exchange/friendship/daily_gift/tasks/account_list/plan_list` 全部迁移到统一交互协议与分页能力，页面布局保持可差异化）

## 修正记录（2026-02-17）

- 发现 `account_list` 与 `plan_list` 在迁移时把排序交互误改为筛选区下拉，偏离了 `tasks` 页面“表头点击排序”交互基线。
- 修正策略：统一回退为表头点击排序（含升降序切换），并继续使用 `sort_by/sort_order` 隐藏字段透传协议。
- 修正结果：`account_list` 与 `plan_list` 已改回表头排序交互；`PYTHONPATH=.:src pytest src/ptcgp_auto_v2/web/tests -v` 通过（7 passed）。
- 工具栏重构：`data_table` 新增双区声明式工具栏布局（left/right + order + min_width + grow），并已接入 `account/plan/exchange/friendship/daily_gift/tasks`，支持长内容自动换行。
