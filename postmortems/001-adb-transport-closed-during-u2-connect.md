# 作用

这份尸检用于记录 `u2.connect()` 因 ADB transport 断链触发 `closed` 后误判为实例失活的问题，以及后续禁止直接重启模拟器的恢复规则。

# adb transport closed during u2 connect

**日期**: 2026-04-12
**影响**: `fetch_account_info` 实机 E2E 无法稳定进入任务执行，失败累计时会误触发模拟器重启。
**发现人**: Codex

## 问题

`AdbController.connect()` 在 `u2.connect()` 初始化阶段遇到 `adbutils.errors.AdbError: closed` 时，没有把它当作可恢复的 ADB transport 断链处理。

## 现象

最小复现命令：

```bash
uv run python - <<'PY'
import uiautomator2 as u2
u2.connect('127.0.0.1:5575')
PY
```

关键报错：

```txt
adbutils.errors.AdbError: closed
```

## 根因

连接路径只重试无障碍服务竞态，没有覆盖 `AdbError` 这类 transport 断链。`connect()` 外层也没有捕获 `AdbError`，异常直接冲出执行器。连接失败计数达到阈值后缺少健康检查，短暂断链会被误判成实例失活。

## 修复

把 `AdbError` 纳入连接阶段的可恢复错误，并在重试前执行 `adb.disconnect/connect` 刷新 transport。重启阈值命中时先检查端口和 `adb shell echo ok`，只有健康检查失败才允许重启模拟器。`snapshot_runtime()` 里同时删掉了已迁移掉的 `run_leases()` 残留依赖，避免实机链路被框架旧接口拦截。

## 预防

连接阶段先区分 transport 断链和实例失活。实机链路失败先做 ADB 健康检查，不允许无证据重启模拟器。迁移 archive 框架后，所有运行时快照接口都必须先和当前 RepositoryFactory 对齐。
