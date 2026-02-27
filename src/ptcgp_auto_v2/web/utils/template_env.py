from fastapi.templating import Jinja2Templates

from ptcgp_auto_v2.config.assets import build_card_image_bases
from ptcgp_auto_v2.web.utils.i18n import get_current_i18n


_templates: Jinja2Templates | None = None


class _LazyI18nContext:
    """延迟加载的 i18n 上下文，每次访问时重新计算"""

    def keys(self):
        return ["t", "current_lang"]

    def __getitem__(self, key):
        if key == "t":
            return get_current_i18n()[1]
        if key == "current_lang":
            return get_current_i18n()[0]
        raise KeyError(key)


def init_templates(templates_path: str) -> Jinja2Templates:
    """初始化 Jinja2 模板引擎。"""
    global _templates
    _templates = Jinja2Templates(directory=templates_path)
    _templates.env.globals["build_card_image_bases"] = build_card_image_bases
    # 注册全局上下文处理器，自动注入 t 和 current_lang（延迟计算）
    _templates.env.globals.update(_LazyI18nContext())
    return _templates


def get_templates() -> Jinja2Templates:
    """获取全局模板引擎实例。"""
    if _templates is None:
        raise RuntimeError("模板引擎未初始化")
    return _templates
