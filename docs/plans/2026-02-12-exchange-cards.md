# Exchange Cards Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现“交换卡牌（exchange_cards）”从 Web 发起、任务执行、到管理端追踪/取消/完成的完整闭环。

**Architecture:** 以 `ExchangeCardRequest` 作为唯一业务真相，`exchange_cards` 任务只消费请求并推进状态；调度层负责“何时执行”，任务层负责“如何执行”。采用“业务失败只写 request，task_instance 收敛为完成态”的策略，避免被调度器重置造成循环重跑。

**Tech Stack:** FastAPI + HTMX + Jinja2 + SQLModel + Task Scheduler + OCR/模板识别 + locales (`zh_Hant` + web locales)

---

> 用户原始诉求（原文保留）：
>
> @docs/needs/11-交换卡牌.md
>
> 准备完成这个需求，写计划

### Task 1: 数据模型与仓储（请求状态机）

**Files:**
- Create: `src/ptcgp_auto_v2/db/models/exchange_card_request.py`
- Create: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`
- Modify: `src/ptcgp_auto_v2/db/models/__init__.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/__init__.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py`

**Step 1: Write the failing test**

```python
def test_one_account_only_one_active_exchange_request():
    """同一账号在非 completed/failed/canceled 状态下只能有一条活跃请求。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: FAIL（模型/仓储尚未实现）

**Step 3: Write minimal implementation**

```python
class ExchangeCardRequest(SQLModel, table=True):
    """交换卡牌请求记录。"""
    __tablename__ = "exchange_card_requests"
    id: Optional[int] = Field(default=None, primary_key=True)
    from_account_id: int = Field(index=True)
    to_account_id: Optional[int] = Field(default=None, index=True)
    to_friend_id: str = Field(index=True)
    target_card_id: int = Field(index=True)
    target_card_rarity: str
    status: str = Field(default="sending", index=True)
    failed_reason: Optional[str] = None
    cancel_reason: Optional[str] = None
    next_check_at: Optional[datetime] = None
    expire_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/db/models/exchange_card_request.py src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py src/ptcgp_auto_v2/db/models/__init__.py src/ptcgp_auto_v2/db/repositories/__init__.py src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py
git commit -m "feat: add exchange card request persistence"
```

### Task 2: 交换服务层（规则收敛点）

**Files:**
- Create: `src/ptcgp_auto_v2/services/exchange_card_service.py`
- Modify: `src/ptcgp_auto_v2/services/__init__.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py`

**Step 1: Write the failing test**

```python
def test_create_request_rejects_im_and_ur_rarity():
    """IM/UR 稀有度在服务层必须被拒绝。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: FAIL（服务未实现）

**Step 3: Write minimal implementation**

```python
class ExchangeCardService:
    """交换卡牌业务服务。"""

    EXCHANGE_POINT_COSTS = {
        "C": 0, "U": 0, "R": 1200, "RR": 5000,
        "AR": 4000, "SR": 25000, "SAR": 25000,
        "S": 10000, "SSR": 30000,
    }
    NON_EXCHANGEABLE_RARITIES = {"IM", "UR"}

    @classmethod
    def create_request(cls, ...):
        ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/services/exchange_card_service.py src/ptcgp_auto_v2/services/__init__.py src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py
git commit -m "feat: add exchange card domain service"
```

### Task 3: 调度“延时复查”机制（不改 Hook 基类）

**Files:**
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`
- Modify: `src/ptcgp_auto_v2/db/repositories/task_instance_repository.py`
- Test: `src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py`

**Step 1: Write the failing test**

```python
def test_scheduler_only_wakes_due_exchange_requests():
    """仅唤醒 next_check_at <= now 的请求对应账号。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py -v`
Expected: FAIL（唤醒逻辑未实现）

**Step 3: Write minimal implementation**

```python
def _wake_due_exchange_cards_tasks(self):
    """唤醒到期的 exchange_cards 请求。"""
    ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/core/scheduler.py src/ptcgp_auto_v2/db/repositories/task_instance_repository.py src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py
git commit -m "feat: wake due exchange tasks by request time"
```

### Task 4: 新任务 `exchange_cards`（sending/sended 双阶段）

**Files:**
- Create: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/__init__.py`
- Modify: `src/ptcgp_auto_v2/locales/zh_Hant.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py`

**Step 1: Write the failing test**

```python
def test_exchange_cards_sending_success_marks_sended():
    """sending 阶段送出成功后标记 sended。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: FAIL（任务未实现）

**Step 3: Write minimal implementation**

```python
@TaskRegistry.register("exchange_cards")
class ExchangeCardsTask(Task):
    """交换卡牌任务：处理 sending/sended 请求。"""
    task_type = "exchange_cards"
    reset_type = ResetType.ONCE
    ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/exchange_cards.py src/ptcgp_auto_v2/tasks/__init__.py src/ptcgp_auto_v2/locales/zh_Hant.py src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py
git commit -m "feat: add exchange cards task workflow"
```

### Task 5: Web 端“拥有卡牌”弹窗改造与发起入口

**Files:**
- Modify: `src/ptcgp_auto_v2/web/routers/owned_cards.py`
- Modify: `src/ptcgp_auto_v2/web/services/owned_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`

**Step 1: Write the failing test**

```python
def test_owned_card_modal_only_allows_exchange_when_count_gt_zero():
    """账号卡牌数量为 0 时不应出现交换入口。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/web/test_owned_cards_exchange_modal.py -v`
Expected: FAIL（入口未实现）

**Step 3: Write minimal implementation**

```python
@router.post("/api/exchange-cards/requests")
async def create_exchange_request(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/web/test_owned_cards_exchange_modal.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/routers/owned_cards.py src/ptcgp_auto_v2/web/services/owned_card_service.py src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json
git commit -m "feat: add exchange request entry in owned card modal"
```

### Task 6: 管理中心新增“交换记录”

**Files:**
- Create: `src/ptcgp_auto_v2/web/routers/exchange_card.py`
- Create: `src/ptcgp_auto_v2/web/services/exchange_card_service.py`
- Create: `src/ptcgp_auto_v2/web/queries/exchange_card_queries.py`
- Create: `src/ptcgp_auto_v2/web/templates/partials/exchange_card_list.html`
- Modify: `src/ptcgp_auto_v2/web/app.py`
- Modify: `src/ptcgp_auto_v2/web/templates/index.html`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/tabs.js`
- Modify: `src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js`
- Modify: `src/ptcgp_auto_v2/web/locales/zh_CN.json`
- Modify: `src/ptcgp_auto_v2/web/locales/en.json`

**Step 1: Write the failing test**

```python
def test_management_exchange_page_renders_requests_and_actions():
    """管理页应展示交换请求列表并提供取消操作。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/web/test_exchange_management.py -v`
Expected: FAIL（页面未接入）

**Step 3: Write minimal implementation**

```python
@router.get("/management/exchange-cards", response_class=HTMLResponse)
async def get_management_exchange_cards(...):
    ...
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/web/test_exchange_management.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/web/routers/exchange_card.py src/ptcgp_auto_v2/web/services/exchange_card_service.py src/ptcgp_auto_v2/web/queries/exchange_card_queries.py src/ptcgp_auto_v2/web/templates/partials/exchange_card_list.html src/ptcgp_auto_v2/web/app.py src/ptcgp_auto_v2/web/templates/index.html src/ptcgp_auto_v2/web/static/js/modules/tabs.js src/ptcgp_auto_v2/web/static/js/modules/bootstrap.js src/ptcgp_auto_v2/web/locales/zh_CN.json src/ptcgp_auto_v2/web/locales/en.json
git commit -m "feat: add exchange records management page"
```

### Task 7: 文档与可见性补齐

**Files:**
- Modify: `README.md`
- Modify: `src/ptcgp_auto_v2/web/AGENTS.md`

**Step 1: Write the failing test**

```python
def test_docs_mentions_exchange_cards_feature():
    """文档应包含交换卡牌能力与管理入口说明。"""
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/docs/test_readme_exchange_cards.py -v`
Expected: FAIL（说明缺失）

**Step 3: Write minimal implementation**

```markdown
- 新增“交换卡牌”任务能力说明
- 新增“管理中心 -> 交换记录”入口说明
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/docs/test_readme_exchange_cards.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add README.md src/ptcgp_auto_v2/web/AGENTS.md
git commit -m "docs: document exchange cards workflow"
```

### Task 8: 全链路验证与回归

**Files:**
- Test-only

**Step 1: Run focused tests**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: PASS

**Step 2: Run regression tests**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_send_card_daily_task.py src/ptcgp_auto_v2/tests/tasks/test_manage_friendship_task.py src/ptcgp_auto_v2/tests/hooks/test_gift_hooks.py -v`
Expected: PASS

**Step 3: Manual verification checklist**

```text
1) 拥有卡牌弹窗可发起 exchange request（IM/UR 被拦截）
2) 管理中心可查看并取消 exchange request
3) sending -> sended -> completed/canceled/failed 状态流转正确
4) 超时窗口到达后自动复查并收敛
```

**Step 4: Final commit (if needed)**

```bash
git add <relevant-files-only>
git commit -m "feat: complete exchange cards end-to-end workflow"
```

## 风险与边界

- 请求状态与任务状态解耦：request 记录业务结果，task_instance 用于调度执行。
- 所有时间字段使用本地时间（`datetime.now()` / SQL localtime）。
- 禁止硬编码 OCR 文本，页面识别统一走 `get_text_patterns(...)`。
- 对 `send_card_daily` / `manage_friendship` 仅允许“无侵入式复用”，避免回归。

## 执行策略

1. 先实现后端状态机与任务，再接 Web 入口与管理页。
2. 每个 Task 按 TDD 小步推进，失败用例优先。
3. 每步独立验证，必要时分批提交，避免大变更难回滚。
