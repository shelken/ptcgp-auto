# Exchange Cards Implementation Plan (Fix-2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在已完成 1-7 与 fix-1 的基础上，补齐 `exchange_cards` 的任务状态机、前置校验、超时收敛与管理联动，确保行为与需求文档一致。

**Architecture:** 继续以 `ExchangeCardRequest` 为业务真相，`TaskInstance(exchange_cards)` 仅负责执行驱动与重试唤醒。任务层按 `sending/sended` 分阶段处理，所有失败/取消/完成都写回 request，不将 task instance 标记为失败。调度层只唤醒到期请求，不承担业务判定。

**Tech Stack:** Python 3.12 + SQLModel + Scheduler + Task Registry + OCR/Template + FastAPI/HTMX

---

> 用户原始诉求（原文保留）：
>
> @docs/needs/11-交换卡牌.md

## 当前差距（Fix-2 范围）

1. `exchange_cards` 仍是最小骨架，缺少需求中的页面流转与状态机收敛。
2. 缺少前置校验：14 天冷静期、交换点数不足、目标卡数量不足。
3. 缺少 `FriendPreHook` 接入与 `sended` 阶段完成/取消分支。
4. `next_check_at` 有延后逻辑但无 `expire_at` 收敛，存在无限复查风险。
5. repo 缺少显式语义接口（`has_active_request` / due 查询 / 原子状态迁移）。
6. Web 创建请求后缺少任务唤醒；管理取消对 `sended` 缺少“进入任务执行取消”的对齐策略。

---

### Task 1: Repo 能力补齐（active/due/状态迁移）

**Files:**
- Modify: `src/ptcgp_auto_v2/db/repositories/exchange_card_request_repository.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py`

**Step 1: Write the failing tests**

```python
def test_has_active_request_returns_true_for_sending_or_sended():
    ...

def test_list_due_sended_requests_only_returns_due_rows():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: FAIL（方法未实现）

**Step 3: Write minimal implementation**

- 新增 `has_active_request(from_account_id)`
- 新增 `list_due_sended_requests(now)`（SQL 过滤 `next_check_at <= now`）
- 新增状态迁移辅助：`mark_failed/mark_canceled/mark_completed/mark_sended`

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: PASS

---

### Task 2: Service 与创建入口对齐（校验 + 唤醒）

**Files:**
- Modify: `src/ptcgp_auto_v2/services/exchange_card_service.py`
- Modify: `src/ptcgp_auto_v2/web/routers/owned_cards.py`
- Modify: `src/ptcgp_auto_v2/web/services/exchange_card_service.py`
- Test: `src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py`

**Step 1: Write the failing tests**

```python
def test_create_request_rejects_active_account_request():
    ...

def test_create_request_sets_expire_at_when_created():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- `create_request()` 调用 `has_active_request` 显式拦截
- 创建请求时写入 `expire_at`（默认窗口，例如 30 分钟）
- Web 创建成功后调用 `TaskInstanceRepository.ensure_pending(..., exchange_cards, once)` 立即唤醒
- 管理端取消：`sending` 直接 canceled；`sended` 写取消意图字段并唤醒任务由任务执行取消

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py -v`
Expected: PASS

---

### Task 3: 任务前置校验（进入页面前可快速失败）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/locales/zh_Hant.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py`

**Step 1: Write the failing tests**

```python
def test_on_start_fails_when_account_not_past_14_days():
    ...

def test_on_start_fails_when_no_active_request():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- `on_start` 中补齐：账号ID/活跃请求/14天冷静期
- 引入 `_fail_request(reason)` 统一写 request `failed`
- 保持 task 完成态（不抛 TaskResult.fail）

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: PASS

---

### Task 4: sending 阶段流程补齐（最小闭环）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/locales/zh_Hant.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py`

**Step 1: Write the failing tests**

```python
def test_sending_moves_to_sended_and_sets_next_check():
    ...

def test_sending_marks_failed_when_send_button_not_found_after_retries():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- 用页面内动作缓存 dict 防重入（符合 tasks/AGENTS 规范）
- 仅在正确页面进行精确点击（`exact=True`）
- 失败超过阈值写 `failed_reason`
- 成功后 `status=sended` + `next_check_at`

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: PASS

---

### Task 5: sended 阶段流程补齐（完成/取消/超时）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/locales/zh_Hant.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py`

**Step 1: Write the failing tests**

```python
def test_sended_marks_completed_when_confirm_exchange_success():
    ...

def test_sended_marks_canceled_when_expired_without_partner_response():
    ...

def test_sended_reschedules_next_check_when_still_waiting():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- `sended` 分支识别：可交换完成、等待中、取消路径
- 若到达 `expire_at` 仍等待，执行取消并写 `canceled`
- 若仍在窗口内等待，延后 `next_check_at`（固定步长）

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py -v`
Expected: PASS

---

### Task 6: 调度与管理联动回归

**Files:**
- Modify: `src/ptcgp_auto_v2/core/scheduler.py`
- Modify: `src/ptcgp_auto_v2/web/services/exchange_card_service.py`
- Test: `src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py`
- Test: `src/ptcgp_auto_v2/tests/web/test_exchange_management.py`

**Step 1: Write/adjust failing tests**

```python
def test_scheduler_wake_uses_due_query_only():
    ...

def test_cancel_sended_request_sets_cancel_intent_and_wakes_task():
    ...
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py src/ptcgp_auto_v2/tests/web/test_exchange_management.py -v`
Expected: FAIL

**Step 3: Write minimal implementation**

- 调度器改用 repo 的 due 查询
- 管理取消在 `sended` 时改为“写取消意图 + 唤醒任务”，避免越权直接终态

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py src/ptcgp_auto_v2/tests/web/test_exchange_management.py -v`
Expected: PASS

---

### Task 7: 全链路验证（重点回归）

**Files:**
- Test-only

**Step 1: Run focused tests**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/services/test_exchange_card_service.py src/ptcgp_auto_v2/tests/tasks/test_exchange_cards_task.py src/ptcgp_auto_v2/tests/core/test_scheduler_exchange_due.py src/ptcgp_auto_v2/tests/web/test_exchange_management.py -v`
Expected: PASS

**Step 2: Run related regression**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_send_card_daily_task.py src/ptcgp_auto_v2/tests/tasks/test_manage_friendship_task.py -v`
Expected: PASS

**Step 3: Manual verification checklist**

```text
1) Web 创建后可立即触发对应账号 exchange_cards
2) sending 成功后写入 sended + next_check_at
3) sended 在窗口内等待会复查，超时会 canceled 并写 reason
4) 对方完成后可进入 completed
5) 任何业务失败都写 request failed_reason，不让 task instance 进入 failed
```

---

## 风险与边界

- 需求中的“完整页面自动化细节”较长，Fix-2 优先保证状态机与收敛正确，再逐步补齐 OCR 细节。
- 取消路径需与游戏实际页面状态一致；若页面变化，优先写 request 失败并收敛，避免死循环。
- 所有文本匹配均走 locale key，禁止硬编码 OCR 文本。
- 时间统一使用本地时间 `datetime.now()`。

## 进度

- [x] 计划重写（Fix-2）
- [x] Task 1 Repo 能力补齐（代码已改，待 pytest 验证）
- [x] Task 2 Service 与创建入口对齐（代码已改，待 pytest 验证）
- [x] Task 3 任务前置校验（代码已改，待 pytest 验证）
- [x] Task 4 sending 流程补齐（代码已改，待 pytest 验证）
- [x] Task 5 sended 流程补齐（代码已改，待 pytest 验证）
- [x] Task 6 调度与管理联动回归（代码已改，待 pytest 验证）
- [x] Task 7 全链路验证

### 阶段备注（2026-02-12）

- 已使用 `PYTHONPATH=src:. uv run pytest` 完成命令级验证。
- 交换链路 + 关联回归共 29 项测试通过。
