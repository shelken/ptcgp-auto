"""Web E2E 专用 FastAPI app bootstrap。"""

from pathlib import Path
import os

from ptcgp_auto_v2.tests.e2e.harness import rebind_test_runtime
from ptcgp_auto_v2.tests.e2e.seed_web_db import validate_web_e2e_db_path
from ptcgp_auto_v2.web.app import create_app

DB_PATH_ENV = "PTCGP_WEB_E2E_DB_PATH"


def _require_e2e_db_path() -> Path:
    raw_path = os.getenv(DB_PATH_ENV, "").strip()
    if not raw_path:
        raise RuntimeError(f"{DB_PATH_ENV} 必须指向隔离 Web E2E 数据库")
    db_path = validate_web_e2e_db_path(Path(raw_path))
    if not db_path.exists():
        raise RuntimeError(f"Web E2E 数据库不存在: {db_path}")
    return db_path


# 变更原因：Web E2E 必须绑定隔离测试库，避免读取默认生产/本地 data/ptcgp_v2.db。
rebind_test_runtime(_require_e2e_db_path(), [])
app = create_app()
