import sys
import os

# Add the src directory to sys.path to allow importing ptcgp_auto_v2
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.abspath(os.path.join(current_dir, "../.."))
sys.path.append(src_dir)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ptcgp_auto_v2.config.rarity_icons import get_rarity_display
from ptcgp_auto_v2.web.utils.i18n import init_i18n, detect_lang, set_lang_context
from ptcgp_auto_v2.web.utils.template_env import init_templates
from ptcgp_auto_v2.web.utils.view_helpers import format_datetime

from ptcgp_auto_v2.web.routers import (
    index,
    records,
    owned_cards,
    tasks,
    management,
    plans,
    metadata,
    pack_config,
    friendship,
    daily_gift,
    exchange_card,
    notifications,
)

# 导入任务模块以触发注册
import ptcgp_auto_v2.tasks


app = FastAPI(title="PTCGP Auto Web")


# 静态资源挂载
static_path = os.path.join(current_dir, "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

# 模板初始化
templates_path = os.path.join(current_dir, "templates")
templates = init_templates(templates_path)
templates.env.filters["datetime"] = format_datetime
templates.env.filters["rarity_display"] = get_rarity_display

# 多语言初始化
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


# 路由挂载
app.include_router(index.router)
app.include_router(records.router)
app.include_router(owned_cards.router)
app.include_router(tasks.router)
app.include_router(management.router)
app.include_router(plans.router)
app.include_router(metadata.router)
app.include_router(pack_config.router)
app.include_router(friendship.router)
app.include_router(daily_gift.router)
app.include_router(exchange_card.router)
app.include_router(notifications.router)


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
