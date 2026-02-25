from fastapi.templating import Jinja2Templates

from ptcgp_auto_v2.config.assets import build_card_image_bases


_templates: Jinja2Templates | None = None


def init_templates(templates_path: str) -> Jinja2Templates:
    """初始化 Jinja2 模板引擎。"""
    global _templates
    _templates = Jinja2Templates(directory=templates_path)
    _templates.env.globals["build_card_image_bases"] = build_card_image_bases
    return _templates


def get_templates() -> Jinja2Templates:
    """获取全局模板引擎实例。"""
    if _templates is None:
        raise RuntimeError("模板引擎未初始化")
    return _templates
