# 线程调度回收 E2E 框架

## 这套 E2E 在干什么

这份文档只说明当前分支已迁移过来的 E2E 框架骨架、模板和运行约定。

当前分支只保留框架能力：
- 通用 `core` / `device` 入口
- 场景加载与 override 机制
- 通用 harness、trace、日志隔离
- 场景模板与新增约定

具体业务场景需要按需在 `scenarios/<case_id>/` 下补充。

## 模拟器约束

实机 E2E 默认禁止频繁重启模拟器。

固定规则：
- 没有先完成 `adb shell`、`uiautomator2 connect` 这类健康检查前，不允许直接重启模拟器
- 同一轮排查里，只有明确证明当前实例已经失活或必须冷启动时，才允许执行一次重启
- 重启后必须先验证设备恢复，再继续跑 pytest
- 不能把“重启试试看”当成常规步骤，避免额外消耗系统资源和浪费时间

## 整体执行流程

跑一条 E2E 时，链路固定是这样：

1. `pytest` 进入 `test_e2e_core.py` 或 `test_e2e_device.py`
2. 测试入口按 profile 发现全部场景目录
3. 如果传了 `--e2e-case`，只保留这一条场景
4. loader 读取 `scenarios/<case_id>/config.py`
5. loader 按 profile 加载 `core.py` 或 `device.py`
6. fixture 构建 `ScenarioContext`
7. 场景模块执行 `run(ctx)`
8. 场景通过 `ctx.harness` 启动 scheduler、轮询状态、注入故障、抓快照、断言结果
9. 日志和 trace 写入 pytest 临时目录

## 为什么分 `core` 和 `device`

这不是重复。

- `core`
  - 用可控 worker 跑
  - 快，稳定，适合反复回归
  - 重点验证状态机和线程超时回收逻辑

- `device`
  - 用真实设备和真实执行器跑
  - 慢，但能发现 ADB、任务执行链、真实阻塞这类问题
  - 重点验证真实链路没有断

同一个业务场景放同一个目录，因为两者验证的是同一个目标，只是执行环境不同。

## 目录结构

```text
src/ptcgp_auto_v2/tests/e2e/
  conftest.py
  harness.py
  scenario_loader.py
  test_e2e_core.py
  test_e2e_device.py
  scenarios/
    _template/
    <case_id>/
      config.py
      core.py
      device.py
```

各文件职责：

- `conftest.py`
  - 解析 CLI 和环境变量
  - 构建 core/device fixture
  - 准备临时数据库和临时日志目录

- `scenario_loader.py`
  - 发现目录
  - 读取配置
  - 加载场景模块
  - 处理 override

- `harness.py`
  - 通用公共动作
  - 不写任何场景专属流程

- `scenarios/<case_id>/`
  - 一个目录就是一个完整场景单元

## 场景目录约定

每个场景目录固定长这样：

```text
scenarios/<case_id>/
  config.py
  core.py
  device.py
```

要求：
- 目录名必须等于 `case_id`
- `config.py` 必须导出 `CONFIGS`
- `CONFIGS["core"]` / `CONFIGS["device"]` 使用 `E2EScenarioConfig`
- `core.py` / `device.py` 必须导出 `run(ctx)`
- 只支持一个 profile 时，只保留对应文件和对应配置

## `config.py` 写什么

`config.py` 只写场景元信息，不写执行逻辑。

字段含义：
- `case_id`
  - 场景唯一标识，必须和目录名一致
- `profile`
  - `core` 或 `device`
- `description`
  - 一句话写清楚这个场景在验证什么
- `task_type`
  - 默认测试任务
  - 优先用 `claim_gifts`
- `allow_skipped`
  - 是否允许 `skipped` 也算通过
- `params`
  - 场景私有参数
  - 框架不解释，场景自己取用

## `run(ctx)` 写什么

场景执行逻辑全部写在 `core.py` / `device.py` 的 `run(ctx)`。

固定写法：
- setup
- act
- inject
- observe
- assert
- cleanup

至少断言三件事：
- 任务状态
- 调度器活跃执行状态（`active_in_scheduler`）
- 设备或 worker 是否释放

不要把场景逻辑写进：
- `test_e2e_core.py`
- `test_e2e_device.py`
- `harness.py`

## `ctx` 能用什么

- `ctx.config`
  - 当前场景最终配置

- `ctx.harness`
  - 公共动作集合
  - 常用方法：
    - `create_scheduler()`
    - `start_scheduler()`
    - `stop_scheduler()`
    - `override_scheduler_lease_timeout()`
    - `wait_until()`
    - `snapshot_runtime()`
    - `signal_worker()`
    - `ensure_task_pending()`
    - `mute_other_accounts()`
    - `mute_other_tasks_for_account()`

- `ctx.device_config`
  - 只有 device 场景有
  - 包含 `device_address`、`account_id`、`worker_mode`

- `ctx.log()`
  - 场景自己的可见进度日志

## 测试数据库怎么处理

- `core`
  - 用 pytest 临时目录里的全新数据库
  - 场景里通常自己 seed 一个最小账号和任务

- `device`
  - 从项目里的 `data/ptcgp_v2.db` 复制一份到 pytest 临时目录
  - 真实跑时不会直接污染主库

## 如何新增一个场景

### 第一步：复制模板

```bash
cp -R src/ptcgp_auto_v2/tests/e2e/scenarios/_template \
  src/ptcgp_auto_v2/tests/e2e/scenarios/<case_id>
```

### 第二步：改 `config.py`

- 改 `case_id`
- 改 `description`
- 改 `task_type`
- 改 `params`
- 不需要的 profile 配置删掉

### 第三步：实现 `core.py` / `device.py`

- 只实现你需要的 profile
- 每个文件只写该 profile 的流程
- 场景文件开头注释必须写清楚在测什么

### 第四步：先跑静态检查

```bash
uv run ruff check src/ptcgp_auto_v2/tests/e2e
```

### 第五步：跑单场景

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id>
```

如果有 `device.py`：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-device <adb> \
  --e2e-account-id <id> \
  --e2e-device-worker-mode real
```

## 如何运行框架

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

跑单场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id>
```

跑单个 device 场景：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-device emulator-5574 \
  --e2e-account-id 350 \
  --e2e-device-worker-mode real
```

## CLI 参数和环境变量

CLI 优先，环境变量兜底。

CLI：
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

- 只对当前 `--e2e-case` 生效
- 不指定 `case` 时禁止 override
- 未知字段直接失败
- `PARAMS__<KEY>` 覆盖 `config.params`

示例：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case <case_id> \
  --e2e-override PARAMS__LEASE_TIMEOUT_SECONDS=4
```

## 日志和排查

日常测试不要直接看整段实时输出。
默认跑法保持 pytest capture，测试结束后只从持久化日志排查。

E2E 运行时会有两类文件：

- `app.log`
  - 应用原生日志，默认 `TRACE`
  - 看 scheduler、executor、锁、ADB 相关日志

- 控制台日志
  - 默认 `ERROR`
  - 通过 `--e2e-console-log-level` 临时调高

- `trace.jsonl`
  - E2E 关键事件
  - 看场景步骤、状态快照、等待超时、故障注入、worker 信号

默认日志文件写到 pytest 临时目录。
pytest 结束时会统一打印本次临时日志根目录。

常用命令：

```bash
rg '"event":"wait_until_timeout"' /path/to/trace.jsonl
rg '"event":"signal_worker_ok"' /path/to/trace.jsonl
rg '"event":"snapshot"' /path/to/trace.jsonl
rg 'Scheduler|DevicePool|stale_thread_timeout|lock' /path/to/app.log
```

日志级别：
- `--e2e-app-log-level`
  - 控制 `app.log` 文件详细度
  - 默认 `TRACE`
- `--e2e-console-log-level`
  - 控制终端输出详细度
  - 默认 `ERROR`
- `--e2e-trace-snapshot-mode`
  - `changes` 只在状态变化时写快照
  - `all` 每次都写

低噪音推荐：

```bash
uv run pytest ... \
  -q \
  --e2e-app-log-level TRACE \
  --e2e-console-log-level ERROR \
  --e2e-trace-snapshot-mode changes
```

## 当前状态

当前分支内置场景：
- `fetch_account_info_completion`
  - `device` profile
