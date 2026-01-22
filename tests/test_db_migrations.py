import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from ptcgp_auto_v2.config.settings import Settings, get_settings, set_settings
from ptcgp_auto_v2.db.connection import get_database, reset_database


class TestDatabaseMigrations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        settings = Settings()
        settings.data_dir = Path(self.temp_dir.name)
        settings.db_name = "test.db"
        set_settings(settings)
        reset_database()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_accounts_has_remark_column(self):
        get_database()

        conn = sqlite3.connect(str(get_settings().db_path))
        try:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(accounts)")]
        finally:
            conn.close()

        self.assertIn("remark", columns)


if __name__ == "__main__":
    unittest.main()
