import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect
from werkzeug.security import generate_password_hash
from secrets import token_urlsafe

db = SQLAlchemy()


def _upgrade_rating_criterion_notes():
    if db.engine.dialect.name != "sqlite":
        return

    with db.engine.connect() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        connection.commit()
        try:
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("rating_criterion")
            }
            connection.commit()
            if "notes" in columns and columns["score"]["nullable"]:
                return

            notes_expression = "notes" if "notes" in columns else "NULL"
            with connection.begin():
                connection.exec_driver_sql(
                    """
                    CREATE TABLE rating_criterion_new (
                        id INTEGER NOT NULL PRIMARY KEY,
                        rating_id INTEGER NOT NULL,
                        name VARCHAR(80) NOT NULL,
                        score INTEGER,
                        notes TEXT,
                        CONSTRAINT uq_rating_criterion_name
                            UNIQUE (rating_id, name),
                        CONSTRAINT ck_rating_criterion_score
                            CHECK (score BETWEEN 1 AND 10),
                        FOREIGN KEY(rating_id) REFERENCES rating (id)
                    )
                    """
                )
                connection.exec_driver_sql(
                    "INSERT INTO rating_criterion_new "
                    "(id, rating_id, name, score, notes) "
                    "SELECT id, rating_id, name, score, "
                    f"{notes_expression} FROM rating_criterion"
                )
                connection.exec_driver_sql("DROP TABLE rating_criterion")
                connection.exec_driver_sql(
                    "ALTER TABLE rating_criterion_new RENAME TO rating_criterion"
                )
        finally:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.commit()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "development-only-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///project.db",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    db.init_app(app)

    from app import models  # noqa: F401

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        _upgrade_rating_criterion_notes()
        from app.models import User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            db.session.add(
                User(
                    username="demo",
                    email="demo@example.test",
                    password_hash=generate_password_hash(token_urlsafe(32)),
                )
            )
            db.session.commit()
        print("Initialized the database.")

    @app.get("/")
    def index():
        from app.models import Game, LibraryEntry, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        search_term = request.args.get("q", "").strip()
        library_query = LibraryEntry.query.join(Game).filter(
            LibraryEntry.user_id == demo_user.id
        )
        if search_term:
            library_query = library_query.filter(
                func.lower(Game.title).contains(
                    search_term.lower(), autoescape=True
                )
            )
        library_entries = library_query.order_by(LibraryEntry.added_at.desc()).all()
        return render_template(
            "index.html",
            library_entries=library_entries,
            search_term=search_term,
        )

    @app.get("/library")
    def library():
        return redirect(url_for("index"))

    @app.get("/library/<int:entry_id>/rating")
    def view_game_rating(entry_id):
        from app.models import LibraryEntry, RATING_CATEGORIES, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        entry = LibraryEntry.query.filter_by(
            id=entry_id, user_id=demo_user.id
        ).first()
        if entry is None:
            flash("That game is not in your library.", "error")
            return redirect(url_for("index"))
        if entry.rating is None:
            flash("This game has no rating to view yet.", "info")
            return redirect(url_for("rate_game_form", entry_id=entry.id))

        criteria = {criterion.name: criterion for criterion in entry.rating.criteria}
        return render_template(
            "rating_detail.html",
            entry=entry,
            categories=RATING_CATEGORIES,
            criteria=criteria,
        )

    @app.get("/library/add")
    def add_game_form():
        from app.models import RATING_CATEGORIES

        return render_template("add_game.html", categories=RATING_CATEGORIES)

    @app.post("/library/add")
    def add_game():
        from app.models import (
            Game,
            LibraryEntry,
            Rating,
            RatingCriterion,
            RATING_CATEGORIES,
            User,
        )

        title = request.form.get("title", "").strip()
        if not title:
            flash("Enter a game name to add it to your library.", "error")
            return redirect(url_for("add_game_form"))
        if len(title) > 200:
            flash("Game names must be 200 characters or fewer.", "error")
            return redirect(url_for("add_game_form"))

        category_values = {
            category: request.form.get(category, "").strip()
            for category in RATING_CATEGORIES
        }
        category_notes = {
            category: request.form.get(f"{category}_notes", "").strip()
            for category in RATING_CATEGORIES
        }
        overall_notes = request.form.get("overall_notes", "").strip()
        scores = {}
        if any(category_values.values()):
            if not all(category_values.values()):
                flash(
                    "Either leave all rating categories blank or score all five.",
                    "error",
                )
                return redirect(url_for("add_game_form"))

            for category, value in category_values.items():
                try:
                    score = int(value)
                except ValueError:
                    flash(
                        "Enter a whole-number score from 1 to 10 for each category.",
                        "error",
                    )
                    return redirect(url_for("add_game_form"))
                if not 1 <= score <= 10:
                    flash("Scores must be from 1 to 10.", "error")
                    return redirect(url_for("add_game_form"))
                scores[category] = score

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        game = Game.query.filter(func.lower(Game.title) == title.lower()).first()
        if game is None:
            game = Game(title=title)
            db.session.add(game)
            db.session.flush()

        existing_entry = LibraryEntry.query.filter_by(
            user_id=demo_user.id, game_id=game.id
        ).first()
        if existing_entry is not None:
            flash(f"{game.title} is already in your library.", "info")
            return redirect(url_for("index"))

        entry = LibraryEntry(user=demo_user, game=game)
        db.session.add(entry)
        if scores or overall_notes or any(category_notes.values()):
            entry.rating = Rating(
                overall_score=(
                    round(sum(scores.values()) / len(RATING_CATEGORIES), 1)
                    if scores
                    else None
                ),
                notes=overall_notes or None,
                criteria=[
                    RatingCriterion(
                        name=category,
                        score=scores.get(category),
                        notes=category_notes[category] or None,
                    )
                    for category in RATING_CATEGORIES
                    if category in scores or category_notes[category]
                ],
            )
        db.session.commit()
        if scores or overall_notes or any(category_notes.values()):
            flash(f"Added {game.title} and saved its ratings and notes.", "success")
        else:
            flash(f"Added {game.title} to your library.", "success")
        return redirect(url_for("index"))

    @app.get("/library/<int:entry_id>/rate")
    def rate_game_form(entry_id):
        from app.models import LibraryEntry, RATING_CATEGORIES, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        entry = LibraryEntry.query.filter_by(
            id=entry_id, user_id=demo_user.id
        ).first()
        if entry is None:
            flash("That game is not in your library.", "error")
            return redirect(url_for("index"))

        scores = (
            {criterion.name: criterion.score for criterion in entry.rating.criteria}
            if entry.rating
            else {}
        )
        category_notes = (
            {criterion.name: criterion.notes or "" for criterion in entry.rating.criteria}
            if entry.rating
            else {}
        )
        return render_template(
            "rate_game.html",
            entry=entry,
            categories=RATING_CATEGORIES,
            scores=scores,
            category_notes=category_notes,
            overall_notes=entry.rating.notes if entry.rating else "",
        )

    @app.post("/library/<int:entry_id>/rate")
    def save_game_rating(entry_id):
        from app.models import LibraryEntry, Rating, RatingCriterion, RATING_CATEGORIES, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        entry = LibraryEntry.query.filter_by(
            id=entry_id, user_id=demo_user.id
        ).first()
        if entry is None:
            flash("That game is not in your library.", "error")
            return redirect(url_for("index"))

        score_values = {
            category: request.form.get(category, "").strip()
            for category in RATING_CATEGORIES
        }
        category_notes = {
            category: request.form.get(f"{category}_notes", "").strip()
            for category in RATING_CATEGORIES
        }
        overall_notes = request.form.get("overall_notes", "").strip()
        scores = {}
        if any(score_values.values()) and not all(score_values.values()):
            flash(
                "Either leave all rating scores blank or score all five categories.",
                "error",
            )
            return redirect(url_for("rate_game_form", entry_id=entry.id))

        for category in RATING_CATEGORIES:
            value = score_values[category]
            if not value:
                continue
            try:
                score = int(value)
            except ValueError:
                flash(
                    "Enter a whole-number score from 1 to 10 for each category.",
                    "error",
                )
                return redirect(url_for("rate_game_form", entry_id=entry.id))
            if not 1 <= score <= 10:
                flash("Scores must be from 1 to 10.", "error")
                return redirect(url_for("rate_game_form", entry_id=entry.id))
            scores[category] = score

        rating = entry.rating
        if rating is None and (scores or overall_notes or any(category_notes.values())):
            rating = Rating(library_entry=entry)
            db.session.add(rating)

        if rating is not None:
            rating.overall_score = (
                round(sum(scores.values()) / len(RATING_CATEGORIES), 1) if scores else None
            )
            rating.notes = overall_notes or None
            criteria_by_name = {
                criterion.name: criterion for criterion in rating.criteria
            }
            for category in RATING_CATEGORIES:
                score = scores.get(category)
                notes = category_notes[category] or None
                criterion = criteria_by_name.get(category)
                if criterion is None and (score is not None or notes):
                    rating.criteria.append(
                        RatingCriterion(name=category, score=score, notes=notes)
                    )
                elif criterion is not None and (score is not None or notes):
                    criterion.score = score
                    criterion.notes = notes
                elif criterion is not None:
                    rating.criteria.remove(criterion)

            if not scores and not overall_notes and not any(category_notes.values()):
                db.session.delete(rating)

        db.session.commit()
        flash(f"Saved ratings and notes for {entry.game.title}.", "success")
        return redirect(url_for("index"))

    @app.post("/library/<int:entry_id>/remove")
    def remove_game(entry_id):
        from app.models import LibraryEntry, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        entry = LibraryEntry.query.filter_by(
            id=entry_id, user_id=demo_user.id
        ).first()
        if entry is None:
            flash("That game is not in your library.", "error")
            return redirect(url_for("index"))

        title = entry.game.title
        db.session.delete(entry)
        db.session.commit()
        flash(f"Removed {title} from your library.", "success")
        return redirect(url_for("index"))

    return app
