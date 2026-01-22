import sys
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.orm.exc import DetachedInstanceError
from sqlmodel import Session, SQLModel

src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.config.settings import Settings, set_settings
from ptcgp_auto_v2.db import engine as db_engine
from ptcgp_auto_v2.db.connection import reset_database
from ptcgp_auto_v2.db.models import Account, TaskPlan
from ptcgp_auto_v2.db.repositories import AccountRepository


class TestAccountRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings()
        settings.data_dir = Path(self.temp_dir.name)
        settings.db_name = "test.db"
        set_settings(settings)

        reset_database()
        db_engine._engine = None
        engine = db_engine.get_engine()
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            session.add(TaskPlan(name="daily", description="daily", task_types="[]"))
            session.commit()

        self.repo = AccountRepository()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_all_preloads_task_plan(self):
        self.repo.create(Account(game_id="game-id-1"))

        accounts = self.repo.get_all()
        self.assertEqual(1, len(accounts))

        try:
            plan_name = accounts[0].task_plan.name if accounts[0].task_plan else None
        except DetachedInstanceError as exc:
            self.fail(f"get_all should preload task_plan, but raised: {exc}")

        self.assertEqual("daily", plan_name)


if __name__ == "__main__":
    unittest.main()
