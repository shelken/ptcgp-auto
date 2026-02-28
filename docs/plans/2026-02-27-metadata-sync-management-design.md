# 元数据同步管理页重构 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将元数据管理页升级为“检查 -> 预览 -> 确认执行”的同步控制台，支持 all/set/pack/card 范围、supplement/force（仅覆盖不删除）模式，并覆盖本地+flibustier+52poke 全链路检查与缓存复用。

**Architecture:** 采用“共享领域服务 + Web 编排层”模式：把 `sync_metadata.py` 的核心同步能力抽离为可复用服务，Web 仅负责参数解析、快照驱动和界面呈现。执行必须基于预览快照，确保“先看清楚再写库”。52poke 引入分层缓存（入口链接、系列->子包、子包文本、本地化映射）并支持强制刷新。

**Tech Stack:** FastAPI, SQLModel/SQLite(localtime), HTMX, ES Modules, Jinja2, pytest.

---

### Task 1: 建立同步域模型与快照持久化基础

**Files:**
- Create: `src/ptcgp_auto_v2/db/models/metadata_sync_snapshot.py`
- Modify: `src/ptcgp_auto_v2/db/models/__init__.py`
- Create: `src/ptcgp_auto_v2/db/repositories/metadata_sync_snapshot_repository.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/__init__.py`
- Test: `src/ptcgp_auto_v2/tests/db/test_metadata_sync_snapshot_repository.py`

**Step 1: 写失败测试（仓储 CRUD 与 TTL）**
- 覆盖：创建快照、读取快照、标记已执行、过期过滤。
- 关键断言：时间字段使用本地时间语义，状态流转正确（`previewed -> executed/expired`）。

**Step 2: 运行失败测试确认红灯**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/db/test_metadata_sync_snapshot_repository.py -v`
- Expected: FAIL（模型/仓储未实现）。

**Step 3: 最小实现模型与仓储**
- 模型字段建议：`snapshot_id`, `scope_level`, `scope_value`, `source`, `mode`, `payload_json`, `summary_json`, `status`, `expires_at`, `created_at`, `updated_at`。
- 仓储接口：`create_snapshot/get_snapshot/mark_executed/mark_expired/list_recent_snapshots`。

**Step 4: 复跑测试确认绿灯**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/db/models/metadata_sync_snapshot.py src/ptcgp_auto_v2/db/models/__init__.py src/ptcgp_auto_v2/db/repositories/metadata_sync_snapshot_repository.py src/ptcgp_auto_v2/db/repositories/__init__.py src/ptcgp_auto_v2/tests/db/test_metadata_sync_snapshot_repository.py
git commit -m "feat(metadata): add sync snapshot persistence"
```

---

### Task 2: 抽离 flibustier 同步核心为共享服务（复用现有脚本逻辑）

**Files:**
- Create: `src/ptcgp_auto_v2/services/metadata_sync/flibustier_sync_service.py`
- Modify: `src/ptcgp_auto_v2/scripts/sync_metadata.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_flibustier_sync_service.py`

**Step 1: 写失败测试（preview/execute 两阶段）**
- 覆盖：all 与 set 范围下的 preview 统计；execute 按 payload 写入。
- 覆盖模式：`supplement` 与 `force`（force=仅覆盖不删除）。

**Step 2: 跑测试确认失败**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_flibustier_sync_service.py -v`
- Expected: FAIL

**Step 3: 最小实现服务**
- 从 `src/ptcgp_auto_v2/scripts/sync_metadata.py` 提炼：远端拉取、diff、payload 构建、执行写库。
- 保持脚本仍可调用该服务，不重复实现。
- 明确禁删策略：不生成删除动作。

**Step 4: 回归脚本路径**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_flibustier_sync_service.py -v`
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/services/metadata_sync/flibustier_sync_service.py src/ptcgp_auto_v2/scripts/sync_metadata.py src/ptcgp_auto_v2/tests/services/test_flibustier_sync_service.py
git commit -m "refactor(metadata): extract flibustier sync service"
```

---

### Task 3: 实现 52poke 本地化抓取与多级缓存服务

**Files:**
- Create: `src/ptcgp_auto_v2/services/metadata_sync/poke52_localization_service.py`
- Create: `src/ptcgp_auto_v2/services/metadata_sync/cache_store.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_poke52_localization_service.py`

**Step 1: 写失败测试（链路与缓存命中）**
- 覆盖：entry links、A/B 系列页解析、pack 页解析、card 名称提取、title 归一化回查。
- 覆盖缓存：同请求二次调用不重复抓取；`force_refresh=True` 会绕过缓存。

**Step 2: 跑测试确认失败**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_poke52_localization_service.py -v`
- Expected: FAIL

**Step 3: 最小实现**
- 缓存键层级：
  - `entry_links`
  - `series_packs:{series_title}`
  - `pack_wikitext:{pack_title}`
  - `localized_map:{set_code}`
- TTL 默认 6~24h（计划落 12h，可配置）。
- 输出统一本地化映射：`set.zh`, `pack.zh`, `card.localized_name.zh`。

**Step 4: 复跑测试**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/services/metadata_sync/poke52_localization_service.py src/ptcgp_auto_v2/services/metadata_sync/cache_store.py src/ptcgp_auto_v2/tests/services/test_poke52_localization_service.py
git commit -m "feat(metadata): add 52poke localization with cache"
```

---

### Task 4: 实现统一编排服务（检查/预览/执行）

**Files:**
- Create: `src/ptcgp_auto_v2/web/services/metadata_sync_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Test: `src/ptcgp_auto_v2/web/tests/services/test_metadata_sync_service.py`

**Step 1: 写失败测试（核心契约）**
- 覆盖 `check_sources()`: 本地+flibustier+52poke 健康与统计差异。
- 覆盖 `preview_sync(request)`: 返回快照 ID、汇总、分组、字段 diff。
- 覆盖 `execute_sync(snapshot_id)`: 仅接受未过期快照，执行后更新状态。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/services/test_metadata_sync_service.py -v`
- Expected: FAIL

**Step 3: 最小实现**
- 编排 flibustier/52poke 服务结果，统一成 UI 视图模型。
- 强制模式固定语义：覆盖字段，不删除本地缺失项。
- 预览与执行解耦：execute 不重新算 diff，仅消费快照 payload。

**Step 4: 复跑测试**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/web/services/metadata_sync_service.py src/ptcgp_auto_v2/web/services/metadata_service.py src/ptcgp_auto_v2/web/tests/services/test_metadata_sync_service.py
git commit -m "feat(web): orchestrate metadata check preview execute flow"
```

---

### Task 5: 路由升级为同步控制台 API

**Files:**
- Modify: `src/ptcgp_auto_v2/web/routers/metadata.py`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_metadata.py`
- Create: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py`

**Step 1: 写失败测试（新 API）**
- GET `/management/metadata` 返回控制台模板上下文。
- POST `/api/metadata/sync/check`
- POST `/api/metadata/sync/preview`
- POST `/api/metadata/sync/execute`
- 参数校验：scope/source/mode、快照过期、非法组合。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_metadata.py src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py -v`
- Expected: FAIL

**Step 3: 最小实现路由**
- 保留旧 label 编辑 API（兼容）但标记为次级入口。
- 新 API 统一返回 partial HTML 或 JSON（按 HTMX 场景决定，优先 HTML 片段 + HX-Trigger）。

**Step 4: 复跑测试**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/web/routers/metadata.py src/ptcgp_auto_v2/web/tests/routers/test_metadata.py src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py
git commit -m "feat(web): add metadata sync check preview execute routes"
```

---

### Task 6: 重做 metadata 页面 UI（同步控制台）

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js`
- Test: `src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py`

**Step 1: 写失败测试（模板关键结构）**
- 断言必须存在：健康卡、配置区、预览区、执行区、快照标识、tabs、下钻容器。
- 断言无内联事件，使用 `data-action`。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py -v`
- Expected: FAIL

**Step 3: 最小实现模板与文案**
- 采用你确认的页面结构（三栏桌面 + 三步移动端）。
- 预览区先汇总后下钻；执行区二次确认。
- 新增 i18n key 覆盖所有新文案。

**Step 4: 接入前端动作分发**
- `action_handlers.js` 增加 metadata 专属动作（生成预览、切 tab、展开分组、触发执行）。
- 保持事件委托规范，不新增内联 JS。

**Step 5: 复跑模板测试**
- Run: 同 Step 2
- Expected: PASS

**Step 6: Commit**
```bash
git add src/ptcgp_auto_v2/web/templates/partials/metadata_list.html src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py
git commit -m "feat(web): redesign metadata page as sync console"
```

---

### Task 7: 端到端验证与回归

**Files:**
- Modify: `src/ptcgp_auto_v2/web/AGENTS.md`
- Optional Test Add: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py`

**Step 1: 写失败测试（端到端最小流）**
- 流程：check -> preview -> execute（mock 远端）。
- 覆盖：snapshot 必填、过期失败、execute 后不可重复执行。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py -v`
- Expected: FAIL

**Step 3: 完整回归测试**
- Run:
  - `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_metadata.py -v`
  - `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests -v`
- Expected: metadata 与 web 相关测试全绿。

**Step 4: 更新经验文档**
- 在 `src/ptcgp_auto_v2/web/AGENTS.md` 回填本次新增注意点（快照执行、防重复提交、缓存命中展示、force 语义固定）。

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/web/AGENTS.md src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py
git commit -m "test(web): cover metadata sync e2e flow and update playbook"
```

---

### Task 8: 文档与落地校验

**Files:**
- Modify: `docs/plans/2026-02-27-metadata-sync-management.md`
- Optional Create: `docs/plans/2026-02-27-metadata-sync-management-design.md`
- Optional Modify: `README.md`（若页面功能对外说明有变化）

**Step 1: 文档更新**
- 记录最终 API 契约、快照结构、缓存策略、force 语义（仅覆盖不删除）。

**Step 2: 最终命令校验**
- Run:
  - `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests -v`
  - `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_flibustier_sync_service.py src/ptcgp_auto_v2/tests/services/test_poke52_localization_service.py -v`

**Step 3: Commit**
```bash
git add docs/plans/2026-02-27-metadata-sync-management.md docs/plans/2026-02-27-metadata-sync-management-design.md README.md
git commit -m "docs(metadata): document sync console design and contracts"
```

---

### Task 9: 左侧导航改为“层次中心”交互（系列 -> 卡包 -> 卡牌）

> 背景问题：当前左侧以参数表单为主（来源/范围/模式并列），不符合“用户先选对象层次，再触发动作”的使用方式。

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/event_bindings.js`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Test: `src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py`

**Step 1: 写失败测试（层次结构）**
- 断言左侧必须存在层次树：系列节点 -> 卡包节点 -> 卡牌节点。
- 断言不再出现“平铺筛选项主导”的参数布局（来源/范围/系列/卡包/卡牌并列输入）。
- 断言节点操作通过 `data-action` 触发，不使用内联事件。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py -v`
- Expected: FAIL

**Step 3: 最小实现（层次中心）**
- 左侧改为资源树（Tree）：
  - 一级：系列（set）
  - 二级：该系列下卡包（pack）
  - 三级：该卡包下卡牌（card）
- 右侧动作面板随“当前选中节点”动态变化：
  - 选中系列：显示系列级动作
  - 选中卡包：显示卡包级动作
  - 选中卡牌：显示卡牌级动作
  - 选中根节点：显示全量动作

**Step 4: 复跑测试**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/web/templates/partials/metadata_list.html src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js src/ptcgp_auto_v2/web/static/js/modules/event_bindings.js src/ptcgp_auto_v2/web/services/metadata_service.py src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py
git commit -m "feat(web): switch metadata sidebar to hierarchy-first tree"
```

---

### Task 10: 动作语义融入层次节点（去参数化）

> 目标：用户不再先选“来源/范围”等参数，而是先选层次节点，再选择动作，系统自动推导执行范围与来源。

**Files:**
- Modify: `src/ptcgp_auto_v2/web/routers/metadata.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_sync_service.py`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py`

**Step 1: 写失败测试（动作驱动）**
- 覆盖“节点 + 动作”协议，例如：
  - `node_type=set,node_id=A1,action=sync_structure`
  - `node_type=pack,node_id=PackX,action=sync_localization`
  - `node_type=card,node_id=A1-001,action=force_repair`
- 断言后端可从动作协议自动推导 source/scope/mode。

**Step 2: 运行失败测试**
- Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py -v`
- Expected: FAIL

**Step 3: 最小实现（动作映射）**
- 新增动作映射表：`action -> (source, mode, scope_level)`。
- 执行范围由节点推导，不再依赖平铺筛选参数。
- 保持强制模式语义不变：仅覆盖，不删除。

**Step 4: 复跑测试**
- Run: 同 Step 2
- Expected: PASS

**Step 5: Commit**
```bash
git add src/ptcgp_auto_v2/web/routers/metadata.py src/ptcgp_auto_v2/web/services/metadata_service.py src/ptcgp_auto_v2/web/services/metadata_sync_service.py src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py
git commit -m "refactor(web): drive metadata sync by hierarchy node actions"
```

---

### Task 11: UI 先行改造（按 Step 2 三步流程逐屏交付）

> 约束：先把页面交互做到可用，再做后端整合；每完成一步必须清理未使用旧代码，禁止遗留无关逻辑。

**Files:**
- Modify: `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/event_bindings.js`
- Test: `src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py`

**Step 1: 交付“选择对象”页（Step 1/3）并清理旧参数区**
- 页面仅保留对象选择（系列/卡包/卡牌层次），不出现旧参数平铺表单。
- 清理未使用的范围归一化代码和旧参数输入控件。

**Step 2: 交付“预览变更”页（Step 2/3）并清理旧预览块**
- 页面聚焦动作选择 + 差异汇总 + 明细，不混入执行表单。
- 删除与旧布局绑定但已无入口的预览结构与文案。

**Step 3: 交付“确认执行”页（Step 3/3）并清理旧执行区**
- 页面聚焦快照摘要、二次确认、执行日志。
- 清理旧执行区残留字段和重复按钮逻辑。

**Step 4: 每步验证与用户验收循环**
- 每完成一步跑模板/路由/web 测试。
- 提交页面给用户验收；用户确认“页面没问题”后再进入后端整合阶段。

**Step 5: Commit（按步骤小提交）**
```bash
git add src/ptcgp_auto_v2/web/templates/partials/metadata_list.html src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json src/ptcgp_auto_v2/web/static/js/modules/action_handlers.js src/ptcgp_auto_v2/web/static/js/modules/event_bindings.js src/ptcgp_auto_v2/web/tests/templates/test_metadata_console_template.py
git commit -m "feat(web): deliver metadata ui step-by-step with dead-code cleanup"
```

---

### Task 12: UI 验收后再整合服务与路由

> 前置条件：用户明确确认“页面没问题”。

**Files:**
- Modify: `src/ptcgp_auto_v2/web/routers/metadata.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_service.py`
- Modify: `src/ptcgp_auto_v2/web/services/metadata_sync_service.py`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_api.py`
- Test: `src/ptcgp_auto_v2/web/tests/routers/test_metadata_sync_flow.py`

**Step 1:** 对齐 Step 1/2/3 页面协议与接口参数。
**Step 2:** 清理所有已失效的旧参数分支代码。
**Step 3:** 跑全量回归并更新文档。

---

### 问题回填（持续维护）

> 规则：后续每出现一个新问题，必须先写入此节（抽象为可复用注意点），再提交对应代码变更。

#### [2026-02-28] 问题1：自动刷新导致元数据页面状态重置

- **现象**：自动刷新后，`ui_step` 与当前选中节点（set/pack/card）被重置。
- **根因**：`auto_refresh_container` 未包含状态表单，刷新请求丢失选择上下文。
- **修复策略**：
  - 新增隐藏状态表单 `#metadata-state-form`，持久化 `ui_step/selected_node_type/selected_node_id/selected_set_code/selected_pack_name`。
  - `auto_refresh_container` 的 include selector 固定为 `#metadata-state-form`。
  - `check/preview/execute/node-select` 四类请求统一透传 `ui_step` 与节点状态。

#### [2026-02-28] 问题2：节点名称未按当前语言展示

- **现象**：中文界面下，系列/卡包/卡牌仍大量显示英文名称。
- **根因**：模板直接渲染模型 `name` 字段，未走语言优先级解析。
- **修复策略**：
  - 服务层统一计算 `display_name`（当前语言优先 -> 回退 en/原始值）。
  - 系列/卡包使用 `label_data` 多语言键解析；卡牌使用 `data.localized_name` 解析。
  - 模板只消费 `display_name`，禁止继续直渲染原始 `name`。

#### [2026-02-28] 问题3：自动刷新 URL 参数覆盖与目标替换不稳定

- **现象**：状态表单已挂载后，自动刷新仍会出现步骤/节点回退。
- **根因**：
  - 自动刷新 URL 组装直接拼接 `?`，未保留原 URL 查询参数且键值可能重复。
  - 宏未支持显式 `data-refresh-target`，替换边界不稳定。
- **修复策略**：
  - `auto_refresh.js` 统一使用 `URL + URLSearchParams.set` 构建刷新地址，保留 `lang` 并覆盖同名键。
  - metadata 状态表单增加 `lang/ui_step/selected_node_type/selected_node_id/selected_set_code/selected_pack_name`，自动刷新仅依赖 `#metadata-state-form`。

#### [2026-02-28] 问题4：脚本与服务逻辑漂移（违背统一实现要求）

- **现象**：`sync_metadata.py` 仍保留独立预览/构建/执行中间层实现，与 `FlibustierSyncService` 并行存在。
- **根因**：历史脚本逻辑未及时删除，只做了“远端抓取”局部复用。
- **修复策略**：
  - 脚本仅保留入口编排，完整复用 `FlibustierSyncService.fetch_remote_metadata/build_plan/execute_plan`。
  - 删除脚本内与服务重复的中间模型和构建执行逻辑，避免双维护。

#### [2026-02-28] 问题5：中文界面下语言键解析被 normalize 覆盖

- **现象**：测试环境/部分请求路径下，输入 `zh_CN` 最终语言键落成 `en`，导致展示回退英文。
- **根因**：先 `normalize_lang` 后再算 `lang_key`，在测试 i18n 未初始化场景会回退 `en`。
- **修复策略**：
  - `build_metadata_context` 先用原始请求 `lang` 计算 `requested_lang_key`，仅在非中文请求时再走 normalize 后语言键。
  - 展示层统一消费 `display_name`，避免模板直渲染英文原始名。

#### [2026-02-28] 问题6：自动刷新未透传当前动作（current_action）

- **现象**：自动刷新后节点不变，但动作会回退到默认值，导致预览/执行行为偏移。
- **根因**：状态表单仅透传 step/node/set/pack，未包含动作状态。
- **修复策略**：
  - 状态表单补充 `current_action`；
  - 所有 metadata 相关接口（check/preview/execute/node-select）统一透传并回写 `current_action`；
  - 模板中 `action` 由 `current_action` 统一驱动。

#### [2026-02-28] 问题7：要求“先实现后统一补测”执行约束

- **现象**：用户明确要求停止新增测试，先完成功能与清理。
- **根因**：执行节奏与用户指令冲突。
- **修复策略**：
  - 即刻停止新增测试代码；
  - 后续变更先完成功能与清理，再在统一收尾阶段集中测试。

#### [2026-02-28] 问题8：进入元数据管理页即触发远端请求

- **现象**：仅点击“元数据管理”就触发 flibustier/52poke 请求。
- **根因**：`build_metadata_context` 默认调用远端检查聚合，页面初载即执行网络请求。
- **修复策略**：
  - 页面初载只使用本地默认检查上下文（零远端请求）；
  - 仅在用户主动点击“重新检查数据源”或执行预览动作时触发远端请求。

#### [2026-02-28] 问题9：远端 API 请求缺少缓存与显式刷新控制

- **现象**：用户多次操作同一对象时，仍重复请求远端接口。
- **根因**：Web metadata 服务未统一复用远端缓存，flibustier/52poke 请求按调用即发。
- **修复策略**：
  - 在 `metadata_service` 引入进程内共享 TTL 缓存，统一传入 `FlibustierSyncService` 与 `Poke52LocalizationService`。
  - `preview` 接口仅在用户显式触发时请求远端；并通过 `force_refresh` 控制是否绕过缓存。
  - UI 提供“强制刷新并生成预览”按钮，默认走缓存，明确由用户决定刷新时机。

#### [2026-02-28] 问题10：metadata 页不应启用被动自动刷新

- **现象**：即使已加状态透传，自动刷新仍会在不合适时机触发请求，导致用户感知为“条件被清”或“无意义请求”。
- **根因**：metadata 页面场景是“强交互编排页”，不属于被动刷新列表；沿用 `data-auto-refresh` 机制会与三步流程状态机冲突。
- **修复策略**：
  - metadata 页面禁用被动自动刷新（不再注入 `data-auto-refresh`）；
  - 仅保留用户主动触发：节点选择、检查、预览、执行。

#### [2026-02-28] 问题11：筛选缓存架构分叉导致复杂度失控

- **现象**：不同页面存在多套缓存实现（records/owned/tasks 私有 key + metadata 私有模块），维护和排障成本高。
- **根因**：筛选缓存没有单一入口，页面级模块重复实现保存/恢复/侧栏参数拼装逻辑。
- **修复策略**：
  - 统一只保留 `features/filters/shared_form.js` 作为筛选缓存唯一入口；
  - 所有页面筛选表单统一通过 `data-filter-cache-key` 接入；
  - 删除旧缓存 key 与私有缓存模块（含 `metadata_state.js`），不做兼容分支。

#### [2026-02-28] 问题12：metadata 页面选择条件浏览器刷新后丢失

- **现象**：在 metadata 页面选择系列/卡包/卡牌后，浏览器刷新，选择状态丢失，回退到初始状态。
- **根因**：
  1. `initCacheRestoreToUrl()` 在 `restoreTab()` 之前执行，此时 metadata 表单 `#metadata-state-form` 还不存在于 DOM 中，导致缓存恢复失败。
  2. `htmx:afterSwap` 事件中使用 `evt.detail.target`（旧内容）而非 `evt.detail.elt`（新内容）保存缓存，导致动态加载的表单无法正确保存。
  3. HTMX 请求前没有将表单数据同步到状态表单并保存缓存。
- **修复策略**：
  1. **调整初始化顺序**：在 `bootstrap.js` 中将 `initCacheRestoreToUrl()` 移到 `restoreTab()` 之后执行，确保 metadata 表单已加载。
  2. **修复 afterSwap 目标**：在 `event_bindings.js` 中使用 `evt.detail.elt || evt.detail.target` 获取新加载的内容。
  3. **请求前保存缓存**：在 `htmx:beforeRequest` 中检测 metadata 相关请求，将表单数据同步到 `#metadata-state-form` 并调用 `saveFilterCache()`。
  4. **增强恢复函数**：`shared_form.js` 的 `initCacheRestoreToUrl()` 支持 `data-restore-url` 和 `data-restore-check-params` 属性，自动检查 URL 参数并恢复。
- **关键代码变更**：
  - `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`：调整初始化顺序
  - `src/ptcgp_auto_v2/web/static/js/modules/event_bindings.js`：修复 afterSwap 目标，添加 beforeRequest 保存逻辑
  - `src/ptcgp_auto_v2/web/static/js/modules/features/filters/shared_form.js`：增强 `initCacheRestoreToUrl()` 函数
  - `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html`：表单添加 `data-restore-*` 属性

---

## 里程碑验收标准（DoD）

- 有新控制台页面，覆盖 check/preview/execute 三阶段。
- scope 支持 all/set/pack/card，mode 支持 supplement/force（force 不删除）。
- 预览默认“先汇总后下钻”，可见字段级 diff。
- execute 必须依赖快照，且具备过期/重复执行保护。
- 52poke 链路缓存可命中，可强制刷新。
- Web 与服务测试通过，`web/AGENTS.md` 已回填经验点。
- 左侧导航以层次树为中心（系列 -> 卡包 -> 卡牌），不再由平铺参数驱动。
- 同步动作由“当前节点 + 动作类型”自动推导执行参数，用户无需手工拼装范围条件。
- UI 交付采用 Step 1/2/3 分步验收，且每一步都完成死代码清理后再进入下一步。

---

## 待办回填（合并版，一字不漏）

### A. Metadata 设计计划（12 项）状态总表

- 已完成：**9** 项（Task 1,2,3,4,5,7,9,10,12）
- 部分完成：**3** 项（Task 6,8,11）
- 未完成：**0** 项

| 任务 | 状态 | 偏离说明 |
|---|---|---|
| Task 1 | ✅ 已完成 | 快照模型/仓储/状态流已落地。 |
| Task 2 | ✅ 已完成 | flibustier 同步逻辑已抽到共享服务并被脚本复用。 |
| Task 3 | ✅ 已完成 | 52poke 本地化抓取 + TTL 缓存实现完成。 |
| Task 4 | ✅ 已完成 | `check/preview/execute` 编排服务已实现。 |
| Task 5 | ✅ 已完成 | metadata 路由 API 已升级并接服务。 |
| Task 6 | ⚠️ 部分完成 | Step2/Step3 仍有收尾项，预览/执行展示闭环未完全验收。 |
| Task 7 | ✅ 已完成 | e2e 流程测试存在（check→preview→execute）。 |
| Task 8 | ⚠️ 部分完成 | 最终落地文档未补齐（仅 design 文档）。 |
| Task 9 | ✅ 已完成 | 层级中心（系列→卡包→卡牌）已实现。 |
| Task 10 | ✅ 已完成 | `node_type+action -> source/mode/scope` 已映射。 |
| Task 11 | ⚠️ 部分完成 | Step1/2/3 分屏有了，但 2/3 业务区仍待收尾。 |
| Task 12 | ✅ 已完成 | UI/服务/路由已完成主链整合。 |

#### 当前部分完成项证据

- Task 6：⚠️ 部分完成
  - 证据：
    - `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html:219`
    - `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html:247`

- Task 8：⚠️ 部分完成
  - 证据：
    - 当前仅存在 `docs/plans/2026-02-27-metadata-sync-management-design.md`

- Task 11：⚠️ 部分完成
  - 证据：
    - `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html:219`
    - `src/ptcgp_auto_v2/web/templates/partials/metadata_list.html:247`

### B. Web 统一规范计划（完整待办）

#### 核心偏离检查项

| 检查项 | 状态 | 证据 | 偏离说明 |
|---|---|---|---|
| Service 命名统一 `build_` | ⚠️ | `src/ptcgp_auto_v2/web/services/pack_config_service.py:7-58` | 仍有 `list_`/`save_` 风格函数。 |
| 列表 context 协议统一 | ⚠️ | `src/ptcgp_auto_v2/web/services/record_service.py:15-106` | 无数据时返回 `{"stop": True}`，非统一协议。 |
| Router 全部用 `render_template()` | ❌ | `src/ptcgp_auto_v2/web/routers/metadata.py:21-210` | 手写 `get_templates()+TemplateResponse`。 |
| Router 不直接操作 Repository | ❌ | `src/ptcgp_auto_v2/web/routers/tasks.py:41-52,243-313` | Router 直接 `AccountRepository()`。 |
| Service 不返回 `t/current_lang` | ❌ | `src/ptcgp_auto_v2/web/services/metadata_service.py:47-106` | 直接返回 `t/current_lang`。 |
| 模板统一使用 `items` | ❌ | `src/ptcgp_auto_v2/web/templates/partials/task_list.html:15-315` | 仍使用 `tasks/has_more/accounts/t/current_lang`。 |

#### Top 10 偏离（完整）

1. `src/ptcgp_auto_v2/web/routers/tasks.py` 直接调用 `AccountRepository`（Router 越界）
2. `src/ptcgp_auto_v2/web/routers/metadata.py` 未使用 `render_template`
3. `src/ptcgp_auto_v2/web/services/metadata_service.py` 返回 `t/current_lang`
4. `src/ptcgp_auto_v2/web/templates/partials/task_list.html` 依赖 `tasks/has_more/...` 非统一字段
5. `src/ptcgp_auto_v2/web/services/record_service.py` 无数据返回 `{"stop": True}`
6. `src/ptcgp_auto_v2/web/routers/records.py` 依赖 `stop` 并直接返回空串
7. `src/ptcgp_auto_v2/web/services/pack_config_service.py` 命名仍 `list_`/`save_`
8. `src/ptcgp_auto_v2/web/services/notification_service.py` i18n 上下文耦合重
9. `src/ptcgp_auto_v2/web/routers/tasks.py` Router 侧仍拼 `has_more/next_page_url`
10. `src/ptcgp_auto_v2/web/services/record_service.py` 空数据分支分页字段不完整

### 合并收敛执行待办（按优先级）

#### Phase 1（先消灭协议分叉）
1. 统一所有列表 service 返回协议：`items/page/page_size/has_prev/has_next/total`
2. 删除 `stop` 协议，空结果改为统一字段表达
3. Router 不再自行拼 `has_more/next_page_url`

#### Phase 2（清边界）
1. 把 `tasks.py` 里的 `AccountRepository` 下沉 service
2. `metadata.py` 全量替换为 `render_template()`
3. Service 层移除 `t/current_lang` 返回，统一由模板上下文注入

#### Phase 3（模板字段统一）
1. `task_list.html` 等模板改为 `items` 驱动
2. 分页只依赖 `has_prev/has_next/page/page_size/total`
3. 移除对 `tasks/has_more/stop` 等旧字段依赖

#### Phase 4（Metadata 收尾）
1. 完成 Step2 预览差异区（摘要+明细）
2. 完成 Step3 执行确认与日志展示，接 `snapshot_id`
3. 去掉执行按钮默认禁用逻辑，改为条件启用

#### Phase 5（文档闭环）
1. 补齐 metadata 最终落地文档（非 design 草案）
2. 同步 README / AGENTS.md 的结构与约束说明

### 合并验收清单（待办）

- [ ] A 组 Task 6/8/11 全部转为 ✅
- [ ] 所有列表 service 返回协议统一
- [ ] Router 0 处直接 Repository 调用
- [ ] Router 100% 走 `render_template()`
- [ ] Service 0 处返回 `t/current_lang`
- [ ] 模板 0 处使用 `tasks/has_more/stop` 等旧字段
- [ ] 文档与代码一致，无“设计已改/文档未改”偏差
