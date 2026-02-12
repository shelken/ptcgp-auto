# -*- coding: utf-8 -*-
"""init_first 配置基础测试。"""

import unittest

from ptcgp_auto_v2.core.scheduler import SchedulerConfig


class TestSchedulerInitFirstConfig(unittest.TestCase):
    """验证 init_first 配置项行为。"""

    def test_init_first_default_false(self):
        """默认不启用 init_first。"""
        config = SchedulerConfig()
        self.assertFalse(config.init_first)

    def test_init_first_can_be_enabled(self):
        """支持显式启用 init_first。"""
        config = SchedulerConfig(init_first=True)
        self.assertTrue(config.init_first)


if __name__ == "__main__":
    unittest.main()
