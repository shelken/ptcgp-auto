# -*- coding: utf-8 -*-

import importlib


def test_image_manager_assets_base_url_follows_default_locale(monkeypatch):
    """图片资源基地址应跟随 DEFAULT_LOCALE 切换，避免写死语言。"""
    from ptcgp_auto_v2.config import lang as lang_config

    monkeypatch.setattr(lang_config, "DEFAULT_LOCALE", "en_US")

    # 重新加载模块以触发常量初始化
    image_manager = importlib.import_module("ptcgp_auto_v2.utils.image_manager")
    image_manager = importlib.reload(image_manager)
    assert "/en-US/" in image_manager.ASSETS_BASE_URL
