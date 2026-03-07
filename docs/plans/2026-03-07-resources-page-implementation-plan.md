# Resources Page Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a dedicated management resources page that separates account-level resources from per-series pack points and supports direct table-header sorting for both views.

**Architecture:** Add a new `/management/resources` route with a dedicated query/service pair instead of reusing account list assembly. The page keeps one management sidebar entry and switches between `stats` and `pack-points` views using shared list parameters and dynamic table headers for pack-point series columns.

**Tech Stack:** FastAPI, SQLModel, Jinja2 partial templates, HTMX, existing management page filter cache helpers.

---

## 关联设计文档

- `docs/plans/2026-03-07-resources-page-design.md`

## 实施策略

- 严格按视图拆分：`stats` 与 `pack-points` 查询/模板分离
- 先写查询与服务层测试，再实现最小代码
- 不复用 `build_accounts_list_context()` 做资源页特判
- 不修改数据库表结构

### Task 1: 资源页查询层

**Files:**
- Create: `src/ptcgp_auto_v2/web/queries/resource_queries.py`
- Modify: `src/ptcgp_auto_v2/web/queries/__init__.py`
- Test: `src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py`

**Step 1: Write the failing tests**

在 `src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py` 新增至少以下测试：

```python
def test_list_account_resources_sort_by_exchange_points_desc(session):
    rows, total = list_account_resources(
        session=session,
        q="",
        sort_by="exchange_points",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert total == 3
    assert [row["account_id"] for row in rows] == [2, 1, 3]


def test_list_pack_point_resources_sort_by_series_desc(session):
    payload = list_pack_point_resources(
        session=session,
        q="",
        sort_by="series:A1",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert payload["series_list"] == ["A1", "A2"]
    assert [row["account_id"] for row in payload["rows"]] == [2, 1, 3]
    assert payload["rows"][0]["series_points"]["A1"] == 120
```

补充边界测试：

- 缺失 `AccountStat` 时排序稳定
- 缺失某个 `series` 时按该列排序排在后面
- 搜索 `q` 能命中 nickname / friend_id / game_id

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py -v`

Expected: FAIL because `resource_queries.py` or target functions do not exist yet.

**Step 3: Write minimal implementation**

在 `src/ptcgp_auto_v2/web/queries/resource_queries.py` 实现：

- `list_account_resources(...)`
- `list_pack_point_resources(...)`
- 内部辅助：
  - 搜索条件构建
  - `stats` 排序字段白名单
  - `pack-points` 的 `sort_by=series:<code>` 解析

关键实现要求：

- `list_account_resources(...)`
  - 使用 `Account LEFT JOIN AccountStat`
  - 返回 `(rows, total)`
  - 排序字段支持：`id/nickname/friend_id/exchange_points/pack_hourglass_count/updated_at`
- `list_pack_point_resources(...)`
  - 先查 `series_list`
  - 当前排序列若为 `series:<code>`，只让该 `series` 参与 SQL 排序
  - 当前页账号确定后，批量查这些账号全部 `pack_points`
  - 返回：

```python
{
    "rows": rows,
    "total": total,
    "series_list": series_list,
}
```

- `rows` 中每项至少包含：

```python
{
    "account_id": 1,
    "nickname": "foo",
    "friend_id": "1234",
    "game_id": "bar",
    "series_points": {"A1": 100, "A2": 80},
}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/queries/resource_queries.py src/ptcgp_auto_v2/web/queries/__init__.py src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py
git commit -m "feat: add resource page queries"
```

### Task 2: 资源页服务层

**Files:**
- Create: `src/ptcgp_auto_v2/web/services/resource_service.py`
- Test: `src/ptcgp_auto_v2/web/tests/services/test_resource_service.py`

**Step 1: Write the failing tests**

在 `src/ptcgp_auto_v2/web/tests/services/test_resource_service.py` 新增：

```python
def test_build_resources_context_defaults_to_stats(monkeypatch, session):
    context = build_resources_context(
        session=session,
        view="stats",
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    assert context["view"] == "stats"
    assert "items" in context


def test_build_resources_context_pack_points_resets_invalid_sort(monkeypatch, session):
    context = build_resources_context(
        session=session,
        view="pack-points",
        q="",
        sort_by="exchange_points",
        sort_order="desc",
        page=0,
        page_size=10,
    )
    assert context["view"] == "pack-points"
    assert context["sort_by"] == "id"
```

补充测试：

- `stats` 视图透传总数、分页状态
- `pack-points` 视图透传 `series_list`
- 非法 `view` 回退到 `stats`

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/services/test_resource_service.py -v`

Expected: FAIL because service module does not exist yet.

**Step 3: Write minimal implementation**

在 `src/ptcgp_auto_v2/web/services/resource_service.py` 实现 `build_resources_context(...)`：

- 校验 `view` 只允许 `stats/pack-points`
- 统一标准化：`page/page_size/sort_order`
- `stats` 视图调用 `list_account_resources(...)`
- `pack-points` 视图调用 `list_pack_point_resources(...)`
- 当视图切换时，如果 `sort_by` 不属于目标视图允许字段，则回退到默认排序字段

上下文至少包含：

```python
{
    "view": "stats",
    "items": items,
    "series_list": [],
    "q": q,
    "sort_by": normalized_sort_by,
    "sort_order": normalized_sort_order,
    "page": page,
    "page_size": page_size,
    "has_prev": has_prev,
    "has_next": has_next,
    "total": total,
}
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/services/test_resource_service.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/services/resource_service.py src/ptcgp_auto_v2/web/tests/services/test_resource_service.py
git commit -m "feat: add resource page service"
```

### Task 3: 资源页路由与管理页入口

**Files:**
- Create: `src/ptcgp_auto_v2/web/routers/resources.py`
- Modify: `src/ptcgp_auto_v2/web/app.py`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/constants.js`
- Modify: `src/ptcgp_auto_v2/web/templates/index.html`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py`

**Step 1: Write the failing tests**

在 `src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py` 新增：

```python
def test_get_management_resources_returns_partial(client):
    response = client.get("/management/resources?lang=zh_CN")
    assert response.status_code == 200
    assert "RESOURCES" in response.text or "资源" in response.text


def test_get_management_resources_pack_points_view(client):
    response = client.get(
        "/management/resources?lang=zh_CN&view=pack-points&sort_by=series:A1&sort_order=desc"
    )
    assert response.status_code == 200
```

同时检查管理页 hash 白名单与侧栏入口是否已挂载。

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py -v`

Expected: FAIL because route is not registered.

**Step 3: Write minimal implementation**

实现：

- `src/ptcgp_auto_v2/web/routers/resources.py`
  - 新增 `GET /management/resources`
  - 依赖注入 `Session`
  - 调用 `build_resources_context(...)`
  - 渲染 `partials/resource_list.html`
- `src/ptcgp_auto_v2/web/app.py`
  - 导入并挂载 `resources.router`
- `src/ptcgp_auto_v2/web/static/js/modules/constants.js`
  - `MANAGEMENT_HASH_WHITELIST` 新增 `resources`
- `src/ptcgp_auto_v2/web/templates/index.html`
  - 新增侧栏按钮
  - `hx-get="/management/resources?lang={{ current_lang }}"`
  - `data-hash="resources"`

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/routers/resources.py src/ptcgp_auto_v2/web/app.py src/ptcgp_auto_v2/web/static/js/modules/constants.js src/ptcgp_auto_v2/web/templates/index.html src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py
git commit -m "feat: add management resources route"
```

### Task 4: 资源页模板

**Files:**
- Create: `src/ptcgp_auto_v2/web/templates/partials/resource_list.html`
- Create: `src/ptcgp_auto_v2/web/templates/partials/resource_stats_table.html`
- Create: `src/ptcgp_auto_v2/web/templates/partials/resource_pack_points_table.html`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/account_list.html`

**Step 1: Write the failing test**

如果当前没有模板测试基础，先新增最小渲染测试，至少覆盖：

- `pack-points` 表头能根据 `series_list` 输出 `A1/A2`
- 账号页不再包含 `Resources` 列

示例：

```python
def test_account_list_no_longer_renders_resources_column(render_template):
    html = render_template("partials/account_list.html", context)
    assert "Resources" not in html


def test_resource_pack_points_table_renders_dynamic_series_headers(render_template):
    html = render_template("partials/resource_pack_points_table.html", context)
    assert "A1" in html
    assert "A2" in html
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests -k "resource or account_list" -v`

Expected: FAIL because templates do not exist or old account template still contains resources column.

**Step 3: Write minimal implementation**

实现要点：

- `resource_list.html`
  - 使用 `auto_refresh_container`
  - 增加隐藏状态表单 `ptcgp_filter:resources`
  - 增加内部视图切换控件 `view=stats|pack-points`
  - 根据 `view` include 对应表格 partial
- `resource_stats_table.html`
  - 使用现有 `data_table` 宏
  - 支持 `exchange_points/pack_hourglass_count/updated_at` 排序
- `resource_pack_points_table.html`
  - 固定账号列
  - 循环 `series_list` 生成表头排序按钮
  - 行内按 `series_points.get(series)` 显示值或 `-`
- `account_list.html`
  - 移除 `Resources` 列与对应 cell

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests -k "resource or account_list" -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/templates/partials/resource_list.html src/ptcgp_auto_v2/web/templates/partials/resource_stats_table.html src/ptcgp_auto_v2/web/templates/partials/resource_pack_points_table.html src/ptcgp_auto_v2/web/templates/partials/account_list.html
git commit -m "feat: add resources page templates"
```

### Task 5: 资源页本地化与状态细节

**Files:**
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py`

**Step 1: Write the failing test**

补充测试验证资源页使用新增 i18n key：

```python
def test_resources_menu_label_localized(client):
    response = client.get("/?lang=zh_CN")
    assert "资源" in response.text
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py -v`

Expected: FAIL because localization keys are missing.

**Step 3: Write minimal implementation**

在两个 locale 文件新增至少以下 key：

- `menu_resources`
- `title_resources`
- `tab_resource_stats`
- `tab_resource_pack_points`
- `empty_resource_rows`
- `empty_pack_point_rows`

必要时补充：

- `col_resource_updated_at`
- `label_resource_view`

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py
git commit -m "feat: localize resources page"
```

### Task 6: 回归验证

**Files:**
- Verify: `src/ptcgp_auto_v2/web/queries/resource_queries.py`
- Verify: `src/ptcgp_auto_v2/web/services/resource_service.py`
- Verify: `src/ptcgp_auto_v2/web/routers/resources.py`
- Verify: `src/ptcgp_auto_v2/web/templates/partials/resource_list.html`

**Step 1: Run focused tests**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/queries/test_resource_queries.py src/ptcgp_auto_v2/web/tests/services/test_resource_service.py src/ptcgp_auto_v2/web/tests/routers/test_resources_router.py -v`

Expected: PASS.

**Step 2: Run related account template tests**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests -k "account_list or resource" -v`

Expected: PASS.

**Step 3: Manual verification**

Run: `PYTHONPATH=src python -m ptcgp_auto_v2.web.app`

Verify manually:

- 管理页侧栏出现 `resources`
- `accounts` 页已无资源列
- 资源页默认进入 `stats`
- 切到 `pack-points` 后可直接点击 `A1/A2/...` 排序
- 资源页刷新后仍能恢复 `resources` hash

**Step 4: Commit**

```bash
git add src/ptcgp_auto_v2/web
git commit -m "test: verify resources page flow"
```
