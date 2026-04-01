# FastAPI 升级核对（2026-04-01）

- 目标版本：`fastapi 0.128.0 -> 0.135.2`
- 结论：当前项目可以升级，但要重点盯住 JSON 请求头检查。

## 影响范围

- `src/ptcgp_auto_v2/web/app.py`
  - 直接创建 `FastAPI()` 应用并注册中间件和路由。
- `src/ptcgp_auto_v2/web/routers/*.py`
  - 广泛使用 `APIRouter`、`Depends`、`HTTPException`、`Query`、`Request`。
- `src/ptcgp_auto_v2/web/frontend/src/lib/api.ts`
  - 当前前端发 JSON 请求时会显式带 `Content-Type: application/json`。

## 变更核对

- `0.132.0`
  - 新增 JSON 请求的 `strict_content_type` 检查。
  - 如果客户端发 JSON 却不带正确 `Content-Type`，会被拒绝。
- `0.134.0`
  - 引入新的流式响应能力，并提升 `Starlette` 最低版本要求。
- `0.135.2`
  - 主要是提升 `pydantic` 最低版本要求到 `>=2.9.0`。
- 当前锁文件里的 `pydantic` 已是 `2.12.5`，`starlette` 已是 `0.50.0`，满足要求。
- 当前项目前端统一通过 `src/lib/api.ts` 发 JSON，请求头已满足新要求。

## 来源

- https://fastapi.tiangolo.com/release-notes/
- https://fastapi.tiangolo.com/reference/apirouter/
