# -*- coding: utf-8 -*-

from pathlib import Path
import re


ONERROR_ATTR_PATTERN = re.compile(r'onerror="([^"]+)"')


def test_image_onerror_handlers_should_unbind_self_before_fallback():
    """图片 onerror 内联处理必须先 this.onerror=null，避免错误事件重复触发。"""
    template_paths = [
        Path("src/ptcgp_auto_v2/web/templates/partials/owned_card_list.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/notification_list_items.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/owned_card_detail.html"),
        Path("src/ptcgp_auto_v2/web/templates/partials/modals/card_picker_modal.html"),
    ]

    missing_unbind = []
    for path in template_paths:
        content = path.read_text(encoding="utf-8")
        handlers = ONERROR_ATTR_PATTERN.findall(content)
        for index, handler in enumerate(handlers):
            if "this.onerror=null" not in handler.replace(" ", ""):
                missing_unbind.append(f"{path}:{index + 1}")

    assert not missing_unbind, (
        "以下 onerror 处理器未先执行 this.onerror=null，存在重复触发风险: "
        + ", ".join(missing_unbind)
    )
