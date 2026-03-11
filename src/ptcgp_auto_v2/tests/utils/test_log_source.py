# -*- coding: utf-8 -*-
"""日志来源解析测试。"""

import ptcgp_auto_v2.utils.log_source as log_source


def test_resolve_log_device_prefers_auto_display_name(monkeypatch):
    """命中 auto 实例时应优先显示实例名。"""
    monkeypatch.setattr(
        log_source,
        "list_manageable_instances",
        lambda prefix="auto-": {
            5555: ("Tiramisu64_20", "auto-1"),
        },
    )

    device, color_key = log_source.resolve_log_device("127.0.0.1:5555", "auto-")

    assert device == "auto-1"
    assert color_key == "5555"


def test_resolve_log_device_falls_back_to_port(monkeypatch):
    """未命中 auto 实例时应回退到端口。"""
    monkeypatch.setattr(
        log_source,
        "list_manageable_instances",
        lambda prefix="auto-": {},
    )

    device, color_key = log_source.resolve_log_device("127.0.0.1:5655", "auto-")

    assert device == "5655"
    assert color_key == "5655"
