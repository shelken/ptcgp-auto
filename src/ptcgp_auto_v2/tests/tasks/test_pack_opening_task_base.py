# -*- coding: utf-8 -*-
"""
PackOpeningTaskBase 真实行为测试

使用模块隔离来测试真实的基类方法。
"""

from unittest.mock import Mock

import pytest


@pytest.fixture(scope="module")
def pack_opening_base():
    """提供真实 PackOpeningTaskBase 类。"""
    from ptcgp_auto_v2.tasks.pack_opening_task_base import PackOpeningTaskBase

    yield PackOpeningTaskBase


class TestRealResolveScanSetCode:
    """测试真实基类的 _resolve_scan_set_code 方法"""

    def test_only_inferred_returns_inferred_code(self, pack_opening_base):
        """只有推断上下文时返回推断的 set_code"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = object.__new__(TestTask)
        task._inferred_pack_context = {"set_code": "A1", "booster_name": "Mewtwo"}
        task._target_pack = None

        result = task._resolve_scan_set_code()
        assert result == "A1"

    def test_explicit_overrides_inferred(self, pack_opening_base):
        """显式目标覆盖推断上下文"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

            def get_target_pack_context(self):
                return {"set_code": "A2", "booster_name": "Charizard"}

        task = object.__new__(TestTask)
        task._inferred_pack_context = {"set_code": "A1", "booster_name": "Mewtwo"}

        result = task._resolve_scan_set_code()
        assert result == "A2"

    def test_fixed_overrides_all(self, pack_opening_base):
        """固定代码覆盖所有"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

            def get_fixed_set_code(self):
                return "A3"

            def get_target_pack_context(self):
                return {"set_code": "A2", "booster_name": "Charizard"}

        task = object.__new__(TestTask)
        task._inferred_pack_context = {"set_code": "A1", "booster_name": "Mewtwo"}

        result = task._resolve_scan_set_code()
        assert result == "A3"


class TestRealClearPackInferenceSession:
    """测试真实基类的 _clear_pack_inference_session 方法"""

    def test_clears_context(self, pack_opening_base):
        """清理上下文"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = object.__new__(TestTask)
        task._inferred_pack_context = {"set_code": "A2", "booster_name": "Mewtwo"}

        task._clear_pack_inference_session()

        # 验证上下文被清理
        assert task._inferred_pack_context is None


class TestRealFinalizePackSession:
    """测试真实基类的 finalize_pack_session 方法"""

    def test_calls_clear_session(self, pack_opening_base):
        """finalize_pack_session 调用 _clear_pack_inference_session"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = object.__new__(TestTask)
        task._clear_pack_inference_session = Mock()

        task.finalize_pack_session()

        task._clear_pack_inference_session.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
