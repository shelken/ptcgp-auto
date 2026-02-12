# -*- coding: utf-8 -*-
"""调度器 init_first 策略测试。"""

import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.scheduler import Scheduler, SchedulerConfig


class TestSchedulerInitFirstStrategy(unittest.TestCase):
    """测试 init_first 对批次选择策略的影响。"""

    def test_default_should_pick_non_init_first(self):
        """默认策略应先尝试非 init 任务批次。"""
        scheduler = Scheduler(
            device_addresses=[], config=SchedulerConfig(init_first=False)
        )

        expected_batch = ("acc", ["task"])  # 仅用于断言流程
        scheduler._get_next_non_init_batch = lambda: expected_batch  # type: ignore[method-assign]
        scheduler._get_next_account_batch = lambda: None  # type: ignore[method-assign]

        result = scheduler._pick_next_account_batch()
        self.assertEqual(expected_batch, result)

    def test_default_should_fallback_to_init_batch_when_non_init_missing(self):
        """默认策略在无非 init 批次时，应回退到包含 init 的批次。"""
        scheduler = Scheduler(
            device_addresses=[], config=SchedulerConfig(init_first=False)
        )

        expected_batch = ("acc", ["init_account"])
        scheduler._get_next_non_init_batch = lambda: None  # type: ignore[method-assign]
        scheduler._get_next_account_batch = lambda: expected_batch  # type: ignore[method-assign]

        result = scheduler._pick_next_account_batch()
        self.assertEqual(expected_batch, result)

    def test_init_first_should_pick_init_batch_directly(self):
        """开启 init_first 后应直接按 init 优先策略取批次。"""
        scheduler = Scheduler(
            device_addresses=[], config=SchedulerConfig(init_first=True)
        )

        expected_batch = ("acc", ["init_account"])
        scheduler._get_next_non_init_batch = lambda: None  # type: ignore[method-assign]
        scheduler._get_next_account_batch = lambda: expected_batch  # type: ignore[method-assign]

        result = scheduler._pick_next_account_batch()
        self.assertEqual(expected_batch, result)


if __name__ == "__main__":
    unittest.main()
