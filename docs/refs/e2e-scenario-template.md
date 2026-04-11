# E2E 场景模板

这份文档只讲一件事：基于当前分支里的框架模板新增一个 E2E 场景。

## 目录模板

先复制模板目录：

```bash
cp -R src/ptcgp_auto_v2/tests/e2e/scenarios/_template \
  src/ptcgp_auto_v2/tests/e2e/scenarios/<case_id>
```

复制后目录长这样：

```text
scenarios/<case_id>/
  config.py
  core.py
  device.py
```

如果这个场景只做一个 profile，删掉不需要的文件和配置。

## `config.py` 怎么写

`config.py` 只写元信息。
执行逻辑不要写这里。

示例：

```python
from ptcgp_auto_v2.tests.e2e.scenario_loader import E2EScenarioConfig

CONFIGS = {
    "core": E2EScenarioConfig(
        case_id="normal_completion",
        profile="core",
        description="验证 core 层正常完成闭环",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "wait_timeout_seconds": 20,
        },
    ),
    "device": E2EScenarioConfig(
        case_id="normal_completion",
        profile="device",
        description="验证 device 真实执行器正常完成闭环",
        task_type="claim_gifts",
        allow_skipped=False,
        params={
            "join_timeout_seconds": 300,
            "lease_timeout_seconds": 12,
        },
    ),
}
```

固定要求：
- `case_id` 必须等于目录名
- `description` 必须写清楚“测什么”
- 默认任务优先选 `claim_gifts`
- `params` 只放这个场景自己要用的参数

## `core.py` / `device.py` 怎么写

这两个文件只做一件事：实现本 profile 的 `run(ctx)`。

推荐结构：

```python
def run(ctx):
    # 1. setup
    # 2. act
    # 3. inject
    # 4. observe
    # 5. assert
    # 6. cleanup
    pass
```

示例骨架：

```python
def run(ctx):
    """这里写清楚这个场景在验证什么。"""
    ctx.log(ctx.config.description)

    # setup
    task_type = ctx.config.task_type

    # act
    # 启动 scheduler 或 run_single_task

    # inject
    # 如果需要故障注入，在这里做

    # observe
    # 用 wait_until 或 snapshot_runtime 观察状态变化

    # assert
    # 断言任务状态、active_in_scheduler、设备释放
```

## 场景里允许依赖什么

优先使用 `ctx.harness` 提供的公共动作：
- `start_scheduler()`
- `create_scheduler()`
- `stop_scheduler()`
- `override_scheduler_lease_timeout()`
- `wait_until()`
- `snapshot_runtime()`
- `signal_worker()`
- `ensure_task_pending()`
- `mute_other_accounts()`
- `mute_other_tasks_for_account()`

不要重复造轮子。
同样的准备动作，优先复用 harness 现有方法。

## 固定约束

- 不在 `test_e2e_core.py` / `test_e2e_device.py` 写场景逻辑
- 不在 `harness.py` 里硬塞场景专属判断
- 场景文件顶部注释必须说明“测什么”
- `run(ctx)` 顶部 docstring 必须说明“为什么这样测”
- 默认不用 `send_card_daily`
- 至少断言：
  - 任务状态
  - `active_in_scheduler` 状态
  - 设备释放或 worker 清理

## 写完后怎么验证

先过静态检查：

```bash
uv run ruff check src/ptcgp_auto_v2/tests/e2e
```

再跑单场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id>
```

如果你写了 `device.py`，再跑实机场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-device <adb> \
  --e2e-account-id <id> \
  --e2e-device-worker-mode real
```
