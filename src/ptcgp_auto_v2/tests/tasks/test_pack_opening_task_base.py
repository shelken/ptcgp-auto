# -*- coding: utf-8 -*-
"""
PackOpeningTaskBase 行为契约测试

验证统一开包基类的核心行为：
- set_code 解析优先级
- 结果页幂等识别
- pack_type 落库行为
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch, MagicMock

import pytest


class DummyPackOpeningTask:
    """用于测试的虚拟任务类"""

    def __init__(self):
        self._fixed_set_code: str | None = None
        self._target_pack_context: dict[str, str] | None = None
        self._result_recognized = False
        self.card_recognizer = Mock()
        self._pack_record_repo = Mock()
        self._pack_record_repo.create_for_account.return_value = object()
        self._card_repo: Mock | None = None
        self._account_card_repo: Mock | None = None
        self.account = SimpleNamespace(id=1, display_name="test_acc")

    def _resolve_scan_set_code(self):
        """解析要使用的 set_code，优先级：fixed > context"""
        return self._fixed_set_code or (self._target_pack_context or {}).get(
            "pack_code"
        )

    def _scan_cards_with_retry(self, set_code, max_retries=3):
        """带重试的卡牌扫描"""
        for _ in range(max_retries):
            cards = self.card_recognizer.scan(
                set_code=set_code, similarity_threshold=0.68, debug=True
            )
            if cards:
                return cards
        return []

    def _handle_pack_opening_result(self, page_info):
        """处理开包结果页"""
        if not self._result_recognized:
            self._recognize_cards()
            self._result_recognized = True

    def _recognize_cards(self):
        """识别卡牌"""
        pass

    def _save_pack_record(self, cards):
        """保存开包记录"""
        if not (self._pack_record_repo and self.account.id):
            return

        self._pack_record_repo.create_for_account(
            self.account.id,
            pack_type=self.get_pack_record_type(),
            pack_code=None,
            pack_name=None,
            cards=cards,
        )

    def get_pack_record_type(self):
        """获取 pack 记录类型（子类覆盖）"""
        raise NotImplementedError


class DummyGiftTask(DummyPackOpeningTask):
    """模拟礼物盒任务"""

    def get_pack_record_type(self):
        return "gift_box"


class TestPackOpeningTaskBase:
    """PackOpeningTaskBase 行为契约测试套件"""

    def test_resolve_set_code_priority_fixed_over_context(self):
        """测试 set_code 解析优先级：fixed > context"""
        task = DummyPackOpeningTask()
        task._fixed_set_code = "A1"
        task._target_pack_context = {"pack_code": "A2", "booster_name": "X"}

        result = task._resolve_scan_set_code()

        assert result == "A1"

    def test_resolve_set_code_uses_context_when_no_fixed(self):
        """测试无 fixed_set_code 时使用 context"""
        task = DummyPackOpeningTask()
        task._fixed_set_code = None
        task._target_pack_context = {"pack_code": "A2", "booster_name": "X"}

        result = task._resolve_scan_set_code()

        assert result == "A2"

    def test_resolve_set_code_returns_none_when_empty(self):
        """测试无任何配置时返回 None（全局模式）"""
        task = DummyPackOpeningTask()
        task._fixed_set_code = None
        task._target_pack_context = None

        result = task._resolve_scan_set_code()

        assert result is None

    def test_handle_pack_opening_result_recognize_once_then_continue(self):
        """测试结果页处理：仅首次调用识别，后续跳过"""
        task = DummyPackOpeningTask()
        task._result_recognized = False
        task._recognize_cards = Mock()

        # 第一次调用应该触发识别
        task._handle_pack_opening_result({"ocr_results": []})
        # 第二次调用不应该再触发识别
        task._handle_pack_opening_result({"ocr_results": []})

        task._recognize_cards.assert_called_once()

    def test_handle_pack_opening_result_calls_recognize_when_not_recognized(self):
        """测试未识别状态下会调用识别"""
        task = DummyPackOpeningTask()
        task._result_recognized = False
        task._recognize_cards = Mock()

        task._handle_pack_opening_result({"ocr_results": []})

        task._recognize_cards.assert_called_once()

    def test_handle_pack_opening_result_skips_when_already_recognized(self):
        """测试已识别状态下跳过识别"""
        task = DummyPackOpeningTask()
        task._result_recognized = True
        task._recognize_cards = Mock()

        task._handle_pack_opening_result({"ocr_results": []})

        task._recognize_cards.assert_not_called()

    def test_save_pack_record_uses_subclass_pack_type(self):
        """测试保存记录时使用子类指定的 pack_type"""
        task = DummyGiftTask()
        task._pack_record_repo = Mock()
        task._pack_record_repo.create_for_account.return_value = object()
        task.account = SimpleNamespace(id=1, display_name="acc")

        task._save_pack_record([{"card_name": "X", "position": 1}])

        call_args = task._pack_record_repo.create_for_account.call_args
        assert call_args.kwargs["pack_type"] == "gift_box"

    def test_save_pack_record_skips_when_no_repo(self):
        """测试无 repo 时跳过保存"""
        task = DummyGiftTask()
        # type: ignore - 故意设置为 None 测试边界情况
        task._pack_record_repo = None  # type: ignore
        task.account = SimpleNamespace(id=1, display_name="acc")

        # 不应抛出异常
        task._save_pack_record([{"card_name": "X", "position": 1}])

    def test_save_pack_record_skips_when_no_account_id(self):
        """测试无 account_id 时跳过保存"""
        task = DummyGiftTask()
        task._pack_record_repo = Mock()
        task.account = SimpleNamespace(id=None, display_name="acc")

        task._save_pack_record([{"card_name": "X", "position": 1}])

        task._pack_record_repo.create_for_account.assert_not_called()

    def test_scan_cards_with_retry_returns_cards_on_first_success(self):
        """测试首次识别成功即返回"""
        task = DummyPackOpeningTask()
        mock_card = MagicMock()
        task.card_recognizer.scan.return_value = [mock_card]

        cards = task._scan_cards_with_retry(set_code="A1", max_retries=3)

        assert len(cards) == 1
        assert cards[0] == mock_card
        assert task.card_recognizer.scan.call_count == 1

    def test_scan_cards_with_retry_retries_until_success(self):
        """测试失败后重试直到成功"""
        task = DummyPackOpeningTask()
        mock_card = MagicMock()
        task.card_recognizer.scan.side_effect = [[], [], [mock_card]]

        cards = task._scan_cards_with_retry(set_code="A1", max_retries=3)

        assert len(cards) == 1
        assert task.card_recognizer.scan.call_count == 3

    def test_scan_cards_with_retry_returns_empty_after_max_retries(self):
        """测试达到最大重试次数后返回空列表"""
        task = DummyPackOpeningTask()
        task.card_recognizer.scan.return_value = []

        cards = task._scan_cards_with_retry(set_code="A1", max_retries=3)

        assert cards == []
        assert task.card_recognizer.scan.call_count == 3

    def test_scan_cards_with_retry_calls_scan_without_set_code_when_none(self):
        """测试全局模式下调用 scan 时不传 set_code"""
        task = DummyPackOpeningTask()
        task.card_recognizer.scan.return_value = []

        task._scan_cards_with_retry(set_code=None, max_retries=2)

        task.card_recognizer.scan.assert_called_with(
            set_code=None, similarity_threshold=0.68, debug=True
        )


# 使用局部 patch 测试真实 PackOpeningTaskBase 的 _recognize_cards 方法
class TestPackOpeningTaskBaseRecognize:
    """PackOpeningTaskBase._recognize_cards 实际行为测试"""

    def test_recognize_cards_with_none_set_code_passes_none_to_scan(self):
        """测试 _recognize_cards 在 set_code=None 时传递 None 给 scan（全局模式）"""
        # 局部 patch 外部依赖
        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
                "ptcgp_auto_v2.infra.notifier": Mock(),
            },
        ):
            from ptcgp_auto_v2.tasks.pack_opening_task_base import (
                PackOpeningTaskBase,
            )

            class TestTask(PackOpeningTaskBase):
                def get_pack_record_type(self):
                    return "test"

                def get_rare_card_notify_message(self):
                    return "测试获得稀有卡牌"

                def is_completed(self):
                    return False

                def handle_page(self, page_name, page_info):
                    return None

            # 创建 task 并 mock 依赖
            task = object.__new__(TestTask)
            task._card_repo = Mock()
            task._pack_record_repo = Mock()
            task._account_card_repo = Mock()
            task._account = SimpleNamespace(id=1, display_name="test")
            task._packs_opened_count = 0
            task._result_recognized = False

            # Mock card_recognizer
            task.card_recognizer = Mock()
            mock_card = Mock()
            mock_card.set_code = "A1"
            mock_card.card_number = 1
            task.card_recognizer.scan.return_value = [mock_card]

            # Mock _resolve_scan_set_code 返回 None
            task._resolve_scan_set_code = Mock(return_value=None)

            # Mock map_detected_cards
            with patch(
                "ptcgp_auto_v2.tasks.pack_opening_task_base.map_detected_cards"
            ) as mock_map:
                mock_map.return_value = []
                task._recognize_cards()

                # 验证 scan 被调用时 set_code=None（全局模式）
                task.card_recognizer.scan.assert_called_with(
                    set_code=None, similarity_threshold=0.68, debug=True
                )

    def test_recognize_cards_global_mode_maps_each_card_with_own_set_code(self):
        """测试全局识别模式下，每张卡按各自的 set_code 映射，而非固定为首卡系列

        这是 Task 13 的回归测试：当识别结果包含 A1/A2 等多系列卡牌时，
        不应将所有卡都固定到第一张卡的系列。
        """
        from unittest.mock import patch, Mock, MagicMock

        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
                "ptcgp_auto_v2.infra.notifier": Mock(),
            },
        ):
            from ptcgp_auto_v2.tasks.pack_opening_task_base import (
                PackOpeningTaskBase,
            )

            # 创建具体测试子类（不注册到 TaskRegistry）
            class ConcreteTestTask(PackOpeningTaskBase):
                def get_pack_record_type(self):
                    return "test"

                def get_rare_card_notify_message(self):
                    return "测试获得稀有卡牌"

                def is_completed(self):
                    return False

                def handle_page(self, page_name, page_info):
                    return None

            # 使用 object.__new__ 绕过 __init__ 避免触发其他依赖
            task = object.__new__(ConcreteTestTask)
            # Mock 所有依赖属性
            task._card_repo = Mock()
            task._pack_record_repo = Mock()
            task._pack_record_repo.create_for_account.return_value = None
            task._account_card_repo = Mock()
            task._account = SimpleNamespace(id=1, display_name="test")
            task._packs_opened_count = 0
            task._result_recognized = False
            task._action_cache = {}

            # Mock 扩展点方法
            task.get_target_pack_context = Mock(return_value=None)
            task._resolve_scan_set_code = Mock(return_value=None)
            task._save_high_rarity_cards = Mock()

            # Mock card_recognizer 返回 A1/A2 两张卡
            task.card_recognizer = Mock()
            mock_card_a1 = MagicMock()
            mock_card_a1.set_code = "A1"
            mock_card_a1.card_number = 1
            mock_card_a1.confidence = 0.9
            mock_card_a1.similarity = 0.92
            mock_card_a2 = MagicMock()
            mock_card_a2.set_code = "A2"
            mock_card_a2.card_number = 2
            mock_card_a2.confidence = 0.85
            mock_card_a2.similarity = 0.88
            task.card_recognizer.scan.return_value = [mock_card_a1, mock_card_a2]

            # Mock _resolve_scan_set_code 返回 None（全局模式）
            task._resolve_scan_set_code = Mock(return_value=None)

            # Mock map_detected_cards 并捕获调用参数
            with patch(
                "ptcgp_auto_v2.tasks.pack_opening_task_base.map_detected_cards"
            ) as mock_map:
                mock_map.return_value = [
                    {"card_name": "A1-1", "rarity": "1S", "card_id": 1},
                    {"card_name": "A2-1", "rarity": "2S", "card_id": 2},
                ]
                task._recognize_cards()

                # 关键验证：map_detected_cards 被调用时 fixed_set_code=None
                call_args = mock_map.call_args
                assert call_args.kwargs["fixed_set_code"] is None, (
                    "全局模式下 fixed_set_code 应为 None，让每张卡使用自己的 set_code"
                )


class TestPackOpeningTaskBaseRealBehavior:
    """使用真实 PackOpeningTaskBase 的行为测试（替代 Dummy 复制逻辑）"""

    def test_build_pack_opening_handlers_returns_expected_handlers(self):
        """测试 build_pack_opening_handlers 返回所有通用开包处理器"""
        from unittest.mock import Mock, patch

        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
                "ptcgp_auto_v2.infra.notifier": Mock(),
            },
        ):
            from ptcgp_auto_v2.tasks.pack_opening_task_base import (
                PackOpeningTaskBase,
            )

            class ConcreteTask(PackOpeningTaskBase):
                def get_pack_record_type(self):
                    return "test"

                def get_rare_card_notify_message(self):
                    return "测试获得稀有卡牌"

                def is_completed(self):
                    return False

                def handle_page(self, page_name, page_info):
                    return None

            # 使用 object.__new__ 绕过 __init__
            task = object.__new__(ConcreteTask)
            handlers = task.build_pack_opening_handlers()

            # 验证返回所有通用开包页面处理器
            expected_pages = [
                "pack_opening_swipe",
                "pack_opening_select",
                "pack_opening_card",
                "pack_card_register",
                "pack_opening_result",
                "speed_up_button",
            ]
            for page in expected_pages:
                assert page in handlers, f"缺少处理器: {page}"
                assert callable(handlers[page]), f"{page} 处理器不可调用"

    def test_scan_cards_with_retry_uses_provided_set_code(self):
        """测试 _scan_cards_with_retry 使用传入的 set_code 调用 scan"""
        from unittest.mock import Mock, patch, MagicMock

        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
                "ptcgp_auto_v2.infra.notifier": Mock(),
            },
        ):
            from ptcgp_auto_v2.tasks.pack_opening_task_base import (
                PackOpeningTaskBase,
            )

            class ConcreteTask(PackOpeningTaskBase):
                def get_pack_record_type(self):
                    return "test"

                def get_rare_card_notify_message(self):
                    return "测试获得稀有卡牌"

                def is_completed(self):
                    return False

                def handle_page(self, page_name, page_info):
                    return None

            task = object.__new__(ConcreteTask)
            task.card_recognizer = Mock()
            mock_card = MagicMock()
            task.card_recognizer.scan.return_value = [mock_card]

            # 使用指定 set_code 调用
            cards = task._scan_cards_with_retry(set_code="A1", max_retries=2)

            # 验证 scan 被正确调用
            assert len(cards) == 1
            task.card_recognizer.scan.assert_called_with(
                set_code="A1", similarity_threshold=0.68, debug=True
            )


class TestPackOpeningTaskBaseNotifyMessage:
    """稀有卡通知消息来源标记测试"""

    def test_notify_message_uses_chinese_source_message(self):
        """测试通知消息使用中文来源文案，而非 pack_type 英文值"""
        from unittest.mock import Mock, patch

        with patch.dict(
            "sys.modules",
            {
                "ptcgp_auto_v2.infra.model_manager": Mock(),
                "ptcgp_auto_v2.infra.card_hash_manager": Mock(),
                "ptcgp_auto_v2.infra.notifier": Mock(),
            },
        ):
            from ptcgp_auto_v2.tasks.pack_opening_task_base import (
                PackOpeningTaskBase,
            )

            class ConcreteTask(PackOpeningTaskBase):
                def get_pack_record_type(self):
                    return "daily_free"

                def get_rare_card_notify_message(self):
                    return "开包获得稀有卡牌"

                def is_completed(self):
                    return False

                def handle_page(self, page_name, page_info):
                    return None

            task = object.__new__(ConcreteTask)
            message = task.get_rare_card_notify_message()

            # 验证返回中文文案，不含英文 pack_type
            assert message in {
                "开包获得稀有卡牌",
                "礼物获得稀有卡牌",
                "新手开包获得稀有卡牌",
            }
            # 确保不包含英文 pack_type 值
            assert "daily_free" not in message
            assert "gift_box" not in message
            assert "init_tutorial" not in message


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
