import tempfile
import unittest
from pathlib import Path

from app import create_app, db
from app.models import Game, LibraryEntry, User


class AppTests(unittest.TestCase):
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
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.temp_dir.cleanup()

    def test_homepage_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Add to library", response.data)
        self.assertIn(b"No games yet", response.data)

    def test_adding_game_saves_it_to_demo_users_library(self):
        response = self.client.post(
            "/library/add", data={"title": "  Example Game  "}
        )

        self.assertEqual(response.status_code, 302)
        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Added Example Game to your library.", homepage.data)
        self.assertIn(b"<li>Example Game</li>", homepage.data)

        with self.app.app_context():
            demo_user = User.query.filter_by(username="demo").one()
            game = Game.query.filter_by(title="Example Game").one()
            entry = LibraryEntry.query.one()
            self.assertEqual(entry.user_id, demo_user.id)
            self.assertEqual(entry.game_id, game.id)

    def test_adding_duplicate_game_does_not_duplicate_library_entry(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        response = self.client.post(
            "/library/add", data={"title": "  example game "}
        )

        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Example Game is already in your library.", homepage.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 1)
            self.assertEqual(LibraryEntry.query.count(), 1)

    def test_empty_game_name_is_rejected(self):
        response = self.client.post("/library/add", data={"title": "  "})

        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Enter a game name", homepage.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_game_name_over_200_characters_is_rejected(self):
        response = self.client.post("/library/add", data={"title": "G" * 201})

        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"200 characters or fewer", homepage.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_init_db_creates_foundation_tables(self):
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            self.assertEqual(
                set(db.inspect(db.engine).get_table_names()),
                {"game", "library_entry", "rating", "rating_criterion", "user"},
            )
            self.assertIsNotNone(User.query.filter_by(username="demo").first())


if __name__ == "__main__":
    unittest.main()
