# ruff: noqa: E402
import os
import sys

# Add the src directory to sys.path to allow importing ptcgp_auto_v2
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(src_dir)

from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from ptcgp_auto_v2.web.routers import (
    index,
    react_api,
)
from ptcgp_auto_v2.web.utils.i18n import init_i18n, detect_lang, set_lang_context

# 导入任务模块以触发注册
import ptcgp_auto_v2.tasks  # noqa: F401


app = FastAPI(title="PTCGP Auto Web")


# React 构建产物挂载（Vite 输出的 /assets/*）
frontend_assets_path = os.path.join(current_dir, "frontend", "dist", "assets")
app.mount(
    "/assets",
    StaticFiles(directory=frontend_assets_path, check_dir=False),
    name="frontend-assets",
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """避免浏览器默认 favicon 请求产生 404 噪音。"""
    return Response(status_code=204)

# 多语言初始化（必须在模板初始化之前）
locales_dir = os.path.join(current_dir, "locales")
init_i18n(locales_dir)

@app.middleware("http")
async def set_request_lang_context(request, call_next):
    """统一在中间件设置语言上下文，路由层不再单独处理。"""
    explicit_lang = request.query_params.get("lang")
    current_lang = detect_lang(request, explicit_lang)
    set_lang_context(current_lang)
    response = await call_next(request)
    return response


@app.middleware("http")
async def set_static_cache_control_for_dev(request, call_next):
    """开发模式下禁用前端资源缓存，避免修改后页面不生效。"""
    response = await call_next(request)
    if os.getenv("PTCGP_WEB_DEV") != "1":
        return response
    if not request.url.path.startswith("/assets/"):
        return response
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# 路由挂载
app.include_router(index.router)
app.include_router(react_api.router)


if __name__ == "__main__":
    # 初始化数据库
    from ptcgp_auto_v2.db.connection import get_database

    get_database()

    # 初始化 Settings
    from ptcgp_auto_v2.config.settings import Settings, set_settings

    settings = Settings()
    set_settings(settings)
    settings.configure_logging()

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
