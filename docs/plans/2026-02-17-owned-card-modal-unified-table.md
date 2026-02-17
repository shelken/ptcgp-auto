# Owned Card Modal Unified Table Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 owned-card modal 的滚动/穿透与交互问题，并建设统一表格组件，逐步收敛管理类列表页面到统一能力。

**Architecture:** 前端采用 `data_table` 宏抽象 toolbar/sort/pager/infinite 四类能力，页面按模式选择 `pager`（modal）或 `infinite`（页面流）。后端统一列表查询参数（`page/page_size/q/sort_by/sort_order`）并在服务层做白名单校验。owned-card modal 先行改造为固定高度 + 顶部交换操作区 + 传统分页，之后迁移 management 下表格类页面。

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

## Task 4: 抽取统一表格宏并接入第一批 management 页面

**Files:**
- Create: `src/ptcgp_auto_v2/web/templates/partials/macros/data_table.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/exchange_card_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/friendship_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/task_list.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/daily_gift_list.html`

**Steps:**
1. 提供统一 toolbar（搜索/刷新）与排序头宏。
2. 提供 pager/infinite 两种分页宏。
3. 将上述页面逐个迁移到统一宏，保持现有字段与业务行为不变。

## Task 5: 文案、规则、回归

**Files:**
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Modify: `src/ptcgp_auto_v2/web/AGENTS.md`

**Steps:**
1. 统一“创建请求”相关文案为“交换卡牌”。
2. 回填 AGENTS：统一列表组件规范、modal 禁止双滚动规范。
3. 运行：`PYTHONPATH=src pytest tests -v`。
