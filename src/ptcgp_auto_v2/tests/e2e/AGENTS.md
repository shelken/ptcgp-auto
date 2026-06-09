本目录是通用 E2E 框架，不是某一个功能的测试脚本堆。

你在这里工作时，目标只有两个：
- 把场景写清楚
- 让新增场景的成本保持很低

## 模拟器资源约束

实机 E2E 默认禁止频繁重启模拟器。

固定规则：
- 先做 `adb shell`、`uiautomator2 connect` 之类的健康检查，再决定是否重启
- 同一轮定位里，没有证据证明实例已经失活时，不准反复重启
- 一次重启后要先验证恢复结果，再决定后续动作
- 不能把重启当成默认排障动作，避免浪费系统资源和时间
- task成功情况下可能是当前账号遇到任务跳过或者账号不满足任务流程的情况,必须根据当前要测试内容来检查日志,确保不把任务跳过当成任务成功

## 先理解目录职责

- `test_e2e_core.py`
  - 通用 `core` 入口
  - 只负责发现 `core` 场景、加载配置、执行 `run(ctx)`

- `test_e2e_device.py`
  - 通用 `device` 入口
  - 只负责发现 `device` 场景、加载配置、执行 `run(ctx)`

- `scenario_loader.py`
  - 负责发现 `scenarios/<case_id>/`
  - 负责加载 `config.py`
  - 负责按 profile 加载 `core.py` 或 `device.py`
  - 负责处理 `override`

- `harness.py`
  - 公共测试基础设施
  - 负责启动/停止 scheduler、轮询、抓快照、发信号、隔离测试数据库、写 trace
  - 不写具体业务场景

- `scenarios/<case_id>/`
  - 一个目录就是一个业务场景
  - 目录内自己描述“测什么、怎么测、断言什么”

## profile 是什么

- `core`
  - 用假 worker 或可控 worker
  - 目标是稳定、快速、可重复
  - 用来验证调度状态机、线程卡死回收、并发竞态这类逻辑

- `device`
  - 用真实执行器和真实设备
  - 目标是验证真实链路仍然成立
  - 用来验证调度器接上 ADB 和任务执行后没有断链

同一个业务场景可以同时有 `core` 和 `device` 两个版本。
它们共用同一个目录，因为它们验证的是同一件事，只是执行环境不同。

## 场景目录约定

每个场景一个目录：`scenarios/<case_id>/`

固定文件：
- `config.py`
- `core.py`，可选
- `device.py`，可选

当前分支默认只有 `_template/`，具体场景按需新增。

规则：
- 目录名就是 `case_id`
- `config.py` 必须导出 `CONFIGS`，按 profile 分开配置
- `core.py` / `device.py` 必须导出 `run(ctx)`
- loader 会按约定加载同名模块，不在一个文件里写 profile 分支
- 如果场景只支持一个 profile，只保留对应文件和对应配置

## 新增场景怎么做

1. 复制 `scenarios/_template/` 到 `scenarios/<case_id>/`
2. 把 `config.py` 里的 `case_id` 改成目录名
3. 写清楚 `description`
4. 默认任务优先选 `claim_gifts`
5. 只实现需要的 `core.py` / `device.py`
6. 在 `run(ctx)` 里按顺序写完整流程：
   - setup
   - act
   - inject
   - observe
   - assert
   - cleanup

## 场景代码怎么写

场景逻辑只写在 `scenarios/<case_id>/core.py` 或 `device.py`。

不要做这些事：
- 不要把业务逻辑写进 `test_e2e_core.py`
- 不要把业务逻辑写进 `test_e2e_device.py`
- 不要在 `harness.py` 里塞场景专属判断
- 不要默认选 `send_card_daily` 这类不可逆任务

轻量化硬规则：
- 每个 E2E 都要尽量走通真实流程边界，但必须轻量化。
- 禁止为了覆盖率跑重资源、长耗时、不可逆流程。
- 有送卡、交换、好友申请/删除、生产同步、外部下载等副作用时，优先写只读 / probe / 中止型场景：进入目标页面或调用真实边界后，在最终确认动作前退出。
- 如果无法安全走到真实页面，必须在场景说明里写清楚替代 seam 和未覆盖风险，不能把单测包装成 E2E。

至少要断言三件事：
- 任务状态对了
- 调度器活跃执行状态对了（`active_in_scheduler`）
- worker 线程或设备资源释放了

## `ctx` 里有什么

- `ctx.config`
  - 当前场景最终生效的配置
  - 包含 `task_type`、`description`、`allow_skipped`、`params`

- `ctx.harness`
  - 公共动作入口
  - 常用方法：
    - `create_scheduler()`
    - `stop_scheduler()`
    - `wait_until()`
    - `snapshot_runtime()`
    - `ensure_task_pending()`
    - `mute_other_accounts()`
    - `mute_other_tasks_for_account()`

- `ctx.device_config`
  - 只有 `device` 场景会有
  - 包含 `device_address`、`account_id`、`worker_mode`

- `ctx.log()`
  - 输出当前场景自己的进度信息

## 运行方式

跑全部 `core`：

```bash
uv run pytest -m e2e_core src/ptcgp_auto_v2/tests/e2e -q
```

跑全部 `device`：

```bash
uv run pytest -m e2e_device src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-device emulator-5574 \
  --e2e-account-id 350 \
  --e2e-device-worker-mode real
```

跑单个场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id>
```

跑单个 `device` 场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-device emulator-5574 \
  --e2e-account-id 350 \
  --e2e-device-worker-mode real
```

## CLI 和环境变量

优先用 CLI。
环境变量只做兜底。

支持的 CLI：
- `--e2e-case`
- `--e2e-device`
- `--e2e-account-id`
- `--e2e-device-worker-mode`
- `--e2e-app-log-level`
- `--e2e-console-log-level`
- `--e2e-raw-log-file`
- `--e2e-trace-file`
- `--e2e-trace-snapshot-mode`
- `--e2e-override KEY=VALUE`

环境变量：
- `PTCGP_E2E_CASE`
- `PTCGP_E2E_DEVICE`
- `PTCGP_E2E_ACCOUNT_ID`
- `PTCGP_E2E_DEVICE_WORKER_MODE`
- `PTCGP_E2E_APP_LOG_LEVEL`
- `PTCGP_E2E_CONSOLE_LOG_LEVEL`
- `PTCGP_E2E_RAW_LOG_FILE`
- `PTCGP_E2E_TRACE_FILE`
- `PTCGP_E2E_TRACE_SNAPSHOT_MODE`
- `PTCGP_E2E_OVERRIDE_<FIELD>`
- `PTCGP_E2E_OVERRIDE_PARAMS__<KEY>`

## override 规则

- 只允许覆盖当前选中的单场景
- 没有 `case_id` 时禁止 override
- 未知字段直接失败
- `PARAMS__<KEY>` 用来覆盖 `config.params`

示例：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-override PARAMS__LEASE_TIMEOUT_SECONDS=4
```

## 路径规则（写死）

E2E 里只允许一个路径来源：`pytestconfig.rootpath`。

固定规则：
- 项目根目录：只准用 `pytestconfig.rootpath`
- 测试数据库：只准用 `pytestconfig.rootpath / "data" / "ptcgp_v2.db"`
- E2E 日志根目录：只准用 `pytestconfig.rootpath / ".e2e-logs"`
- E2E 日志路径：只准用 `<日志根>/<case_id>/<profile>/app.log` 和 `<日志根>/<case_id>/<profile>/trace.jsonl`

禁止：
- `Path.cwd()`
- `Path(__file__).resolve().parents[n]`
- 硬编码 `/tmp`
- 多套 fallback 路径
- 用环境变量或 CLI 再定义另一套路日志根目录

## 日志怎么用

日常测试不要直接看整段实时输出。
必须优先看持久化日志文件。

E2E 会写两类输出：

- `app.log`
  - 应用原生日志（默认 `TRACE`）
  - 用于查锁、线程回收、任务状态迁移细节

- 控制台输出
  - 单独使用 `--e2e-console-log-level`
  - 默认 `ERROR`，避免终端刷屏占用上下文

- `trace.jsonl`
  - E2E 框架自己的关键事件
  - 用来查场景流程、快照变化、发信号、等待超时

默认日志文件写到 pytest 临时目录。
pytest 结束时会统一打印本次 pytest 临时日志根目录。

常用查法：

```bash
rg '"event":"wait_until_timeout"' /path/to/trace.jsonl
rg '"event":"signal_worker_ok"' /path/to/trace.jsonl
rg 'Scheduler|DevicePool|stale_thread_timeout|任务失败' /path/to/app.log
```

## 写完场景后必须做什么

1. 先跑 `ruff`

```bash
uv run ruff check src/ptcgp_auto_v2/tests/e2e
```

2. 再跑你新增的单场景

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id>
```

3. 如果你写了 `device.py`，再跑对应的 `device` 版本

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-device <adb> \
  --e2e-account-id <id> \
  --e2e-device-worker-mode real
```

## 当前状态

当前分支内置：
- `_template/`
- `fetch_account_info_completion`（仅 `device`）
