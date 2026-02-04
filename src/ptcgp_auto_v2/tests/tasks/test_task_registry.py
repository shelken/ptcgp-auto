# -*- coding: utf-8 -*-
"""
任务注册表测试
"""

import sys
import unittest
from pathlib import Path

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

import ptcgp_auto_v2.tasks


class TestTaskRegistry(unittest.TestCase):
    """测试任务注册表"""

    def test_wonder_pick_registered(self):
        """测试得卡挑战任务已注册"""
        self.assertIn("wonder_pick", ptcgp_auto_v2.tasks.TaskRegistry.all_types())


if __name__ == "__main__":
    unittest.main()
