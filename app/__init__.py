import os

from flask import Flask, flash, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import generate_password_hash
from secrets import token_urlsafe

db = SQLAlchemy()


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
        from app.models import LibraryEntry, User

        demo_user = User.query.filter_by(username="demo").first()
        if demo_user is None:
            return "Database not initialized. Run `flask --app run.py init-db`.", 503

        library_entries = (
            LibraryEntry.query.filter_by(user_id=demo_user.id)
            .order_by(LibraryEntry.added_at.desc())
            .all()
        )
        return render_template("index.html", library_entries=library_entries)

    @app.get("/library")
    def library():
        return redirect(url_for("index"))

    @app.get("/library/add")
    def add_game_form():
        return render_template("add_game.html")

    @app.post("/library/add")
    def add_game():
        from app.models import Game, LibraryEntry, User

        title = request.form.get("title", "").strip()
        if not title:
            flash("Enter a game name to add it to your library.", "error")
            return redirect(url_for("add_game_form"))
        if len(title) > 200:
            flash("Game names must be 200 characters or fewer.", "error")
            return redirect(url_for("add_game_form"))

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

        db.session.add(LibraryEntry(user=demo_user, game=game))
        db.session.commit()
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
        return render_template(
            "rate_game.html",
            entry=entry,
            categories=RATING_CATEGORIES,
            scores=scores,
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

        scores = {}
        for category in RATING_CATEGORIES:
            value = request.form.get(category, "")
            try:
                score = int(value)
            except ValueError:
                flash("Enter a whole-number score from 1 to 10 for each category.", "error")
                return redirect(url_for("rate_game_form", entry_id=entry.id))
            if not 1 <= score <= 10:
                flash("Scores must be from 1 to 10.", "error")
                return redirect(url_for("rate_game_form", entry_id=entry.id))
            scores[category] = score

        rating = entry.rating
        if rating is None:
            rating = Rating(library_entry=entry)
            db.session.add(rating)

        rating.overall_score = round(sum(scores.values()) / len(RATING_CATEGORIES), 1)
        criteria_by_name = {criterion.name: criterion for criterion in rating.criteria}
        for category, score in scores.items():
            criterion = criteria_by_name.get(category)
            if criterion is None:
                rating.criteria.append(RatingCriterion(name=category, score=score))
            else:
                criterion.score = score

        for criterion in list(rating.criteria):
            if criterion.name not in scores:
                rating.criteria.remove(criterion)

        db.session.commit()
        flash(f"Saved ratings for {entry.game.title}.", "success")
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
