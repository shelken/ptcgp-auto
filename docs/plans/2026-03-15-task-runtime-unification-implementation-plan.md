# Task Runtime Unification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在不改变任何任务功能行为的前提下，统一 `src/ptcgp_auto_v2/tasks/` 下全部任务的状态写法、页面分发写法与公共组件。

**Architecture:** 保留每个任务现有 `pages` 页面协议、原有 handler 职责位置与 `handle_unknown_page()` 策略，只抽离重复的运行时状态、页面切换跟踪、动作缓存与反射式页面分发。新增统一的 `StatefulTask`，全部跨页面运行态一律放进单一 map，并且只允许通过少量通用 wrapper 读写，不再按字段名继续包一层 property。

**Tech Stack:** Python 3.12、现有 `Task` 基类、dataclass、项目现有 task/page detector/action result 体系

---

### 最高原则

- 必须简洁优雅，代码量越少越好；
- 绝对不允许改变原有功能行为。
- 所有任务应该写法应该足够简单，重复的功能应该设为组件
- 面向对象编程

### 已发现的审查反馈（2026-03-16）

- 当前实现已经证明，不能把状态统一做成 `state.lifecycle/state.page/state.flow/state.data` 加字段级 property 壳；这样只是换个地方继续冗余读写。
- 全部跨页面运行态必须一视同仁，统一存入单一 map；读取 / 设置 / 删除 / 清空都必须走通用 wrapper，而不是每个字段一个 getter/setter/property。
- `StatefulTask.on_page_changed()` 默认必须是无副作用 `no-op`，禁止在 `core/` 默认清理业务缓存。
- 页面切换回调必须拿到 `old_page/new_page`，不能只在更新后让任务自己反推旧页面。
- 生命周期统一后，`failed` 语义必须与 `Task.execute()` 闭环；否则禁止引入新失败态。
- 下列任务已确认或高度疑似受影响，修复时必须优先复核：`claim_rewards.py`、`fetch_account_info.py`、`collect_account_cards.py`、`exchange_cards.py`、`init_account.py`、`send_card_daily.py`、`wonder_pick.py`。

### Task 1: 盘点全部任务现有写法并冻结重构边界

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_rewards.py`
- Modify: `src/ptcgp_auto_v2/tasks/fetch_account_info.py`
- Modify: `src/ptcgp_auto_v2/tasks/collect_account_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/wonder_pick.py`
- Modify: `src/ptcgp_auto_v2/tasks/send_card_daily.py`
- Modify: `src/ptcgp_auto_v2/tasks/manage_friendship.py`
- Modify: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/battle.py`
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/`

**Step 1: 列出现有重复点清单**

明确以下重复骨架，后续统一替换：

- `_completed/_skipped/_failed/_skip_reason/_complete_reason` 这类字段级别名
- `_action_cache` 与 `_is_action_done/_mark_action_done/_reset_action_cache`
- `_last_page_name/_prev_page_name/_phase/_target_pack` 这类字段级 property 包装
- `handle_page()` 中手写 `handlers = {...}` 或 `getattr(self, f"_handle_{page_name}")`
- `on_start()` 中批量重置运行时字段
- `is_completed()/was_skipped()` 中重复读取布尔字段

**Step 2: 定义不允许变化的行为边界**

写入实现备注并在编码时逐项遵守：

- 不改 `pages` 识别规则、优先级、页面名
- 不改每个页面原先对应的 handler 归属
- 不改 `handle_unknown_page()` 的具体策略
- 不改业务分支、完成条件、返回动作、通知与入库逻辑
- 不把页面内决策提升成新的全局状态机
- 不改变任一缓存字段的作用域
- 不改变页面切换回调的时序语义（依赖旧页面的逻辑必须保持可表达）
- 不再继续引入 `state.lifecycle/state.page/state.flow/state.data` 这种多区块状态访问
- 不再继续引入字段级 property 包装；统一只允许操作型 wrapper

**Step 3: 建立一次性替换范围**

确认全部任务都接入统一写法，不允许“部分任务旧写法、部分任务新写法”并存。

**Step 4: 运行最小基线测试**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks -q`

Expected: 记录当前基线；后续重构后必须回到同一通过状态。


### Task 2: 新增统一状态 map 与通用状态操作

**Files:**
- Create: `src/ptcgp_auto_v2/core/task_state.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_task_state.py`

**Step 1: 写失败测试，定义统一状态容器接口**

```python
def test_task_state_get_set_clear() -> None:
    state = TaskState()
    state.set("task.completed", True)
    assert state.get("task.completed") is True


def test_task_state_clear_prefix() -> None:
    state = TaskState()
    state.set("action.a", True)
    state.set("action.b", True)
    state.clear_prefix("action.")
    assert state.has("action.a") is False
```

**Step 2: 运行测试确认失败**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks/test_task_state.py -q`

Expected: FAIL，提示 `TaskState` 不存在。

**Step 3: 实现最小状态组件**

要求：

- `TaskState` 只保留一个 `runtime: dict[str, object]`
- 提供统一方法：`get/set/has/delete/clear/clear_prefix/update`
- 禁止再按生命周期 / 页面 / flow / data 拆状态存储结构

**Step 4: 运行测试确认通过**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks/test_task_state.py -q`

Expected: PASS


### Task 3: 新增统一状态化任务基类

**Files:**
- Create: `src/ptcgp_auto_v2/core/stateful_task.py`
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Test: `src/ptcgp_auto_v2/tests/tasks/test_stateful_task.py`

**Step 1: 写失败测试，定义基类公共协议**

```python
class DummyTask(StatefulTask):
    pages = []

    def handle_unknown_page(self, page_info):
        return ActionResult.wait(0.5)


def test_stateful_task_dispatches_by_reflection(fake_adb, page_detector):
    task = DummyTask(fake_adb, None, page_detector)
    called = []

    def _handle_home_main(page_info):
        called.append("home_main")
        return ActionResult.ok(wait=0.1)

    task._handle_home_main = _handle_home_main
    result = task.handle_page("home_main", {})

    assert result.success is True
    assert called == ["home_main"]
```

**Step 2: 运行测试确认失败**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks/test_stateful_task.py -q`

Expected: FAIL，提示 `StatefulTask` 不存在。

**Step 3: 实现 `StatefulTask`**

要求：

- 继承现有 `Task`
- 初始化 `self.state = TaskState()`
- 提供通用状态操作：`state_get/state_set/state_has/state_del/state_clear/state_clear_prefix/state_update`
- 提供通用行为包装：`complete()/skip()/fail()`、`is_completed()/was_skipped()/is_failed()`
- 提供通用动作包装：`is_action_done()/mark_action_done()/reset_action_cache()`
- 提供通用页面包装：`get_current_page()/get_previous_page()/set_current_page()`
- `handle_page()` 统一用反射分发 `_handle_{page_name}`
- 未命中时转交 `handle_unmapped_page()`，默认 `ActionResult.ok(wait=1.0)`
- 不接管 `handle_unknown_page()`，仍由原执行框架在 page_name=`unknown` 时调用
- `on_page_changed()` 默认必须无副作用，不得默认清理任何业务缓存
- `on_page_changed()` 必须拿到 `previous_page_name` 与 `page_name`
- 若保留 `fail()`/`failed`，必须同步修改 `Task.execute()` 让失败态返回 `TaskResult.fail(...)`
- 禁止新增任何字段级 wrapper，例如 `_completed`、`_phase`、`_target_pack`、`_home_check_count`

**Step 4: 让 `PackOpeningTaskBase` 改继承 `StatefulTask`**

只替换基类继承关系与 `_action_cache` 访问方式，不动通用开包业务逻辑。

**补充约束**

- `TaskState` / `StatefulTask` 属于任务执行框架，必须放在 `core/`
- `tasks/` 目录只允许放具体任务与任务专用工具，不放框架级状态模型

**Step 5: 运行测试确认通过**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks/test_stateful_task.py src/ptcgp_auto_v2/tests/tasks/test_pack_opening_task_base.py -q`

Expected: PASS


### Task 4: 全量任务接入统一状态 map 与反射分发

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/open_pack.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_gifts.py`
- Modify: `src/ptcgp_auto_v2/tasks/init_account.py`
- Modify: `src/ptcgp_auto_v2/tasks/claim_rewards.py`
- Modify: `src/ptcgp_auto_v2/tasks/fetch_account_info.py`
- Modify: `src/ptcgp_auto_v2/tasks/collect_account_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/wonder_pick.py`
- Modify: `src/ptcgp_auto_v2/tasks/send_card_daily.py`
- Modify: `src/ptcgp_auto_v2/tasks/manage_friendship.py`
- Modify: `src/ptcgp_auto_v2/tasks/exchange_cards.py`
- Modify: `src/ptcgp_auto_v2/tasks/battle.py`

**Step 1: 删除重复生命周期裸字段与字段级别名**

把以下字段统一替换为通用 wrapper 调用：

- `_completed`
- `_skipped`
- `_failed`
- `_complete_reason`
- `_skip_reason`
- `_fail_reason`

保留同名旧字段或 property 壳只会制造双轨状态，禁止兼容保留。

**Step 2: 删除各任务重复 action cache 三件套**

把以下能力统一改为基类通用方法：

- `_is_action_done()` -> `is_action_done()`
- `_mark_action_done()` -> `mark_action_done()`
- `_reset_action_cache()` -> `reset_action_cache()`
- 其他运行态 -> `state_get()/state_set()/state_del()/state_clear()`

并删除任务里重复声明的 `_action_cache` 与同类 property 壳。

**Step 3: 删除手写 `handlers = {...}` 分发表**

将所有任务的页面处理器改名为严格对应 page name 的反射式方法：

- `game_home_main` -> `_handle_game_home_main`
- `pack_paid` -> `_handle_pack_paid`
- `gift_box_page` -> `_handle_gift_box_page`
- 等等

要求：

- page 名与 handler 名 1:1 对应
- 不新增业务中转层
- 不改变 handler 内逻辑，只改入口写法

**Step 4: 把页面切换跟踪统一进基类**

将 `_last_page_name/_prev_page_name` 或同类逻辑，改为调用 `get_current_page()/get_previous_page()/set_current_page()`。

页面切换时需要清 cache 的任务，在 `on_page_changed()` 里显式覆写，不要在基类默认清理。

只有原本就是动作缓存的 key 才跟随 `reset_action_cache()` 清理；其他跨页面流程状态继续留在统一 map 中。

**Step 5: 将任务运行时字段统一改成单一 map 访问**

例如：

- `open_pack` 的 `_home_check_count/_pack_hourglass_count/_target_pack`
- `wonder_pick` 的 `_current_stamina/_pending_after_challenge`
- `collect_account_cards` 的 `_pending_cards/_pending_order`
- `send_card_daily` 的 `_gift_sent_success/_filter_applied`

要求：

- 全部跨页面运行态统一使用 `state_set()/state_get()` 访问
- 不再继续新增裸实例字段
- 不允许把运行态拆到多个状态分区
- 不允许给单个字段继续包 property

**Step 6: 让 `battle` 也接入统一状态模型**

`battle` 可保留它的动态停止条件行为，但：

- 生命周期状态仍统一走 `self.state.lifecycle`
- 反射分发仍走基类默认 `handle_page()`
- 删除它自建的重复完成态写法（如有）

**Step 7: 运行全任务测试**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks -q`

Expected: PASS，且无行为变化。

**补充人工复核清单**

- `claim_rewards.py`：确认 `tab_claimed/theme_checked` 仍跨页面保留
- `fetch_account_info.py`：确认 `profile_fetched/more_menu_opened/holdings_fetched` 仍跨页面保留
- `collect_account_cards.py`：确认 `filter_applied/sort_ready` 不会因离开弹窗丢失
- `exchange_cards.py`：确认筛选状态与恢复重发状态不被页面切换清空
- `init_account.py`：确认 `after_favorite_card` 与 `_phase == COMPLETED` 的完成语义保持原状
- `send_card_daily.py`：确认从 `gift_filter_modal -> gift_select_card` 时仍能读取旧页面名并设置 `_filter_applied`
- `wonder_pick.py` / `battle.py`：确认任务实例复用时 `state` 会在 `on_start()` 重置


### Task 5: 校验行为不变并清理冗余代码

**Files:**
- Modify: `src/ptcgp_auto_v2/tasks/*.py`
- Modify: `src/ptcgp_auto_v2/tasks/pack_opening_task_base.py`
- Modify: `src/ptcgp_auto_v2/tasks/stateful_task.py`
- Modify: `src/ptcgp_auto_v2/tasks/task_state.py`

**Step 1: 删除迁移后未使用字段和方法**

重点清理：

- 已被统一状态取代的裸字段
- 已被基类取代的 `_is_action_done/_mark_action_done/_reset_action_cache`
- 已被反射分发取代的手写 `handlers` 字典

**Step 2: 全量跑任务测试**

Run: `PYTHONPATH=src uv run pytest src/ptcgp_auto_v2/tests/tasks -q`

Expected: 全绿。

**Step 3: 做静态语法检查**

Run: `uv run python -m py_compile src/ptcgp_auto_v2/tasks/*.py`

Expected: 无语法错误。

**Step 4: 提交**

```bash
git add src/ptcgp_auto_v2/tasks src/ptcgp_auto_v2/tests/tasks docs/plans/2026-03-15-task-runtime-unification-implementation-plan.md
git commit -m "refactor(tasks): unify task runtime and page dispatch"
```
