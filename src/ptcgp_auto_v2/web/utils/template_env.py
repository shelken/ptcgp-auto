from fastapi.templating import Jinja2Templates


_templates: Jinja2Templates | None = None


def init_templates(templates_path: str) -> Jinja2Templates:
    """初始化 Jinja2 模板引擎。"""
    global _templates
    _templates = Jinja2Templates(directory=templates_path)
    return _templates


def get_templates() -> Jinja2Templates:
    """获取全局模板引擎实例。"""
    if _templates is None:
        raise RuntimeError("模板引擎未初始化")
    return _templates
