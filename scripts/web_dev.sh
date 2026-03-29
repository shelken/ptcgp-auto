#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_DIR="$ROOT_DIR/src/ptcgp_auto_v2/web"
WEB_PID=""
STOPPING="0"
RUN_WITH_DIRENV="0"
HOST="127.0.0.1"
PORT="8000"
UVICORN_ARGS=()

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      if [ "$#" -lt 2 ]; then
        echo "错误: --host 需要一个参数。" >&2
        exit 1
      fi
      HOST="$2"
      shift 2
      ;;
    --host=*)
      HOST="${1#*=}"
      shift
      ;;
    --port)
      if [ "$#" -lt 2 ]; then
        echo "错误: --port 需要一个参数。" >&2
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    *)
      UVICORN_ARGS+=("$1")
      shift
      ;;
  esac
done

if command -v direnv >/dev/null 2>&1 && [ -f "$ROOT_DIR/.envrc" ]; then
  RUN_WITH_DIRENV="1"
fi

if ! command -v bun >/dev/null 2>&1; then
  echo "错误: 未找到 bun，请先安装 bun。" >&2
  exit 1
fi

echo "校验 React 前端依赖..."
bun install --cwd "$WEB_DIR/frontend" --frozen-lockfile

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

echo "启动 Web 服务: http://$HOST:$PORT"
cd "$ROOT_DIR"
if [ "$RUN_WITH_DIRENV" = "1" ]; then
  direnv exec "$ROOT_DIR" env PTCGP_WEB_DEV=1 PYTHONPATH="$ROOT_DIR/src" \
    uv run python -m uvicorn \
    ptcgp_auto_v2.web.app:app \
    --app-dir "$ROOT_DIR/src" \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --reload-dir src \
    --reload-exclude "src/ptcgp_auto_v2/web/frontend/node_modules/*" \
    --reload-exclude "src/ptcgp_auto_v2/web/frontend/dist/*" \
    --reload-exclude "output/*" \
    --reload-exclude ".git/*" \
    "${UVICORN_ARGS[@]}" &
else
  env PTCGP_WEB_DEV=1 PYTHONPATH="$ROOT_DIR/src" uv run python -m uvicorn \
    ptcgp_auto_v2.web.app:app \
    --app-dir "$ROOT_DIR/src" \
    --host "$HOST" \
    --port "$PORT" \
    --reload \
    --reload-dir src \
    --reload-exclude "src/ptcgp_auto_v2/web/frontend/node_modules/*" \
    --reload-exclude "src/ptcgp_auto_v2/web/frontend/dist/*" \
    --reload-exclude "output/*" \
    --reload-exclude ".git/*" \
    "${UVICORN_ARGS[@]}" &
fi
WEB_PID=$!

sleep 1
if ! kill -0 "$WEB_PID" >/dev/null 2>&1; then
  echo "错误: Web 服务启动失败。" >&2
  wait "$WEB_PID"
  exit 1
fi

wait "$WEB_PID"
