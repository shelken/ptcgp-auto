from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.request
from pathlib import Path


def has_all_dependencies(package_json: dict) -> bool:
    deps = package_json.get("dependencies", {})
    dev_deps = package_json.get("devDependencies", {})
    required_deps = {
        "react",
        "react-dom",
        "react-router-dom",
        "@tanstack/react-query",
        "class-variance-authority",
        "@radix-ui/react-slot",
        "tailwind-merge",
        "clsx",
    }
    required_dev_deps = {
        "typescript",
        "vite",
        "tailwindcss",
    }
    return required_deps.issubset(deps) and required_dev_deps.issubset(dev_deps)


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_smoke_check(root: Path) -> bool:
    """启动本地服务并验证关键页面可访问。"""
    port = _find_free_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = "src"
    server = subprocess.Popen(
        [
            "uv",
            "run",
            "python",
            "-m",
            "uvicorn",
            "ptcgp_auto_v2.web.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=root,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        root_html = ""
        bootstrap_json = ""
        legacy_html = ""
        accounts_html = ""
        for _ in range(30):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as resp:
                    root_html = resp.read().decode("utf-8", errors="ignore")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/react/bootstrap?lang=zh_CN",
                    timeout=2,
                ) as resp:
                    bootstrap_json = resp.read().decode("utf-8", errors="ignore")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/legacy?lang=zh_CN",
                    timeout=2,
                ) as resp:
                    legacy_html = resp.read().decode("utf-8", errors="ignore")
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/management/accounts?lang=zh_CN",
                    timeout=2,
                ) as resp:
                    accounts_html = resp.read().decode("utf-8", errors="ignore")
                break
            except Exception:
                time.sleep(0.2)

        if not root_html or not bootstrap_json or not legacy_html or not accounts_html:
            return False

        return (
            '<div id="root"></div>' in root_html
            and '"options"' in bootstrap_json
            and "htmx.org" in legacy_html
            and len(accounts_html.strip()) > 100
        )
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    frontend_root = root / "src" / "ptcgp_auto_v2" / "web" / "frontend"

    score = 0.0

    if frontend_root.exists():
        score += 20

    package_json_path = frontend_root / "package.json"
    if package_json_path.exists():
        score += 10
        package_json = json.loads(package_json_path.read_text(encoding="utf-8"))
        if has_all_dependencies(package_json):
            score += 25

    required_files = [
        frontend_root / "src" / "main.tsx",
        frontend_root / "src" / "App.tsx",
        frontend_root / "src" / "components" / "ui" / "button.tsx",
        frontend_root / "src" / "components" / "ui" / "card.tsx",
        frontend_root / "tailwind.config.ts",
        frontend_root / "vite.config.ts",
    ]
    if all(path.exists() for path in required_files):
        score += 20

    route_constants = frontend_root / "src" / "lib" / "constants.ts"
    if route_constants.exists():
        content = route_constants.read_text(encoding="utf-8")
        required_route_keys = [
            "records",
            "owned-cards",
            "management/accounts",
            "management/plans",
            "management/resources",
            "management/tasks",
            "management/metadata",
            "management/daily-gift",
            "management/friendships",
            "management/exchange-cards",
            "management/notifications",
        ]
        if all(key in content for key in required_route_keys):
            score += 15

    bun_lock = frontend_root / "bun.lock"
    if bun_lock.exists():
        score += 10

    index_router = root / "src" / "ptcgp_auto_v2" / "web" / "routers" / "index.py"
    if index_router.exists():
        router_content = index_router.read_text(encoding="utf-8")
        if "/api/react/bootstrap" in router_content:
            score += 15
        if "frontend" in router_content and "dist" in router_content and "FileResponse" in router_content:
            score += 10

    page_files = [
        frontend_root / "src" / "pages" / "records-page.tsx",
        frontend_root / "src" / "pages" / "owned-cards-page.tsx",
        frontend_root / "src" / "pages" / "management-page.tsx",
        frontend_root / "src" / "components" / "html-fragment.tsx",
    ]
    if all(path.exists() for path in page_files):
        score += 10

    tracked_node_modules = subprocess.run(
        ["git", "ls-files", "src/ptcgp_auto_v2/web/frontend/node_modules"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if tracked_node_modules.returncode == 0 and not tracked_node_modules.stdout.strip():
        score += 10

    build_check = subprocess.run(
        ["bun", "run", "--cwd", str(frontend_root), "build"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if build_check.returncode == 0:
        score += 15

    generated_artifacts = subprocess.run(
        [
            "git",
            "ls-files",
            "src/ptcgp_auto_v2/web/frontend/src/*.js",
            "src/ptcgp_auto_v2/web/frontend/src/**/*.js",
            "src/ptcgp_auto_v2/web/frontend/*.tsbuildinfo",
            "src/ptcgp_auto_v2/web/frontend/vite.config.js",
            "src/ptcgp_auto_v2/web/frontend/vite.config.d.ts",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if generated_artifacts.returncode == 0 and not generated_artifacts.stdout.strip():
        score += 20

    if run_smoke_check(root):
        score += 20

    print(f"PARITY_SCORE={score:.2f}")


if __name__ == "__main__":
    main()
