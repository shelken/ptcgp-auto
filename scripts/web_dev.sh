#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/src/ptcgp_auto_v2/web"
WEB_PID=""

if ! command -v npm >/dev/null 2>&1; then
  echo "错误: 未找到 npm，请先安装 Node.js/npm。" >&2
  exit 1
fi

if [ ! -x "$WEB_DIR/node_modules/.bin/tailwindcss" ]; then
  echo "安装 web 前端依赖..."
  npm --prefix "$WEB_DIR" install
fi

echo "构建 Tailwind CSS..."
npm --prefix "$WEB_DIR" run build:css

TAILWIND_BIN="./node_modules/.bin/tailwindcss"

cleanup() {
  if [ -n "$WEB_PID" ]; then
    kill "$WEB_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

echo "启动 Web 服务: http://127.0.0.1:8000"
cd "$ROOT_DIR"
PYTHONPATH=src uvicorn ptcgp_auto_v2.web.app:app --host 127.0.0.1 --port 8000 --reload "$@" &
WEB_PID=$!

sleep 1
if ! kill -0 "$WEB_PID" >/dev/null 2>&1; then
  echo "错误: Web 服务启动失败。" >&2
  wait "$WEB_PID"
  exit 1
fi

echo "启动 Tailwind watch..."
cd "$WEB_DIR"
"$TAILWIND_BIN" \
  -c tailwind.config.js \
  -i static/css/tailwind.input.css \
  -o static/css/tailwind.generated.css \
  --watch
