from fastapi import Request
from fastapi.templating import Jinja2Templates

from ptcgp_auto_v2.config.assets import build_card_image_bases
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


_templates: Jinja2Templates | None = None


def _template_context_processor(_: Request) -> dict:
    """按请求注入 i18n 上下文。"""
    current_lang, t = get_current_i18n()
    return {
        "t": t,
        "current_lang": current_lang,
    }


def init_templates(templates_path: str) -> Jinja2Templates:
    """初始化 Jinja2 模板引擎。"""
    global _templates
    templates = Jinja2Templates(
        directory=templates_path,
        context_processors=[_template_context_processor],
    )
    templates.env.globals["build_card_image_bases"] = build_card_image_bases
    _templates = templates
    return templates


def get_templates() -> Jinja2Templates:
    """获取全局模板引擎实例。"""
    if _templates is None:
        raise RuntimeError("模板引擎未初始化")
    return _templates
