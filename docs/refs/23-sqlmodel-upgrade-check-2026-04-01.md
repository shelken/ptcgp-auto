# SQLModel 升级核对（2026-04-01）

- 目标版本：`sqlmodel 0.0.31 -> 0.0.37`
- 结论：可以升级，已知对当前项目最相关的是 `0.0.32` 对新 Pydantic 的兼容修复。

## 影响范围

- `src/ptcgp_auto_v2/db/models/*`
  - 全部 ORM 模型都基于 `SQLModel`。
- `src/ptcgp_auto_v2/db/engine.py`
  - 使用 `Session` 和 `create_engine`。
- `src/ptcgp_auto_v2/db/repositories/*`
  - 广泛使用 `select()`、`col()`、`func()`、`session.exec()`。
- `src/ptcgp_auto_v2/web/routers/*`
  - 大量通过 `Depends(get_fastapi_session)` 注入 `Session`。

## 官方变更核对

- `0.0.32`
  - 修复 `Annotated` 字段在 Pydantic 2.12+ 下的兼容问题。
- `0.0.35`
  - 只是不再支持 Python 3.9。
- `0.0.36`、`0.0.37`
  - 主要是打包和内部构建调整。
- 当前项目运行在 Python 3.13，且已经使用 Pydantic 2.x，因此从说明上看这次升级方向是正向的。

## 验证策略

- 跑 `ruff`
- 跑 `vulture`
- 真实打开当前数据库
- 通过 Repository 跑账号、计划、分页等读库动作
- 启动 Web，确认 `openapi.json` 还能正常生成

## 来源

- https://sqlmodel.tiangolo.com/release-notes/
- https://github.com/sqlmodel/sqlmodel/releases
