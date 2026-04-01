# Uvicorn 升级核对（2026-04-01）

- 目标版本：`uvicorn 0.40.0 -> 0.42.0`
- 结论：可以先升，当前项目没有使用这段时间里官方点名废弃或移除的旧接口。

## 影响范围

- `src/ptcgp_auto_v2/main.py`
  - 程序内直接用 `uvicorn.Config` 和 `uvicorn.Server` 启动 Web。
- `src/ptcgp_auto_v2/web/app.py`
  - 本地直接用 `uvicorn.run()` 启动开发 Web。
- `scripts/web_dev.sh`
  - 命令行方式起 `uv run python -m uvicorn ... --reload`

## 变更核对

- `0.41.0`
  - 新增了 worker 相关参数。
  - 修了 `watchfiles` reload 相关问题。
- `0.42.0`
  - 主要是请求体和 websocket 的修复。
- `0.40.0`
  - 只看到移除了 Python 3.9 支持。
- 当前项目要求 `Python >=3.12`，不受影响。
- 当前项目没有使用 `uvicorn.workers`、`Config.setup_event_loop()` 这类已废弃或已移除接口。

## 来源

- https://uvicorn.dev/release-notes/
- https://www.uvicorn.org/settings/
