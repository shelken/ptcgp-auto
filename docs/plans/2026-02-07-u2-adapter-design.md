# uiautomator2 适配与滑动语义设计

## 用户原始诉求（原文）

adb现在我想从adbutils改成uiautomator2

uiautomator2中关于滑动的概念有些和当前不一样，他那个是匀速滑动，steps，我这边是开始到终点然后用时长来限制速度。如何变更

因为我还想要双指缩放，因为adbutils不支持，所以打算所有换成u2

## 目标与范围

- 目标：完整替换设备适配层为 uiautomator2，支持双指缩放；滑动语义从 duration 切换为 steps，并采用相对 steps（按距离比例缩放）。
- 范围：`src/ptcgp_auto_v2/infra/adb.py`（保留类名 `AdbController`，内部实现替换）、`src/ptcgp_auto_v2/utils/gesture.py`（滑动入口与步数计算），以及调用点适配。
- 非目标：不改动任务调度逻辑与页面识别规则。

## 关键差异与结论

- adbutils：`swipe(start, end, duration)` 通过时长控制速度，duration 越短越快。
- uiautomator2：`swipe(start, end, steps)` 通过步数控制速度，steps 越少越快；且速度与设备帧率相关。
- 结论：需要定义“相对 steps”模型，按距离/屏幕高度比例换算实际 steps，避免长距离滑动过慢。

## 设计方案

### 1) 保留类名，替换内部实现

- 保留 `AdbController` 名称，避免大范围重构。
- 内部替换为 `uiautomator2.Device`，对外接口尽量保持不变。

### 2) 滑动语义迁移（相对 steps）

统一使用 steps：

- `swipe(x1, y1, x2, y2, steps)`
- `steps = clamp(min_steps, max_steps, base_steps * (distance_ratio / base_ratio))`
- `distance_ratio = distance_px / screen_height`

默认基准（快档）：

- `base_ratio = 0.25`（屏幕高度的 25%）
- `base_steps = 8`
- `min_steps = 6`
- `max_steps = 24`

### 3) 多指缩放能力

新增接口：

- `pinch_in(center, scale, steps)`
- `pinch_out(center, scale, steps)`

参数以“中心点 + 比例 + steps”定义，业务层不直接拼轨迹。

### 4) 坐标与尺寸

- `scaled_x/y`、`center_x/y` 基于 `device.window_size()` 计算并缓存。
- 继续使用 1080x1920 基准像素与缩放函数，避免改动现有业务坐标逻辑。

## 数据流

```
业务任务 -> gesture(动作编排) -> AdbController(原子动作) -> u2 设备
```

## 错误处理

- 设备未连接、截图失败、输入失败时记录中文日志并返回。
- u2 常见连接错误可做一次轻量重试（配置开关，默认关闭）。

## 测试策略

- 统一测试桩接口（FakeAdb/FakeU2Device）包含 `click/swipe/screenshot/window_size/press/send_keys/long_click`。
- 重点覆盖：steps 计算、滑动路径一致性、多指缩放参数。

## 迁移步骤

1) 替换 `AdbController` 内部实现为 u2，删除 duration 语义。
2) `gesture` 层统一 steps 入口与相对 steps 计算。
3) 更新调用点与测试桩。
4) 增加 pinch 接口并试点验证。

## 当前进度

- 2026-02-07：已完成 pinch 接口；试点调用按用户要求移除（待确认是否需要指定试点页面）。

## 本次流程中出现的问题与经验

- 全量 pytest 存在跨目录重复测试文件名导致收集冲突（`tests/test_account_card_repository.py` 与 `src/ptcgp_auto_v2/tests/db/test_account_card_repository.py`）。
- 测试桩缺少新接口（如 `scaled_y`、`swipe`）导致失败，后续需统一 FakeAdb 接口。
- 工作区有未提交改动时合并被阻塞，需要提前选择 stash 或临时 worktree。
- 迁移滑动语义时，u2 的 steps 与体感速度差异显著，需要通过基准比例与基准步数校准。
