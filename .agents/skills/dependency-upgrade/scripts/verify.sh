#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

SCOPE="${1:?usage: verify.sh <main|web|image|model|training|all>}"
UV_PYTHON_BIN="${UV_PYTHON:-$(command -v python)}"

run_main() {
    uv run ruff check src main.py main_v2.py debug_tool.py scripts yolo-card-training/scripts
    uv run vulture
}

run_web() {
    run_main
    PYTHONPATH="$ROOT/src" uv run python - <<'PY'
from pathlib import Path
from ptcgp_auto_v2.config.settings import Settings, set_settings
from ptcgp_auto_v2.db.engine import session_scope
from ptcgp_auto_v2.db.repositories import AccountRepository, TaskPlanRepository

settings = Settings()
set_settings(settings)
print({"db_exists": Path(settings.db_path).exists(), "db_path": str(settings.db_path)})
with session_scope() as session:
    account_repo = AccountRepository(session)
    plan_repo = TaskPlanRepository(session)
    accounts = account_repo.get_all()
    plans = plan_repo.get_all()
    page_items, page_total = plan_repo.list_page(
        q="",
        sort_by="id",
        sort_order="asc",
        page=0,
        page_size=10,
    )
    print({
        "accounts": len(accounts),
        "plans": len(plans),
        "page_items": len(page_items),
        "page_total": page_total,
    })
PY

    tmp_log="$(mktemp)"
    PYTHONPATH="$ROOT/src" uv run python -m uvicorn ptcgp_auto_v2.web.app:app \
        --app-dir "$ROOT/src" --host 127.0.0.1 --port 8013 >"$tmp_log" 2>&1 &
    pid=$!
    cleanup() {
        kill "$pid" >/dev/null 2>&1 || true
        wait "$pid" >/dev/null 2>&1 || true
        rm -f "$tmp_log"
    }
    trap cleanup EXIT
    sleep 3
    curl -fsS -o /dev/null -D - -H 'Accept: application/json' http://127.0.0.1:8013/openapi.json
    sed -n '1,80p' "$tmp_log"
}

run_image() {
    run_main
    PYTHONPATH="$ROOT/src" uv run python - <<'PY'
from io import BytesIO
from PIL import Image
from ptcgp_auto_v2.utils.perceptual_hash import pil_to_color_pixels, calculate_perceptual_hash
from ptcgp_auto_v2.utils.pack_image_manager import PackImageManager

img = Image.new("RGBA", (160, 256), (12, 34, 56, 255))
buf = BytesIO()
img.save(buf, format="PNG")
buf.seek(0)
opened = Image.open(buf)
color_pixels = pil_to_color_pixels(opened)
hash_arr = calculate_perceptual_hash(color_pixels)
manager = PackImageManager(base_dir="/tmp/ptcgp-pack-test")
cropped = manager._crop_image(opened)
manager.close()
print({
    "opened_mode": opened.mode,
    "hash_len": int(hash_arr.shape[0]),
    "cropped_size": cropped.size,
    "cropped_mode": cropped.mode,
})
PY
}

run_model() {
    run_main
    PYTHONPATH="$ROOT/src" uv run python - <<'PY'
import ultralytics
from ultralytics import YOLO

model = YOLO("data/models/yolo11n-10k-100-2026.02.08/best.mlpackage", task="obb")
print({
    "ultralytics": ultralytics.__version__,
    "model_type": type(model).__name__,
    "task": getattr(model, "task", None),
})
PY

    UV_PYTHON="$UV_PYTHON_BIN" uv run --project yolo-card-training python - <<'PY'
import ultralytics
from ultralytics import YOLO

print({
    "ultralytics": ultralytics.__version__,
    "yolo_name": YOLO.__name__,
})
PY
}

run_training() {
    UV_PYTHON="$UV_PYTHON_BIN" uv run --project yolo-card-training python - <<'PY'
import cv2
import numpy as np
import requests
import scipy
import tqdm
import ultralytics
from PIL import Image
from scipy.fftpack import dct

img = Image.new("RGB", (32, 32), (5, 6, 7))
arr = np.array(img, dtype=np.float32)
coeff = dct(arr[:, :, 0], type=2, norm="ortho", axis=0)
print({
    "opencv": cv2.__version__,
    "requests": requests.__version__,
    "tqdm": tqdm.__version__,
    "scipy": scipy.__version__,
    "ultralytics": ultralytics.__version__,
    "coeff_shape": tuple(int(v) for v in coeff.shape),
})
PY
}

case "$SCOPE" in
main)
    run_main
    ;;
web)
    run_web
    ;;
image)
    run_image
    ;;
model)
    run_model
    ;;
training)
    run_training
    ;;
all)
    run_web
    run_image
    run_model
    run_training
    ;;
*)
    echo "usage: $0 <main|web|image|model|training|all>" >&2
    exit 1
    ;;
esac
