# -*- coding: utf-8 -*-
"""
TemplateMatcher 测试

测试模板匹配器功能，特别是动态模板卸载能力。
"""

import pytest
import numpy as np
from unittest.mock import patch, MagicMock

from ptcgp_auto_v2.infra.template import TemplateMatcher


@pytest.fixture
def template_matcher():
    """创建模板匹配器实例"""
    with patch.object(TemplateMatcher, "load_core_templates"):
        matcher = TemplateMatcher(templates_dir="templates")
        return matcher


class TestDynamicTemplateUnloading:
    """动态模板卸载测试"""

    def test_unload_templates_removes_loaded_pack_templates(self, template_matcher):
        """测试批量卸载模板"""
        # 模拟加载模板
        template_matcher.templates["packs_auto/Mewtwo"] = np.zeros((10, 10, 3))
        template_matcher.templates["packs_auto/Charizard"] = np.zeros((10, 10, 3))
        template_matcher._loaded_pack_templates = [
            "packs_auto/Mewtwo",
            "packs_auto/Charizard",
        ]

        # 执行卸载
        removed = template_matcher.unload_templates(
            [
                "packs_auto/Mewtwo",
                "packs_auto/Charizard",
            ]
        )

        assert removed == 2
        assert "packs_auto/Mewtwo" not in template_matcher.templates
        assert "packs_auto/Charizard" not in template_matcher.templates
        assert len(template_matcher._loaded_pack_templates) == 0

    def test_unload_templates_only_removes_specified(self, template_matcher):
        """测试只卸载指定的模板"""
        # 模拟加载多个模板
        template_matcher.templates["packs_auto/Mewtwo"] = np.zeros((10, 10, 3))
        template_matcher.templates["packs_auto/Charizard"] = np.zeros((10, 10, 3))
        template_matcher.templates["core/home"] = np.zeros((10, 10, 3))
        template_matcher._loaded_pack_templates = [
            "packs_auto/Mewtwo",
            "packs_auto/Charizard",
        ]

        # 只卸载 Mewtwo
        removed = template_matcher.unload_templates(["packs_auto/Mewtwo"])

        assert removed == 1
        assert "packs_auto/Mewtwo" not in template_matcher.templates
        assert "packs_auto/Charizard" in template_matcher.templates
        assert "core/home" in template_matcher.templates
        assert "packs_auto/Charizard" in template_matcher._loaded_pack_templates

    def test_unload_templates_returns_zero_for_nonexistent(self, template_matcher):
        """测试卸载不存在的模板返回0"""
        template_matcher.templates["core/home"] = np.zeros((10, 10, 3))

        removed = template_matcher.unload_templates(["packs_auto/NonExistent"])

        assert removed == 0
        assert "core/home" in template_matcher.templates

    def test_unload_templates_normalizes_names(self, template_matcher):
        """测试模板名称规范化"""
        template_matcher.templates["packs_auto/Mewtwo"] = np.zeros((10, 10, 3))
        template_matcher._loaded_pack_templates = ["packs_auto/Mewtwo"]

        # 使用带 .png 后缀的名称
        removed = template_matcher.unload_templates(["packs_auto/Mewtwo.png"])

        assert removed == 1
        assert "packs_auto/Mewtwo" not in template_matcher.templates
