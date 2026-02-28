# Pack Opening Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 通过一次继承将 `open_pack`、`claim_gifts`、`init_account` 的开包页面处理、识别、开包记录与稀有卡保存通知统一到同一套可复用流程。

**Architecture:** 新增 `PackOpeningTaskBase`（继承 `Task`）作为统一开包流程基类，收敛页面规则、handler 分发、识别编排、落库和通知。三个任务仅保留各自入口页面与完成条件，通过覆写少量扩展点（`get_target_pack_context`、`get_fixed_set_code`、`should_prepare_pack_resources`、`get_pack_record_type`）实现差异化。采用 TDD 小步提交，确保每个迁移阶段可回归。

**Tech Stack:** Python 3.12, SQLModel Repository, YOLO+Hash (`YoloCardRecognizer`), pytest/unittest, FastAPI 项目内任务框架。

---

### Task 1: 为统一基类先写失败测试（行为契约）

**Files:**
- Create: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**Step 1: Write the failing test**

```python
def test_resolve_set_code_priority_fixed_over_context_over_global():
    task = DummyPackOpeningTask(...)
    task._fixed_set_code = "A1"
    task._target_pack_context = {"pack_code": "A2", "booster_name": "X"}

    assert task._resolve_scan_set_code() == "A1"


def test_handle_pack_opening_result_recognize_once_then_continue():
    task = DummyPackOpeningTask(...)
    task._result_recognized = False
    task._recognize_cards = Mock()

    task._handle_pack_opening_result({"ocr_results": []})
    task._handle_pack_opening_result({"ocr_results": []})

    task._recognize_cards.assert_called_once()


def test_save_pack_record_uses_subclass_pack_type():
    task = DummyPackOpeningTask(...)
    task._pack_record_repo = Mock()
    task._pack_record_repo.create_for_account.return_value = object()
    task.bind_account(SimpleNamespace(id=1, display_name="acc"))

    task._save_pack_record([{"card_name": "X", "position": 1}])

    kwargs = task._pack_record_repo.create_for_account.call_args.kwargs
    assert kwargs["pack_type"] == "gift_box"
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -v`
Expected: FAIL，提示 `PackOpeningTaskBase` 或相关方法不存在。

**Step 3: Write minimal implementation**

```python
class DummyPackOpeningTask(PackOpeningTaskBase):
    def is_completed(self) -> bool:
        return False

    def get_pack_record_type(self) -> str:
        return "gift_box"
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py
git commit -m "test: add pack opening base behavior tests" -m "新增统一开包基类行为契约测试，约束识别set_code优先级、结果页幂等识别与pack_type落库行为。"
```

### Task 2: 新增 PackOpeningTaskBase 并实现最小可用统一流程

**Files:**
- Create: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tasks/utils/pack_opening_flow.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**Step 1: Write the failing test**

```python
def test_scan_cards_with_retry_calls_scan_without_set_code_when_global_mode():
    task = DummyPackOpeningTask(...)
    task.card_recognizer = Mock()
    task.card_recognizer.scan.side_effect = [[], [DetectedCard(...)] ]

    cards = task._scan_cards_with_retry(set_code=None, max_retries=2)

    assert len(cards) == 1
    task.card_recognizer.scan.assert_called()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py::test_scan_cards_with_retry_calls_scan_without_set_code_when_global_mode -v`
Expected: FAIL，提示 `_scan_cards_with_retry` 未实现对应分支。

**Step 3: Write minimal implementation**

```python
class PackOpeningTaskBase(Task):
    def _resolve_scan_set_code(self) -> str | None:
        return self.get_fixed_set_code() or (self.get_target_pack_context() or {}).get("pack_code")

    def _scan_cards_with_retry(self, set_code: str | None, max_retries: int) -> list[DetectedCard]:
        for _ in range(max_retries):
            cards = self.card_recognizer.scan(set_code=set_code, similarity_threshold=0.68, debug=True)
            if cards:
                return cards
        return []
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py
git commit -m "feat: add shared pack opening task base" -m "新增PackOpeningTaskBase，统一开包页面动作、识别重试与记录保存基础能力。"
```

### Task 3: 迁移 open_pack 继承统一基类（保持既有业务入口）

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`

**Step 1: Write the failing test**

```python
def test_open_pack_should_use_base_pack_type_daily_free():
    task = OpenPackTask(...)
    assert task.get_pack_record_type() == "daily_free"


def test_open_pack_handle_map_keeps_pack_specific_pages():
    task = OpenPackTask(...)
    result = task.handle_page("pack_detail", {"ocr_results": []})
    assert result.success is True
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py -v`
Expected: FAIL，提示新扩展点方法未提供或 handle 路由冲突。

**Step 3: Write minimal implementation**

```python
class OpenPackTask(PackOpeningTaskBase):
    def get_pack_record_type(self) -> str:
        return "daily_free"

    def get_target_pack_context(self) -> dict[str, str] | None:
        return self.target_pack

    def get_fixed_set_code(self) -> str | None:
        return (self.target_pack or {}).get("pack_code")

    def should_prepare_pack_resources(self) -> bool:
        return True
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/open_pack.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py
git commit -m "refactor: migrate open_pack to shared pack base" -m "将open_pack迁移为继承统一开包基类，保留主页与选包业务入口，移除重复开包处理代码。"
```

### Task 4: 迁移 claim_gifts 到统一开包流程并补齐识别+记录

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`

**Step 1: Write the failing test**

```python
def test_claim_gifts_should_use_pack_type_gift_box():
    task = ClaimGiftsTask(...)
    assert task.get_pack_record_type() == "gift_box"


def test_claim_gifts_pack_opening_result_should_trigger_recognize_once():
    task = ClaimGiftsTask(...)
    task._recognize_cards = Mock()
    task._result_recognized = False

    task.handle_page("pack_opening_result", {"ocr_results": []})
    task.handle_page("pack_opening_result", {"ocr_results": []})

    task._recognize_cards.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py -v`
Expected: FAIL，提示 claim_gifts 尚未接入开包结果页统一处理。

**Step 3: Write minimal implementation**

```python
class ClaimGiftsTask(PackOpeningTaskBase):
    pages = _build_claim_gifts_pages() + build_pack_opening_pages()

    def get_pack_record_type(self) -> str:
        return "gift_box"

    def should_prepare_pack_resources(self) -> bool:
        return False
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/claim_gifts.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py
git commit -m "feat: unify claim_gifts with shared pack flow" -m "让领取礼物任务继承统一开包流程，补齐开包识别与开包记录落库，pack_type使用gift_box。"
```

### Task 5: 迁移 init_account 到统一开包流程并落库教程开包

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py`

**Step 1: Write the failing test**

```python
def test_init_account_should_use_pack_type_init_tutorial():
    task = InitAccountTask(...)
    assert task.get_pack_record_type() == "init_tutorial"


def test_init_account_pack_opening_result_should_recognize_and_continue():
    task = InitAccountTask(...)
    task._recognize_cards = Mock()
    task._result_recognized = False

    task.handle_page("pack_opening_result", {"ocr_results": []})
    task._recognize_cards.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py -v`
Expected: FAIL，提示 init_account 尚未通过基类实现识别落库。

**Step 3: Write minimal implementation**

```python
class InitAccountTask(PackOpeningTaskBase):
    def get_pack_record_type(self) -> str:
        return "init_tutorial"

    def should_prepare_pack_resources(self) -> bool:
        return False
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/init_account.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py
git commit -m "refactor: align init_account with shared pack opening base" -m "将初始化任务教程开包接入统一识别与开包记录流程，pack_type设为init_tutorial。"
```

### Task 6: 文档同步（结构变更说明）

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `src/ptcgp_auto_v2/tasks/AGENTS.md`

**Step 1: Write the failing test**

```python
def test_plan_docs_are_updated_for_new_pack_opening_base():
    assert "PackOpeningTaskBase" in readme_text
    assert "PackOpeningTaskBase" in root_agents_text
```

**Step 2: Run test to verify it fails**

Run: `python - <<'PY'\nfrom pathlib import Path\nfor p in ["README.md","AGENTS.md","src/ptcgp_auto_v2/tasks/AGENTS.md"]:\n    txt = Path(p).read_text(encoding="utf-8")\n    print(p, "PackOpeningTaskBase" in txt)\nPY`
Expected: 至少一个文件输出 `False`。

**Step 3: Write minimal implementation**

```markdown
- 在任务架构说明新增：PackOpeningTaskBase 负责开包页面统一处理、识别、记录。
- 在任务开发规范新增：涉及开包流程的任务优先继承 PackOpeningTaskBase。
```

**Step 4: Run test to verify it passes**

Run: `python - <<'PY'\nfrom pathlib import Path\nfor p in ["README.md","AGENTS.md","src/ptcgp_auto_v2/tasks/AGENTS.md"]:\n    txt = Path(p).read_text(encoding="utf-8")\n    assert "PackOpeningTaskBase" in txt, p\nprint("PASS")\nPY`
Expected: 输出 `PASS`。

**Step 5: Commit**

```bash
git add README.md AGENTS.md src/ptcgp_auto_v2/tasks/AGENTS.md
git commit -m "docs: document shared pack opening base" -m "更新README与AGENTS说明，明确开包统一基类职责与继承规范。"
```

### Task 7: 全链路回归与收尾

**Files:**
- Test: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py`

**Step 1: Write the failing test**

```python
def test_no_regression_placeholder():
    # 此步不新增功能测试；用于强调先跑全链路检查。
    assert True
```

**Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py -v`
Expected: 如果有遗漏应 FAIL；否则进入下一步。

**Step 3: Write minimal implementation**

```python
# 根据失败信息修复最小代码，不做额外抽象，保持 DRY + YAGNI。
```

**Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/ptcgp_auto_v2/tasks/pack_opening_task_base.py src/ptcgp_auto_v2/tasks/open_pack.py src/ptcgp_auto_v2/tasks/claim_gifts.py src/ptcgp_auto_v2/tasks/init_account.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py README.md AGENTS.md src/ptcgp_auto_v2/tasks/AGENTS.md
git commit -m "test: finalize pack opening unification regression" -m "完成统一开包基类改造后的任务回归测试与文档同步，确保三任务行为一致。"
```

## 参考与执行要求

- 执行本计划前，先在独立 worktree 操作（来自 @superpowers/using-git-worktrees）。
- 实施阶段必须逐任务使用 @superpowers/executing-plans。
- 若选择本会话逐任务执行，使用 @superpowers/subagent-driven-development。
- 每个 Task 都要坚持 TDD：先红后绿，再重构，最后提交。
- 禁止 `git add -A`，必须按任务文件显式 add。

---

## 阶段性审查回填（2026-03-01）

本节基于当前工作区代码与实测结果回填新增问题和待办。

### 已发现问题（带证据）

1. **全局识别模式被破坏**
   - 文件：`src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
   - 现状：`_recognize_cards()` 将 `set_code` 兜底成 `"Unknown"`，导致本该 `None` 的全局识别模式无法生效。
   - 影响：`claim_gifts`、`init_account` 在无固定系列时会被错误限制，识别率下降。

2. **open_pack 前置准备失败后的失败状态回归**
   - 文件：`src/ptcgp_auto_v2/tasks/open_pack.py`
   - 现状：`_prepare_image_resources()` 失败时仅 `logger.error` 并 `return`，未设置 `_fail_reason` 或 `skip_reason`。
   - 影响：任务可能继续运行在不完整状态，行为不可控。

3. **测试隔离性问题（污染全局模块）**
   - 文件：`src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
   - 现状：直接改写 `sys.modules[...] = Mock()`，污染后续测试。
   - 证据：串行执行相关测试出现 2 个失败：
     - 命令：
       `PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py -q`
     - 结果：`2 failed, 55 passed`
     - 失败点：`test_open_pack_task.py` 中 `DetectedCard` 被污染为 `Mock`，触发 `TypeError: float() argument must be a string or a real number, not 'Mock'`。

4. **“自动继承 handle”目标尚未完全达成**
   - 文件：`src/ptcgp_auto_v2/tasks/open_pack.py`、`src/ptcgp_auto_v2/tasks/claim_gifts.py`、`src/ptcgp_auto_v2/tasks/init_account.py`
   - 现状：三任务仍各自手写通用开包页面 handler 映射。
   - 影响：后续新增开包页面时仍需三处同步，存在漂移风险。

5. **关键回归测试缺口**
   - 文件：`src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`
   - 现状：未覆盖 `pack_opening_result` 的“识别一次+落库”行为。
   - 影响：礼物触发开包链路再回归时不易被发现。

### 新增任务（必须补做）

### Task 8: 修复全局识别 set_code 兜底逻辑

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`

**Steps:**
1. 先新增失败测试：断言 `_resolve_scan_set_code() is None` 时，调用 `card_recognizer.scan(set_code=None, ...)`。
2. 运行单测确认失败。
3. 修改实现：`_recognize_cards()` 不再把 `None` 兜底成 `"Unknown"`；仅映射环节在无 `set_code` 时使用识别结果自带 `card.set_code`。
4. 运行相关测试并确认通过。
5. 提交一个独立 commit。

### Task 9: 修复 open_pack 前置准备失败状态传播

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py`

**Steps:**
1. 新增失败测试：模拟 `_prepare_image_resources()` 返回 `False` 后，`handle_page()` 必须返回 `ActionResult.fail(...)` 或任务明确 skip。
2. 运行测试确认失败。
3. 在 `on_start()` 设置 `_fail_reason`（或 `_skipped + _skip_reason`），并在 `handle_page()`/`is_completed()` 中统一处理。
4. 运行测试确认通过。
5. 提交一个独立 commit。

### Task 10: 去除测试全局污染，改为局部 patch

**Files:**
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**Steps:**
1. 删除 `sys.modules[...] = Mock()` 写法。
2. 改为 `unittest.mock.patch` 在测试函数或 fixture 作用域内替换依赖。
3. 确保不影响 `DetectedCard` 真实类型导入。
4. 运行四个任务测试文件串行回归，确认 `0 failed`。
5. 提交一个独立 commit。

### Task 11: 实现通用开包 handler 自动继承分发

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`

**Steps:**
1. 基类新增 `build_pack_opening_handlers()`（返回统一 handler dict）。
2. 三任务 `handle_page()` 合并方式改为：`{**self.build_pack_opening_handlers(), **task_specific_handlers}`（或相反，按覆盖策略明确）。
3. 保证页面优先原则：只按页面名分发，不按状态拦截。
4. 回归测试确保三任务仍通过。
5. 提交一个独立 commit。

### Task 12: 补齐 claim_gifts 开包识别落库测试

**Files:**
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`

**Steps:**
1. 新增失败测试：`pack_opening_result` 首次触发识别和落库、二次进入不重复识别。
2. 新增失败测试：`pack_type == "gift_box"` 写入仓储参数。
3. 跑 `test_claim_gifts_task.py` 并确认从红变绿。
4. 与 Task 8/11 联合回归。
5. 提交一个独立 commit。

---

## 二次复查回填（2026-03-01）

### 复查结论

- `Task 8 ~ Task 12` 主目标基本完成：统一 handler 合并、资源失败状态传播、claim_gifts 识别落库测试已落地。
- 四个核心测试文件已回归通过：
  - 命令：`PYTHONPATH=src pytest src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py src/ptcgp_auto_v2/tests/tasks/test_open_pack_task.py src/ptcgp_auto_v2/tests/tasks/test_init_account_task.py src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py -q`
  - 结果：`63 passed in 7.12s`

### 新发现问题（需要补修）

1. **全局识别下多系列映射仍被错误固定到首卡系列（高优先级）**
   - 文件：`src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
   - 代码点：`_recognize_cards()` 中 `effective_set_code = set_code or cards[0].set_code`
   - 问题：当 `set_code is None`（全局模式）且识别结果混合系列时，会把全部卡强制映射为首张卡系列。
   - 证据：
     - `fixed_set_code='A1'` 时，`map_detected_cards` 查询参数为 `[call('A1', 1), call('A1', 2)]`
     - `fixed_set_code=None` 时，查询参数为 `[call('A1', 1), call('A2', 2)]`

2. **通用基类与任务文件存在明显未使用导入（中优先级）**
   - 影响文件：
     - `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
     - `src/ptcgp_auto_v2/tasks/open_pack.py`
     - `src/ptcgp_auto_v2/tasks/claim_gifts.py`
     - `src/ptcgp_auto_v2/tasks/init_account.py`
   - 影响：噪音增多，增加维护成本，且会在严格 lint 流程下阻塞。

3. **基类契约测试仍以 Dummy 复制逻辑为主（中优先级）**
   - 文件：`src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
   - 问题：大量测试未直接绑定真实 `PackOpeningTaskBase` 行为，未来实现漂移时可能“测的是假逻辑”。

### 新增任务（Task 13+）

### Task 13: 修复全局模式多系列映射错误

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_claim_gifts_task.py`

**Steps:**
1. 先新增失败测试：全局识别下输入 `A1/A2` 两张卡时，`card_repo.get_card_by_set_and_number` 必须按各自 `set_code` 查询。
2. 运行测试确认红灯。
3. 修改实现：`set_code is None` 时传 `fixed_set_code=None` 给 `map_detected_cards`，禁止兜底成 `cards[0].set_code`。
4. 运行四个任务测试文件确认通过。
5. 提交独立 commit。

### Task 14: 清理未使用导入并做最小 lint 收敛

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`

**Steps:**
1. 删除未使用 import，保持行为不变。
2. 仅对改动文件执行 `ruff check`，确认无 F401。
3. 回归四个任务测试文件。
4. 提交独立 commit。

### Task 15: 强化基类真实行为测试（替代 Dummy 复制逻辑）

**Files:**
- Modify: `src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py`

**Steps:**
1. 新增轻量 `TestPackTask(PackOpeningTaskBase)` 测试子类，仅覆写最少抽象方法。
2. 将关键测试迁移为“直接调用真实基类方法”，减少 Dummy 逻辑复制。
3. 保留必要 patch，但不污染全局模块。
4. 跑 `test_pack_opening_task_base.py` 与四文件回归。
5. 提交独立 commit。
