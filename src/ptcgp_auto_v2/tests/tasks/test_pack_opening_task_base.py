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


class TestRealMultiPackBehavior:
    """测试真实基类的 10 包结果行为。"""

    @staticmethod
    def _make_result_card(card_id: int, x: float, y: float) -> dict:
        """构造结果页测试卡牌。"""
        return {
            "card_id": card_id,
            "set_code": "A1",
            "card_number": card_id,
            "center_x": x,
            "center_y": y,
            "position": 1,
            "confidence": 0.9,
        }

    def test_build_pack_opening_pages_includes_multi_pack_result(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tasks.pack_opening_task_base import build_pack_opening_pages

        pages = build_pack_opening_pages()

        assert any(page["name"] == "pack_opening_multi_result" for page in pages)

    def test_handle_opening_swipe_counts_ten_pack_once(self, pack_opening_base):
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
                return {"set_code": "A1", "booster_name": "Mewtwo"}

        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._set_pack_result_mode(10)

        task._handle_opening_swipe({})
        task._handle_opening_swipe({})

        assert task._packs_opened_count == 10

    def test_collect_multi_pack_rows_should_continue_after_single_row_reaches_twenty(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

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
        task.adb = FakeAdb()
        task._pack_result_batch_size = 10
        task._pack_result_rows = [
            [
                self._make_result_card(index * 10 + 1, 248.0, float(index * 40)),
                self._make_result_card(index * 10 + 2, 470.0, float(index * 40)),
            ]
            for index in range(19)
        ]
        task._resolve_scan_set_code = Mock(return_value="A1")
        task._scan_cards_with_retry = Mock(side_effect=[[{"frame": 1}], [{"frame": 2}]])
        task._group_result_rows = Mock(
            side_effect=[
                [[self._make_result_card(999, 470.0, 999.0)]],
                [
                    [
                        self._make_result_card(998, 248.0, 999.0),
                        self._make_result_card(999, 470.0, 999.0),
                    ]
                ],
            ]
        )

        result = task._collect_multi_pack_rows()

        assert result is True
        assert task._scan_cards_with_retry.call_count == 2
        assert len(task._pack_result_rows) == 20
        assert [card["card_id"] for card in task._pack_result_rows[-1]] == [998, 999]

    def test_collect_multi_pack_rows_should_stop_after_same_screen_repeats(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

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
        task.adb = FakeAdb()
        task._pack_result_batch_size = 10
        task._pack_result_rows = [
            [
                self._make_result_card(index * 10 + 1, 248.0, float(index * 40)),
                self._make_result_card(index * 10 + 2, 470.0, float(index * 40)),
            ]
            for index in range(19)
        ]
        single_row = [[self._make_result_card(999, 470.0, 999.0)]]
        task._resolve_scan_set_code = Mock(return_value="A1")
        task._scan_cards_with_retry = Mock(side_effect=[[{"frame": 1}], [{"frame": 2}]])
        task._group_result_rows = Mock(side_effect=[single_row, single_row])

        result = task._collect_multi_pack_rows()

        assert result is False
        assert task._scan_cards_with_retry.call_count == 2
        assert len(task._pack_result_rows) == 20
        assert [card["card_id"] for card in task._pack_result_rows[-1]] == [999]

    def test_recognize_multi_pack_results_saves_ten_records(self, pack_opening_base):
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
        task._init_repositories = Mock()
        task._collect_multi_pack_rows = Mock(return_value=True)
        task._reset_pack_result_mode = Mock()
        task._save_pack_record = Mock()
        task._save_high_rarity_cards = Mock()
        task._account_card_repo = Mock()
        task._account = Mock()
        task._account.id = 1
        task._pack_result_batch_size = 10
        task._pack_result_rows = []
        task._result_recognized = False

        for pack_index in range(10):
            base_card_id = pack_index * 10
            base_y = float(pack_index * 100)
            task._pack_result_rows.append(
                [
                    {
                        "card_id": base_card_id + 1,
                        "center_x": 100.0,
                        "center_y": base_y,
                        "position": 1,
                        "confidence": 0.9,
                    },
                    {
                        "card_id": base_card_id + 2,
                        "center_x": 300.0,
                        "center_y": base_y,
                        "position": 2,
                        "confidence": 0.9,
                    },
                    {
                        "card_id": base_card_id + 3,
                        "center_x": 500.0,
                        "center_y": base_y,
                        "position": 3,
                        "confidence": 0.9,
                    },
                ]
            )
            task._pack_result_rows.append(
                [
                    {
                        "card_id": base_card_id + 4,
                        "center_x": 200.0,
                        "center_y": base_y + 40.0,
                        "position": 1,
                        "confidence": 0.9,
                    },
                    {
                        "card_id": base_card_id + 5,
                        "center_x": 400.0,
                        "center_y": base_y + 40.0,
                        "position": 2,
                        "confidence": 0.9,
                    },
                ]
            )

        result = task._recognize_multi_pack_results()

        assert result is True
        assert task._save_pack_record.call_count == 10
        assert task._save_high_rarity_cards.call_count == 10
        assert task._result_recognized is True
        task._reset_pack_result_mode.assert_called_once()

    def test_handle_pack_opening_result_should_not_tap_continue_when_ten_pack_scan_fails(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._set_pack_result_mode(10)
        task._recognize_multi_pack_results = Mock(return_value=False)

        result = task._handle_pack_opening_result({"ocr_results": [{"text": "繼續"}]})

        assert result.success is True
        assert task.adb.tap_points == []
        task._recognize_multi_pack_results.assert_called_once()

    def test_handle_opening_card_should_wait_three_seconds_in_single_mode(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())

        result = task._handle_opening_card({})

        assert result.should_wait == 3.0
        assert len(task.adb.tap_points) == 6

    def test_handle_opening_card_should_wait_three_seconds_after_ten_fast_taps_in_ten_mode(
        self, pack_opening_base
    ):
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "test"

            def get_rare_card_notify_message(self):
                return "测试"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._set_pack_result_mode(10)

        waits = [task._handle_opening_card({}).should_wait for _ in range(11)]

        assert waits[:10] == [0.0] * 10
        assert waits[10] == 3.0


class TestBatchIdAndIndex:
    """测试十连包批次ID和序号功能"""

    def test_set_pack_result_mode_generates_batch_id_for_ten_pack(self, pack_opening_base):
        """十连包模式下应生成 batch_id"""
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "ten_pack"

            def get_rare_card_notify_message(self):
                return "十连开包"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._current_batch_id = None

        task._set_pack_result_mode(10)

        assert task._current_batch_id is not None
        assert "_" in task._current_batch_id

    def test_set_pack_result_mode_clears_batch_id_for_single_pack(self, pack_opening_base):
        """单包模式下 batch_id 应为 None"""
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "daily_free"

            def get_rare_card_notify_message(self):
                return "每日开包"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._current_batch_id = "old_batch_id"

        task._set_pack_result_mode(1)

        assert task._current_batch_id is None

    def test_save_pack_record_passes_batch_info(self, pack_opening_base):
        """_save_pack_record 应正确传递 batch_id 和 batch_index"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "ten_pack"

            def get_rare_card_notify_message(self):
                return "十连开包"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = object.__new__(TestTask)
        task._init_repositories = Mock()
        mock_account = Mock()
        mock_account.id = 123
        task._account = mock_account
        task._pack_record_repo = Mock()
        task._pack_point_repo = None
        task._base_pack_points = None
        task._packs_opened_count = 10
        task._current_batch_id = "test_batch_123"
        task._inferred_pack_context = None

        rows = [{"card_id": 1, "rarity": "★"}]
        task._save_pack_record(rows, batch_index=5)

        task._pack_record_repo.create_for_account.assert_called_once()
        call_kwargs = task._pack_record_repo.create_for_account.call_args
        assert call_kwargs[0][0] == 123  # account_id
        assert call_kwargs[1].get("batch_id") == "test_batch_123"
        assert call_kwargs[1].get("batch_index") == 5

    def test_recognize_multi_pack_results_passes_correct_batch_index(self, pack_opening_base):
        """_recognize_multi_pack_results 应循环传递正确的 batch_index"""

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "ten_pack"

            def get_rare_card_notify_message(self):
                return "十连开包"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = object.__new__(TestTask)
        task._init_repositories = Mock()
        task._collect_multi_pack_rows = Mock(return_value=True)
        task._log_multi_pack_rows_snapshot = Mock()
        task._reset_pack_result_mode = Mock()
        task._save_pack_record = Mock()
        task._save_high_rarity_cards = Mock()
        task._account_card_repo = Mock()
        mock_account = Mock()
        mock_account.id = 1
        task._account = mock_account
        task._pack_result_batch_size = 10
        task._pack_result_rows = []
        task._result_recognized = False
        task._current_batch_id = "batch_abc"

        # 构造10包数据，每包2行
        for pack_index in range(10):
            base_y = float(pack_index * 100)
            task._pack_result_rows.append(
                [{"card_id": pack_index * 6 + 1, "center_y": base_y}]
            )
            task._pack_result_rows.append(
                [{"card_id": pack_index * 6 + 2, "center_y": base_y + 40}]
            )

        result = task._recognize_multi_pack_results()

        assert result is True
        assert task._save_pack_record.call_count == 10

        # 验证每次调用的 batch_index 正确
        for i, call in enumerate(task._save_pack_record.call_args_list, start=1):
            assert call[1].get("batch_index") == i

    def test_reset_pack_result_mode_clears_batch_id(self, pack_opening_base):
        """_reset_pack_result_mode 应清除 batch_id"""
        from ptcgp_auto_v2.tests.fake_adb import FakeAdb

        class TestTask(pack_opening_base):
            def get_pack_record_type(self):
                return "ten_pack"

            def get_rare_card_notify_message(self):
                return "十连开包"

            def is_completed(self):
                return False

            def handle_page(self, page_name, page_info):
                return None

        task = TestTask(FakeAdb(), recognizer=None, page_detector=Mock())
        task._set_pack_result_mode(10)
        assert task._current_batch_id is not None

        task._reset_pack_result_mode()

        assert task._current_batch_id is None
        assert task._pack_result_mode == "single"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
