from __future__ import annotations

import json
import subprocess
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

    print(f"PARITY_SCORE={score:.2f}")


if __name__ == "__main__":
    main()
