# -*- coding: utf-8 -*-
"""响应构建工具。

提供统一的模板响应渲染函数。
"""

import json
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse

from ptcgp_auto_v2.web.utils.template_env import get_templates


def render_template(
    request: Request,
    template_name: str,
    context: dict[str, Any],
) -> HTMLResponse:
    """统一模板渲染函数。

    自动注入 request 到 context，所有 router 必须使用此函数。

    Args:
        request: FastAPI 请求对象
        template_name: 模板路径，如 "partials/account_list.html"
        context: 模板上下文数据

    Returns:
        HTMLResponse 对象
    """
    context["request"] = request
    templates = get_templates()
    return templates.TemplateResponse(template_name, context)
