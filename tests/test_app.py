import tempfile
import unittest
from pathlib import Path

from app import create_app, db
from app.models import Game, LibraryEntry, Rating, RatingCriterion, User


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

        self.assertIn(b"My Library", response.data)
        self.assertIn(b"Add a game", response.data)
        self.assertIn(b"No games yet", response.data)

    def test_homepage_displays_added_games(self):
        self.client.post("/library/add", data={"title": "Example Game"})

        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<strong>Example Game</strong>", response.data)
        self.assertNotIn(b'name="title"', response.data)

    def test_add_game_page_displays_game_form(self):
        response = self.client.get("/library/add")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'name="title"', response.data)
        self.assertIn(b"Back to library", response.data)
        for category in ("Gameplay", "Story", "Graphics", "Music", "Difficulty"):
            self.assertIn(category.encode(), response.data)
            self.assertIn(f'name="{category}_notes"'.encode(), response.data)
        self.assertIn(b'name="overall_notes"', response.data)

    def test_adding_game_with_scores_saves_rating_and_average(self):
        response = self.client.post(
            "/library/add",
            data={
                "title": "Rated Game",
                "Gameplay": "8",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "7",
            },
        )

        self.assertEqual(response.status_code, 302)
        homepage = self.client.get(response.headers["Location"])
        self.assertIn(
            b"Added Rated Game and saved its ratings and notes.", homepage.data
        )
        self.assertIn(b"Overall: 8.2/10", homepage.data)
        with self.app.app_context():
            self.assertEqual(LibraryEntry.query.count(), 1)
            self.assertEqual(Rating.query.count(), 1)
            rating = Rating.query.one()
            self.assertEqual(rating.overall_score, 8.2)
            self.assertEqual(RatingCriterion.query.count(), 5)

    def test_adding_game_with_no_scores_leaves_it_unrated(self):
        response = self.client.post(
            "/library/add",
            data={
                "title": "Unrated Game",
                "Gameplay": "",
                "Story": "",
                "Graphics": "",
                "Music": "",
                "Difficulty": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(LibraryEntry.query.count(), 1)
            self.assertEqual(Rating.query.count(), 0)

    def test_adding_game_saves_optional_category_and_overall_notes(self):
        response = self.client.post(
            "/library/add",
            data={
                "title": "Notes Game",
                "Gameplay": "8",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "7",
                "Gameplay_notes": "Combat feels responsive.",
                "Music_notes": "The soundtrack is memorable.",
                "overall_notes": "I would replay this.",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            rating = Rating.query.one()
            self.assertEqual(rating.notes, "I would replay this.")
            self.assertEqual(
                {criterion.name: criterion.notes for criterion in rating.criteria},
                {
                    "Gameplay": "Combat feels responsive.",
                    "Story": None,
                    "Graphics": None,
                    "Music": "The soundtrack is memorable.",
                    "Difficulty": None,
                },
            )

    def test_adding_game_can_save_notes_without_scores(self):
        response = self.client.post(
            "/library/add",
            data={
                "title": "Notes Only Game",
                "Gameplay_notes": "A note before scoring.",
                "overall_notes": "Try this again later.",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            rating = Rating.query.one()
            self.assertIsNone(rating.overall_score)
            self.assertEqual(rating.notes, "Try this again later.")
            self.assertEqual(
                {criterion.name: criterion.notes for criterion in rating.criteria},
                {"Gameplay": "A note before scoring."},
            )

    def test_library_displays_notes_only_rating_as_unrated(self):
        self.client.post(
            "/library/add",
            data={"title": "Notes Only Game", "overall_notes": "Revisit later."},
        )

        response = self.client.get("/")

        self.assertIn(b"Not rated", response.data)
        self.assertIn(b"View rating", response.data)

    def test_adding_game_with_partial_scores_is_rejected(self):
        response = self.client.post(
            "/library/add",
            data={"title": "Partially Rated", "Gameplay": "8"},
        )

        self.assertEqual(response.headers["Location"], "/library/add")
        add_page = self.client.get(response.headers["Location"])
        self.assertIn(b"score all five", add_page.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_adding_game_with_out_of_range_score_is_rejected(self):
        response = self.client.post(
            "/library/add",
            data={
                "title": "Invalidly Rated",
                "Gameplay": "11",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "7",
            },
        )

        self.assertEqual(response.headers["Location"], "/library/add")
        add_page = self.client.get(response.headers["Location"])
        self.assertIn(b"Scores must be from 1 to 10", add_page.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_library_displays_overall_rating(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry = LibraryEntry.query.one()
            db.session.add(
                Rating(
                    library_entry=entry,
                    overall_score=8.4,
                    criteria=[
                        RatingCriterion(name="Gameplay", score=8),
                        RatingCriterion(name="Story", score=9),
                        RatingCriterion(name="Graphics", score=8),
                        RatingCriterion(name="Music", score=9),
                        RatingCriterion(name="Difficulty", score=8),
                    ],
                )
            )
            db.session.commit()
            entry_id = entry.id

        response = self.client.get("/")

        self.assertIn(b"Overall: 8.4/10", response.data)
        self.assertIn(b"View rating", response.data)
        self.assertIn(f"/library/{entry_id}/rating".encode(), response.data)

    def test_rating_detail_shows_scores_notes_and_edit_link(self):
        self.client.post(
            "/library/add",
            data={
                "title": "Detailed Game",
                "Gameplay": "8",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "7",
                "Gameplay_notes": "Responsive combat.",
                "overall_notes": "Worth replaying.",
            },
        )
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.get(f"/library/{entry_id}/rating")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Detailed Game", response.data)
        self.assertIn(b"Overall: 8.2/10", response.data)
        self.assertIn(b"Gameplay", response.data)
        self.assertIn(b"8/10", response.data)
        self.assertIn(b"Responsive combat.", response.data)
        self.assertIn(b"Worth replaying.", response.data)
        self.assertIn(f"/library/{entry_id}/rate".encode(), response.data)

    def test_rating_detail_for_unrated_game_redirects_to_rating_form(self):
        self.client.post("/library/add", data={"title": "Unrated Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.get(f"/library/{entry_id}/rating")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], f"/library/{entry_id}/rate")

    def test_rating_form_shows_all_categories(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.get(f"/library/{entry_id}/rate")

        self.assertEqual(response.status_code, 200)
        for category in ("Gameplay", "Story", "Graphics", "Music", "Difficulty"):
            self.assertIn(category.encode(), response.data)
            self.assertIn(f'name="{category}_notes"'.encode(), response.data)
        self.assertIn(b'name="overall_notes"', response.data)

    def test_saving_rating_persists_category_scores_and_average(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.post(
            f"/library/{entry_id}/rate",
            data={
                "Gameplay": "8",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "7",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            rating = Rating.query.one()
            self.assertEqual(rating.overall_score, 8.2)
            self.assertEqual(
                {criterion.name: criterion.score for criterion in rating.criteria},
                {
                    "Gameplay": 8,
                    "Story": 9,
                    "Graphics": 7,
                    "Music": 10,
                    "Difficulty": 7,
                },
            )
        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Overall: 8.2/10", homepage.data)

    def test_saving_rating_updates_existing_scores(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        scores = {
            "Gameplay": "8",
            "Story": "8",
            "Graphics": "8",
            "Music": "8",
            "Difficulty": "8",
        }
        self.client.post(f"/library/{entry_id}/rate", data=scores)
        updated_response = self.client.post(
            f"/library/{entry_id}/rate",
            data={category: "10" for category in scores},
        )

        self.assertEqual(updated_response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(Rating.query.count(), 1)
            self.assertEqual(RatingCriterion.query.count(), 5)
            self.assertEqual(Rating.query.one().overall_score, 10.0)

    def test_saving_rating_updates_and_displays_notes(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id
        scores = {
            "Gameplay": "8",
            "Story": "8",
            "Graphics": "8",
            "Music": "8",
            "Difficulty": "8",
        }

        response = self.client.post(
            f"/library/{entry_id}/rate",
            data={
                **scores,
                "Gameplay_notes": "Strong combat.",
                "overall_notes": "A solid experience.",
            },
        )
        self.assertEqual(response.status_code, 302)

        edit_page = self.client.get(f"/library/{entry_id}/rate")

        self.assertIn(b"Strong combat.", edit_page.data)
        self.assertIn(b"A solid experience.", edit_page.data)
        with self.app.app_context():
            rating = Rating.query.one()
            self.assertEqual(rating.notes, "A solid experience.")
            self.assertEqual(
                RatingCriterion.query.filter_by(name="Gameplay").one().notes,
                "Strong combat.",
            )

    def test_clearing_all_rating_scores_and_notes_removes_rating(self):
        self.client.post(
            "/library/add",
            data={
                "title": "Example Game",
                "Gameplay": "8",
                "Story": "8",
                "Graphics": "8",
                "Music": "8",
                "Difficulty": "8",
                "overall_notes": "Good game.",
            },
        )
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.post(
            f"/library/{entry_id}/rate",
            data={
                "Gameplay": "",
                "Story": "",
                "Graphics": "",
                "Music": "",
                "Difficulty": "",
                "overall_notes": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(Rating.query.count(), 0)
            self.assertEqual(RatingCriterion.query.count(), 0)
        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Not rated", homepage.data)

    def test_invalid_category_score_is_rejected(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry_id = LibraryEntry.query.one().id

        response = self.client.post(
            f"/library/{entry_id}/rate",
            data={
                "Gameplay": "11",
                "Story": "9",
                "Graphics": "7",
                "Music": "10",
                "Difficulty": "6",
            },
        )

        self.assertEqual(response.headers["Location"], f"/library/{entry_id}/rate")
        with self.app.app_context():
            self.assertEqual(Rating.query.count(), 0)

    def test_library_url_redirects_to_homepage(self):
        response = self.client.get("/library")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_adding_game_saves_it_to_demo_users_library(self):
        response = self.client.post(
            "/library/add", data={"title": "  Example Game  "}
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")
        library_page = self.client.get(response.headers["Location"])
        self.assertIn(b"Added Example Game to your library.", library_page.data)
        self.assertIn(b"<strong>Example Game</strong>", library_page.data)

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

        self.assertEqual(response.headers["Location"], "/library/add")
        add_page = self.client.get(response.headers["Location"])
        self.assertIn(b"Enter a game name", add_page.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_game_name_over_200_characters_is_rejected(self):
        response = self.client.post("/library/add", data={"title": "G" * 201})

        self.assertEqual(response.headers["Location"], "/library/add")
        add_page = self.client.get(response.headers["Location"])
        self.assertIn(b"200 characters or fewer", add_page.data)
        with self.app.app_context():
            self.assertEqual(Game.query.count(), 0)
            self.assertEqual(LibraryEntry.query.count(), 0)

    def test_removing_game_deletes_library_entry_but_keeps_game(self):
        self.client.post("/library/add", data={"title": "Example Game"})
        with self.app.app_context():
            entry = LibraryEntry.query.one()
            entry_id = entry.id
            db.session.add(Rating(library_entry=entry, overall_score=8))
            db.session.commit()

        response = self.client.post(f"/library/{entry_id}/remove")

        self.assertEqual(response.status_code, 302)
        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"Removed Example Game from your library.", homepage.data)
        self.assertIn(b"No games yet", homepage.data)
        with self.app.app_context():
            self.assertEqual(LibraryEntry.query.count(), 0)
            self.assertEqual(Rating.query.count(), 0)
            self.assertEqual(Game.query.count(), 1)

    def test_removing_unknown_entry_does_not_delete_games(self):
        self.client.post("/library/add", data={"title": "Example Game"})

        response = self.client.post("/library/999/remove")

        homepage = self.client.get(response.headers["Location"])
        self.assertIn(b"That game is not in your library.", homepage.data)
        self.assertIn(b"Example Game", homepage.data)
        with self.app.app_context():
            self.assertEqual(LibraryEntry.query.count(), 1)
            self.assertEqual(Game.query.count(), 1)

    def test_init_db_creates_foundation_tables(self):
        result = self.app.test_cli_runner().invoke(args=["init-db"])
        self.assertEqual(result.exit_code, 0, result.output)

        with self.app.app_context():
            self.assertEqual(
                set(db.inspect(db.engine).get_table_names()),
                {"game", "library_entry", "rating", "rating_criterion", "user"},
            )
            self.assertIsNotNone(User.query.filter_by(username="demo").first())

    def test_init_db_upgrades_existing_category_notes_schema(self):
        self.client.post("/library/add", data={"title": "Existing Game"})
        with self.app.app_context():
            entry = LibraryEntry.query.one()
            db.session.add(
                Rating(
                    library_entry=entry,
                    overall_score=8.0,
                    criteria=[RatingCriterion(name="Gameplay", score=8)],
                )
            )
            db.session.commit()
            db.session.remove()

            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE rating_criterion_legacy (
                        id INTEGER NOT NULL PRIMARY KEY,
                        rating_id INTEGER NOT NULL,
                        name VARCHAR(80) NOT NULL,
                        score INTEGER NOT NULL,
                        CONSTRAINT uq_rating_criterion_name
                            UNIQUE (rating_id, name),
                        CONSTRAINT ck_rating_criterion_score
                            CHECK (score BETWEEN 1 AND 10),
                        FOREIGN KEY(rating_id) REFERENCES rating (id)
                    )
                    """
                )
                connection.exec_driver_sql(
                    "INSERT INTO rating_criterion_legacy "
                    "(id, rating_id, name, score) "
                    "SELECT id, rating_id, name, score FROM rating_criterion"
                )
                connection.exec_driver_sql("DROP TABLE rating_criterion")
                connection.exec_driver_sql(
                    "ALTER TABLE rating_criterion_legacy "
                    "RENAME TO rating_criterion"
                )

        result = self.app.test_cli_runner().invoke(args=["init-db"])

        self.assertEqual(result.exit_code, 0, f"{result.output}\n{result.exception!r}")
        with self.app.app_context():
            columns = {
                column["name"]: column
                for column in db.inspect(db.engine).get_columns("rating_criterion")
            }
            self.assertTrue(columns["score"]["nullable"])
            self.assertTrue(columns["notes"]["nullable"])
            criterion = RatingCriterion.query.one()
            self.assertEqual(criterion.name, "Gameplay")
            self.assertEqual(criterion.score, 8)


if __name__ == "__main__":
    unittest.main()
