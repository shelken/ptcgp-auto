# -*- coding: utf-8 -*-

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

src_dir = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_base import ActionResult
from ptcgp_auto_v2.tasks.utils.rarity_filter import handle_filter_panel


class _DummyAdb:
    def scaled_y(self, value: int) -> int:
        return value

    def scaled_x(self, value: int) -> int:
        return value


class TestRarityFilter(unittest.TestCase):
    @patch("ptcgp_auto_v2.tasks.utils.rarity_filter.tap_text_exact")
    def test_handle_filter_panel_should_reuse_empty_action_cache(
        self, tap_text_exact_mock
    ):
        """传入空 action_cache 时应复用原对象，避免状态丢失。"""
        tap_text_exact_mock.return_value = ActionResult.ok(wait=0.1)
        action_cache: dict[str, bool] = {}

        handle_filter_panel(
            adb=cast(Any, _DummyAdb()),
            page_detector=cast(Any, SimpleNamespace()),
            icon_detector=cast(Any, SimpleNamespace()),
            page_info={"ocr_results": [{"text": "清除", "box": (1, 1, 2, 2)}]},
            rarity_codes=["SR"],
            action_cache=action_cache,
        )

        self.assertTrue(action_cache.get("filter_cleared", False))


if __name__ == "__main__":
    unittest.main()
