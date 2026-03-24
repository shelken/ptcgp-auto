# Web 模块协作指引（React 重构版）

## 当前架构

`src/ptcgp_auto_v2/web/` 已完成前后端重构：

- 后端：FastAPI（仅提供 JSON API）
- 前端：React + TypeScript + shadcn/ui + Tailwind + TanStack Query + React Router
- 包管理：Bun
- 已移除：HTMX、Jinja2 模板、旧静态 JS/CSS 资产

目录结构：

```
src/ptcgp_auto_v2/web/
├── app.py
├── routers/
│   ├── index.py         # React 入口与 bootstrap
│   └── react_api.py     # React 专用 JSON API
├── frontend/
│   ├── src/
│   ├── index.html
│   └── package.json
├── services/
├── queries/
├── locales/
└── utils/
```

## 开发规范

- 所有新接口必须返回 JSON，不允许回退 HTML 片段。
- 前端数据请求统一走 TanStack Query。
- 页面路由统一走 React Router（HashRouter）。
- Web 启动与构建统一使用 Bun，不再使用 web 根目录 npm/tailwind 旧流程。

## 常用命令

```bash
# 构建前端
bun run --cwd src/ptcgp_auto_v2/web/frontend build

# 启动 Web（开发）
./scripts/web_dev.sh

# Python 代码检查
PYTHONPATH=src uv run ruff check src/ptcgp_auto_v2/web
```

## 验收要求

- 后端：`ruff check` 通过。
- 前端：`bun build` 通过。
- 页面：`#/records`、`#/owned-cards`、`#/management/*` 全部可访问，控制台与网络无 4xx/5xx 异常。
