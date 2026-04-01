#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

SCOPE="${1:-all}"

show_main() {
    echo "== main =="
    uv tree --outdated --depth 1
}

show_training() {
    echo "== yolo-card-training =="
    uv tree --project yolo-card-training --outdated --depth 1
}

case "$SCOPE" in
main)
    show_main
    ;;
training)
    show_training
    ;;
all)
    show_main
    echo
    show_training
    ;;
*)
    echo "usage: $0 [main|training|all]" >&2
    exit 1
    ;;
esac
