#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

TOPIC="${1:?usage: prepare_report.sh <topic>}"
DATE_PREFIX="${UPGRADE_DATE:-$(date +%F)}"
REPORT_DIR="docs/upgrade"

mkdir -p "$REPORT_DIR"

find "$REPORT_DIR" -maxdepth 1 -type f -name '*.md' \
    ! -name 'README.md' \
    ! -name "${DATE_PREFIX}-*.md" \
    -print -delete

SAFE_TOPIC="${TOPIC// /-}"
SAFE_TOPIC="${SAFE_TOPIC//\//-}"
SAFE_TOPIC="${SAFE_TOPIC//:/-}"
REPORT_PATH="$REPORT_DIR/${DATE_PREFIX}-${SAFE_TOPIC}.md"

if [ ! -f "$REPORT_PATH" ]; then
    printf '# %s\n\n' "$TOPIC" >"$REPORT_PATH"
fi

printf '%s\n' "$REPORT_PATH"
