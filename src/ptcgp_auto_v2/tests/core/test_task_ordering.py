import sys
import unittest
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine, select

src_dir = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.core.task_ordering import (  # noqa: E402
    TASK_SORT_BY_LAST_DURATION,
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
        self.assertIn("schedule_anchor_at", sql_text)
        self.assertIn("last_completed_at", sql_text)

    def test_build_dispatch_priority_order_prefers_schedule_anchor_at(self):
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            early_anchor = TaskInstance(
                account_id=1,
                task_type="open_pack",
                status="pending",
                reset_type="daily",
                next_run_at=None,
                last_completed_at=datetime(2026, 3, 1, 8, 0, 0),
                schedule_anchor_at=datetime(2026, 3, 5, 8, 0, 0),
            )
            late_anchor = TaskInstance(
                account_id=2,
                task_type="claim_rewards",
                status="pending",
                reset_type="daily",
                next_run_at=None,
                last_completed_at=datetime(2026, 2, 1, 8, 0, 0),
                schedule_anchor_at=datetime(2026, 3, 6, 8, 0, 0),
            )
            session.add(early_anchor)
            session.add(late_anchor)
            session.commit()

            statement = select(TaskInstance).order_by(
                *build_task_instance_order_by("dispatch_priority", "asc")
            )
            ordered = list(session.exec(statement).all())

        self.assertEqual([1, 2], [item.account_id for item in ordered])

    def test_normalize_task_sort_accepts_last_duration(self):
        sort_by, sort_order = normalize_task_sort(
            sort_by=TASK_SORT_BY_LAST_DURATION,
            sort_order="desc",
        )

        self.assertEqual(TASK_SORT_BY_LAST_DURATION, sort_by)
        self.assertEqual("desc", sort_order)

    def test_build_last_duration_order_contains_duration_column(self):
        order_by = build_task_instance_order_by(
            sort_by=TASK_SORT_BY_LAST_DURATION,
            sort_order="desc",
        )
        statement = select(TaskInstance).order_by(*order_by)
        sql_text = str(statement)

        self.assertIn("last_duration_seconds", sql_text)


if __name__ == "__main__":
    unittest.main()
