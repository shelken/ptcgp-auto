import sys
import unittest
from pathlib import Path

from sqlmodel import select

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_ordering import (  # noqa: E402
    build_task_instance_order_by,
    normalize_task_sort,
)
from ptcgp_auto_v2.db.models import TaskInstance  # noqa: E402


class TestTaskOrdering(unittest.TestCase):
    """任务排序统一策略测试。"""

    def test_normalize_task_sort_defaults_to_dispatch_priority(self):
        sort_by, sort_order = normalize_task_sort(sort_by="unknown", sort_order="xxx")
        self.assertEqual("dispatch_priority", sort_by)
        self.assertEqual("asc", sort_order)

    def test_build_dispatch_priority_order_contains_once_priority(self):
        order_by = build_task_instance_order_by(
            sort_by="dispatch_priority",
            sort_order="asc",
        )
        statement = select(TaskInstance).order_by(*order_by)
        sql_text = str(statement)

        self.assertIn("reset_type", sql_text)
        self.assertIn("next_run_at", sql_text)
        self.assertIn("last_completed_at", sql_text)


if __name__ == "__main__":
    unittest.main()
