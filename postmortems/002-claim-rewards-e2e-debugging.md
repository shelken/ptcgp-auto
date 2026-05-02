# claim rewards e2e debugging

**日期**: 2026-05-02
**影响**: `claim_rewards` 修复过程中多次误判页面流，导致无效修改、错误 E2E 写法、日志路径混乱和重复实机测试。
**发现人**: 用户

## 问题

修复 `claim_rewards` 时，没有先把页面流抽象清楚，反复把“领取按钮判断”“是否进入主题收藏”“主题收藏返回后如何收尾”混在同一个函数里处理。

同时 E2E 验证阶段误把直接运行任务当成写 E2E 场景，后续又在没有读取固定日志的情况下猜测循环原因，造成多次无效修改。

## 现象

复现命令：

```bash
uv run pytest src/ptcgp_auto_v2/tests/e2e -q \
  --e2e-case claim_rewards_page_flow \
  --e2e-device 127.0.0.1:5625 \
  --e2e-account-id 397 \
  --e2e-device-worker-mode real
```

关键现象：

- 点完 `全部領取` / `領取` 后弹出 OK。
- 点击 OK 后仍停留在任务页。
- 原逻辑看到 `全部領取` 变灰，误判为需要进入 `主題收藏`。
- 从 `主題收藏` 返回任务页后，如果没有保留页面流事实，会再次进入主题收藏。

## 根因

1. 没有区分三个事实：
   - 当前页是否有可领取按钮。
   - 当前页是否需要检查主题收藏。
   - 当前任务页是否刚从“领取后弹窗”或“主题收藏”返回。
2. 错误地把 E2E 验证理解为直接执行任务命令，没有遵循 `tests/e2e/scenarios/<case_id>/device.py` 目录约定。
3. 没有第一时间读取 `.e2e-logs/<case>/<profile>/app.log`，而是猜测页面规则和流程状态。
4. 日志路径设计反复摇摆，出现 `Path.cwd()`、`parents[n]`、项目外目录等错误尝试。

## 修复

- `claim_rewards` 页面流改成小状态机：
  - `claimed_current_rewards_tab`: 当前任务页点过领取后，后续回到任务页只关闭，不再进入主题收藏。
  - `returned_from_theme_collection`: 从主题收藏返回后，任务页只关闭。
- `_click_claim_buttons()` 只负责按钮点击：先 `全部領取`，再单个领取按钮。
- `_needs_theme_collection()` 只负责判断是否要进主题收藏。
- E2E 改为标准 scenario：`claim_rewards_page_flow/device.py`。
- E2E 日志固定在项目内 `.e2e-logs/<case>/<profile>/`。

## 预防

- 修复页面流前，先写出最小状态图；没有状态图不改代码。
- E2E 只允许通过 `tests/e2e/scenarios/<case_id>/` 新增场景，不准新增顶层业务测试脚本。
- 实机 E2E 失败后，第一步必须读 `.e2e-logs/<case>/<profile>/app.log` 和 `trace.jsonl`，不准猜。
- 路径只准使用 `pytestconfig.rootpath`；禁止 `Path.cwd()`、`Path(__file__).resolve().parents[n]`、硬编码 `/tmp`。
- 任务成功不等于验证成功；必须检查日志是否覆盖本次目标路径。
