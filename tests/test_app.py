import tempfile
import unittest
from pathlib import Path

from app import create_app, db


class AppFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "test.db"
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_homepage_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Game Ratings", response.data)

    def test_init_db_creates_foundation_tables(self):
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            self.assertEqual(
                set(db.inspect(db.engine).get_table_names()),
                {"game", "library_entry", "rating", "rating_criterion", "user"},
            )


if __name__ == "__main__":
    unittest.main()
