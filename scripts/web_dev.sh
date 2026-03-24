#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/src/ptcgp_auto_v2/web"
WEB_PID=""
STOPPING="0"

if ! command -v bun >/dev/null 2>&1; then
  echo "错误: 未找到 bun，请先安装 bun。" >&2
  exit 1
fi

if [ ! -d "$WEB_DIR/frontend/node_modules" ]; then
  echo "安装 React 前端依赖..."
  bun install --cwd "$WEB_DIR/frontend"
fi

echo "构建 React 前端..."
bun run --cwd "$WEB_DIR/frontend" build

cleanup() {
  if [ "$STOPPING" = "1" ]; then
    return
  fi
  STOPPING="1"
  trap - EXIT INT TERM

  if [ -n "$WEB_PID" ]; then
    pkill -TERM -P "$WEB_PID" >/dev/null 2>&1 || true
    kill -TERM "$WEB_PID" >/dev/null 2>&1 || true
    wait "$WEB_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "启动 Web 服务: http://127.0.0.1:8000"
cd "$ROOT_DIR"
PTCGP_WEB_DEV=1 PYTHONPATH=src uvicorn ptcgp_auto_v2.web.app:app --host 127.0.0.1 --port 8000 --reload "$@" &
WEB_PID=$!

sleep 1
if ! kill -0 "$WEB_PID" >/dev/null 2>&1; then
  echo "错误: Web 服务启动失败。" >&2
  wait "$WEB_PID"
  exit 1
fi

wait "$WEB_PID"
